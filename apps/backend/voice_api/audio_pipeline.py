"""Per-session Pipecat audio analysis with bounded, acknowledged ingestion."""

import asyncio

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import InputAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMUserAggregator,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.utils.env import env_truthy
from pipecat.workers.runner import WorkerRunner


class AudioSink(FrameProcessor):
    """Acknowledge consumption so transport cannot queue unbounded audio."""

    def __init__(self):
        """Create the consumption signal."""
        super().__init__()
        self.consumed = asyncio.Event()
        self.expected_id = None

    async def process_frame(self, frame, direction):
        """Forward frames and acknowledge consumed audio."""
        await super().process_frame(frame, direction)
        if (
            direction == FrameDirection.DOWNSTREAM
            and isinstance(frame, InputAudioRawFrame)
            and frame.id == self.expected_id
        ):
            self.consumed.set()
        await self.push_frame(frame, direction)


class AudioPipeline:
    """Own CPU analyzers, pipeline tasks, and silence after microphone release."""

    def __init__(self, notify):
        """Construct private CPU analyzers and register turn events."""
        # Raw-audio debug logging must never be enabled by deployment environment.
        if env_truthy("PIPECAT_SMART_TURN_LOG_DATA"):
            raise ValueError("Smart Turn audio logging is disabled for this application")
        self.analyzer = LocalSmartTurnAnalyzerV3(cpu_count=1)
        user = LLMUserAggregator(
            LLMContext(),
            params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
                user_turn_strategies=UserTurnStrategies(
                    stop=[
                        TurnAnalyzerUserTurnStopStrategy(
                            turn_analyzer=self.analyzer,
                            wait_for_transcript=False,
                        ),
                    ]
                ),
            ),
        )

        @user.event_handler("on_user_turn_started")
        async def started(*_):
            await notify({"type": "speech_started"})

        @user.event_handler("on_user_turn_stopped")
        async def stopped(*_):
            await notify({"type": "turn_ended"})

        self.sink = AudioSink()
        self.worker = PipelineWorker(
            Pipeline([user, self.sink]),
            params=PipelineParams(audio_in_sample_rate=16000, audio_out_sample_rate=16000),
            idle_timeout_secs=None,
            enable_rtvi=False,
        )
        self.running = None
        self.silence = None
        self.lock = asyncio.Lock()

    async def start(self):
        """Launch the Pipecat worker."""
        self.runner = WorkerRunner(handle_sigint=False)
        await self.runner.add_workers(self.worker)
        self.running = asyncio.create_task(self.runner.run())

    async def feed(self, data):
        """Wait for downstream consumption of one PCM frame."""
        async with self.lock:
            if self.running.done():
                await self.running
                raise RuntimeError("Audio pipeline stopped")
            self.sink.consumed.clear()
            frame = InputAudioRawFrame(data, 16000, 1)
            self.sink.expected_id = frame.id
            await self.worker.queue_frame(frame)
            await asyncio.wait_for(self.sink.consumed.wait(), timeout=10)

    async def resume(self):
        """Cancel synthetic silence before accepting microphone audio."""
        await self._stop_silence()

    async def pause(self):
        """Supply bounded silence after microphone release."""

        async def silence_tail():
            # Real-time silence lets Smart Turn's incomplete-turn fallback run
            # after capture stops, without keeping the microphone open.
            for _ in range(175):
                await self.feed(bytes(640))
                await asyncio.sleep(0.02)

        self.silence = asyncio.create_task(silence_tail())

    async def _stop_silence(self):
        if self.silence:
            self.silence.cancel()
            await asyncio.gather(self.silence, return_exceptions=True)
            self.silence = None

    async def close(self):
        """Cancel analysis and release all session tasks."""
        await self._stop_silence()
        if self.running:
            await self.worker.cancel()
            await asyncio.gather(self.running, return_exceptions=True)
