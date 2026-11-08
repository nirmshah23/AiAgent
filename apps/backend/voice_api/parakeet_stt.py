"""Bounded utterance recognition with local Parakeet TDT v3 FP32 ONNX on CPU."""

import os
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
import onnx_asr
import onnxruntime as ort

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams, VADState

from .stt import run_inference

_MODEL_LOCK = threading.Lock()
_INFERENCE_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _load_model(path: str, threads: int):
    root = Path(path)
    required = (
        "config.json",
        "vocab.txt",
        "encoder-model.onnx",
        "encoder-model.onnx.data",
        "decoder_joint-model.onnx",
    )
    if any(not (root / name).is_file() for name in required):
        raise ValueError("Prepare PARAKEET_MODEL_PATH with the FP32 ONNX model files")
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    # Architecture name plus a local path prevents Hugging Face resolution/downloads.
    return onnx_asr.load_model(
        "nemo-conformer-tdt",
        path=root,
        quantization=None,
        providers=["CPUExecutionProvider"],
        sess_options=options,
        preprocessor_config={"use_numpy_preprocessors": True},
    )


class ParakeetRecognizer:
    """Share serialized inference; keep PCM buffers and endpointing per session."""

    MAX_BYTES = 20 * 32000
    PRE_ROLL_BYTES = 16000  # Half a second protects initial consonants.

    def __init__(self):
        """Require prepared FP32 weights; explicitly choose the CPU provider."""
        path = os.getenv("PARAKEET_MODEL_PATH", "models/parakeet-tdt-0.6b-v3")
        threads = int(os.getenv("STT_CPU_THREADS", "4"))
        if not 1 <= threads <= 32:
            raise ValueError("STT_CPU_THREADS must be between 1 and 32")
        with _MODEL_LOCK:
            self.model = _load_model(str(Path(path).resolve()), threads)
        self.vad = SileroVADAnalyzer(sample_rate=16000, params=VADParams(stop_secs=0.6))
        self.vad.set_sample_rate(16000)
        self.buffer = bytearray()
        self.speaking = False

    def _transcribe(self, audio):
        waveform = np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768.0
        with _INFERENCE_LOCK:
            return self.model.recognize(waveform, sample_rate=16000)

    async def _finish(self):
        audio = bytes(self.buffer)
        self.buffer.clear()
        if not self.speaking:
            return []
        self.speaking = False
        return [await run_inference(self._transcribe, audio)]

    async def accept(self, audio: bytes) -> list[str]:
        """Endpoint on silence while held; split continuous speech at twenty seconds."""
        texts = []
        # Small windows make endpointing independent of WebSocket chunk boundaries.
        for offset in range(0, len(audio), 1024):
            chunk = audio[offset : offset + 1024]
            self.buffer.extend(chunk)
            state = await self.vad.analyze_audio(chunk)
            if state in {VADState.SPEAKING, VADState.STOPPING}:
                self.speaking = True
            if self.speaking and (state == VADState.QUIET or len(self.buffer) >= self.MAX_BYTES):
                texts.extend(await self._finish())
            elif not self.speaking:
                del self.buffer[: -self.PRE_ROLL_BYTES]
        return texts

    async def flush(self) -> list[str]:
        """Transcribe remaining speech exactly once before synthetic endpoint silence."""
        texts = await self._finish()
        self.vad.set_params(self.vad.params)
        return texts

    async def close(self):
        """Discard unfinished audio and release this session's VAD executor."""
        self.buffer.clear()
        self.speaking = False
        await self.vad.cleanup()
