"""Provider-neutral PCM recognition contract and Pipecat frame adapter."""

import asyncio
import os
from dataclasses import dataclass
from typing import Protocol

from pipecat.frames.frames import DataFrame, InputAudioRawFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601


class Recognizer(Protocol):
    """Consume ordered mono 16 kHz PCM16; return finalized text only."""

    async def accept(self, audio: bytes) -> list[str]:
        """Consume PCM and return any completed segments."""
        ...

    async def flush(self) -> list[str]:
        """Finalize pending speech at the capture boundary."""
        ...

    async def close(self) -> None:
        """Discard pending speech and release session resources."""
        ...


async def run_inference(function, *args):
    """Keep native work owned until it finishes, even when its caller is cancelled."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task, return_exceptions=True)
        raise


def create_recognizer() -> Recognizer:
    """Select a local provider without importing unused inference dependencies."""
    provider = os.getenv("STT_PROVIDER", "parakeet").strip().lower()
    if provider == "vosk":
        from .vosk_stt import VoskRecognizer

        return VoskRecognizer()
    if provider == "parakeet":
        from .parakeet_stt import ParakeetRecognizer

        return ParakeetRecognizer()
    raise ValueError("STT_PROVIDER must be parakeet or vosk")


@dataclass
class FlushRecognitionFrame(DataFrame):
    """Finalize pending words at a push-to-talk boundary."""


class LocalSTT(FrameProcessor):
    """Adapt interchangeable recognizers to the existing streaming pipeline."""

    def __init__(self, recognizer: Recognizer | None = None):
        """Construct on the pipeline's model-loading worker thread."""
        super().__init__()
        self.recognizer = recognizer if recognizer is not None else create_recognizer()
        self.record_transcript = None

    async def process_frame(self, frame, direction):
        """Emit final text before acknowledging its audio or flush boundary."""
        await super().process_frame(frame, direction)
        texts = []
        if direction == FrameDirection.DOWNSTREAM:
            if isinstance(frame, InputAudioRawFrame):
                if frame.sample_rate != 16000 or frame.num_channels != 1 or len(frame.audio) % 2:
                    raise ValueError("STT requires mono 16 kHz PCM16")
                texts = await self.recognizer.accept(frame.audio)
            elif isinstance(frame, FlushRecognitionFrame):
                texts = await self.recognizer.flush()
        for text in texts:
            if text := text.strip():
                if self.record_transcript:
                    await self.record_transcript("recognition", text)
                await self.push_frame(
                    TranscriptionFrame(
                        text, "user", time_now_iso8601(), language=Language.EN, finalized=True
                    )
                )
        await self.push_frame(frame, direction)

    async def cleanup(self):
        """Discard pending recognition without transcribing on disconnect."""
        try:
            await self.recognizer.close()
        finally:
            await super().cleanup()
