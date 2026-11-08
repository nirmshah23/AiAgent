"""Local English streaming recognition of preprocessed transport PCM."""

import asyncio
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from vosk import KaldiRecognizer, Model

from pipecat.frames.frames import DataFrame, InputAudioRawFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601


@dataclass
class FlushRecognitionFrame(DataFrame):
    """Finalize pending words at the push-to-talk boundary."""


@lru_cache(maxsize=1)
def english_model():
    """Share read-only weights; never download models during a session."""
    path = Path(os.environ.get("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15"))
    if not path.is_dir():
        raise ValueError("Set VOSK_MODEL_PATH to an extracted English Vosk model directory")
    return Model(str(path))


class VoskSTT(FrameProcessor):
    """Keep decoder state private to a session and decoding off the event loop."""

    def __init__(self):
        """Construct on the pipeline's model-loading worker thread."""
        super().__init__()
        self.recognizer = KaldiRecognizer(english_model(), 16000)

    def _decode(self, audio):
        if audio is None:
            return self.recognizer.FinalResult()
        if self.recognizer.AcceptWaveform(audio):
            return self.recognizer.Result()
        return None

    async def process_frame(self, frame, direction):
        """Emit final text internally, then preserve audio and control ordering."""
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM and isinstance(
            frame, (InputAudioRawFrame, FlushRecognitionFrame)
        ):
            audio = frame.audio if isinstance(frame, InputAudioRawFrame) else None
            result = await asyncio.to_thread(self._decode, audio)
            if result:
                text = json.loads(result).get("text", "").strip()
                if text:
                    await self.push_frame(
                        TranscriptionFrame(
                            text,
                            "user",
                            time_now_iso8601(),
                            language=Language.EN,
                            finalized=True,
                        )
                    )
        await self.push_frame(frame, direction)
