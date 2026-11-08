"""Local English Vosk provider, independent of transport and dialog."""

import json
import os
from functools import lru_cache
from pathlib import Path

from vosk import KaldiRecognizer, Model

from .stt import run_inference


@lru_cache(maxsize=1)
def english_model():
    """Share read-only weights; never download models during a session."""
    path = Path(os.environ.get("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15"))
    if not path.is_dir():
        raise ValueError("Set VOSK_MODEL_PATH to an extracted English Vosk model directory")
    return Model(str(path))


class VoskRecognizer:
    """Keep incremental decoder state private to a session."""

    def __init__(self):
        """Load shared weights and create a session decoder."""
        self.recognizer = KaldiRecognizer(english_model(), 16000)

    def _decode(self, audio):
        if audio is None:
            return self.recognizer.FinalResult()
        if self.recognizer.AcceptWaveform(audio):
            return self.recognizer.Result()
        return "{}"

    async def accept(self, audio: bytes) -> list[str]:
        """Return an endpoint result if Vosk finalized one."""
        result = await run_inference(self._decode, audio)
        return [json.loads(result).get("text", "")]

    async def flush(self) -> list[str]:
        """Finalize pending words and retain the decoder for the next press."""
        result = await run_inference(self._decode, None)
        return [json.loads(result).get("text", "")]

    async def close(self):
        """Release session decoder state without emitting pending words."""
        self.recognizer = None
