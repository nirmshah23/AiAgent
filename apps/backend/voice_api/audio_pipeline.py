"""Per-session Pipecat audio analysis with bounded, acknowledged ingestion."""

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    DataFrame,
    ErrorFrame,
    InputAudioRawFrame,
    InterruptionFrame,
    TTSAudioRawFrame,
    TTSSpeakFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMUserAggregator,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.piper.tts import PiperTTSService
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.utils.env import env_truthy
from pipecat.workers.runner import WorkerRunner

from .dialog.voice_bridge import DialogVoiceBridge
from .vosk_stt import FlushRecognitionFrame, VoskSTT

# These upstream modules include the complete speech text in debug messages.
logger.disable("pipecat.services.tts_service")
logger.disable("pipecat.services.piper.tts")


@dataclass
class SpeechCompletionFrame(DataFrame):
    """A downstream barrier after an utterance's paced PCM has been delivered."""

    completed: asyncio.Event = field(default_factory=asyncio.Event)


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
            and isinstance(frame, (InputAudioRawFrame, FlushRecognitionFrame))
            and frame.id == self.expected_id
        ):
            self.consumed.set()
        if isinstance(frame, (InputAudioRawFrame, FlushRecognitionFrame)):
            return
        await self.push_frame(frame, direction)


class AudioPipeline:
    """Own recognition, dialog tasks, interruptible Piper speech and turn analysis."""

    def __init__(self, notify):
        """Construct private CPU analyzers and register turn events."""
        # Raw-audio debug logging must never be enabled by deployment environment.
        if env_truthy("PIPECAT_SMART_TURN_LOG_DATA"):
            raise ValueError("Smart Turn audio logging is disabled for this application")
        self.notify = notify
        self.record_transcript = None
        self.bridge = None
        self.reply_task = None
        self.dialog_finished = False
        self.speech_lock = asyncio.Lock()
        self.stt = VoskSTT()
        model = Path(os.getenv("PIPER_MODEL_PATH", "models/piper/en_US-lessac-medium.onnx"))
        if not model.is_file() or not Path(str(model) + ".json").is_file():
            raise ValueError(
                "Prepare PIPER_MODEL_PATH and its .onnx.json configuration before starting"
            )
        config = json.loads(Path(str(model) + ".json").read_text(encoding="utf-8"))
        if not config.get("espeak", {}).get("voice", "").startswith("en"):
            raise ValueError("Piper requires an English voice")
        self.tts = PiperTTSService(
            settings=PiperTTSService.Settings(voice=model.stem),
            download_dir=model.parent,
            use_cuda=False,
            length_scale=float(os.getenv("PIPER_LENGTH_SCALE", "1.3")),
        )
        self.analyzer = LocalSmartTurnAnalyzerV3(cpu_count=1)
        user = LLMUserAggregator(
            LLMContext(),
            params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
                user_turn_strategies=UserTurnStrategies(
                    stop=[
                        TurnAnalyzerUserTurnStopStrategy(
                            turn_analyzer=self.analyzer,
                            wait_for_transcript=True,
                        ),
                    ]
                ),
            ),
        )

        @user.event_handler("on_user_turn_started")
        async def started(*_):
            await self._interrupt_reply()
            await notify({"type": "speech_started"})

        @user.event_handler("on_user_turn_stopped")
        async def stopped(_user, _strategy, message):
            if self.record_transcript and message.content:
                await self.record_transcript("caller_turn", message.content)
            await notify({"type": "turn_ended"})
            if self.bridge and message.content and not self.dialog_finished:
                await self._interrupt_reply()
                if not self.dialog_finished:
                    self.reply_task = asyncio.create_task(self._reply(message.content))

        self.sink = AudioSink()
        self.output = SpeechOutput(notify)

        @self.tts.event_handler("on_error")
        async def speech_failed(*_):
            self.output.muted = True
            self.output.failed = True
            await notify({"type": "speech_error"})

        self.worker = PipelineWorker(
            Pipeline([self.stt, user, self.sink, self.tts, self.output]),
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
        await self._consume(InputAudioRawFrame(data, 16000, 1))

    async def _consume(self, frame):
        """Serialize audio and explicit recognition boundaries with acknowledgements."""
        async with self.lock:
            if self.running.done():
                await self.running
                raise RuntimeError("Audio pipeline stopped")
            self.sink.consumed.clear()
            self.sink.expected_id = frame.id
            await self.worker.queue_frame(frame)
            await asyncio.wait_for(self.sink.consumed.wait(), timeout=10)

    async def resume(self):
        """Cancel synthetic silence before accepting microphone audio."""
        await self._stop_silence()
        await self._interrupt_reply()
        self.output.muted = True
        await self.worker.queue_frame(InterruptionFrame())

    def attach_dialog(self, dialog):
        """Bind this session's dialog to its own Piper speech function."""
        self.bridge = DialogVoiceBridge(dialog, self.speak)

    async def welcome(self):
        """Speak the configured welcome without blocking WebSocket receive."""
        self.reply_task = asyncio.create_task(self._welcome())

    async def _welcome(self):
        try:
            if self.bridge:
                await self.bridge.start()
            else:
                await self.speak("Welcome. Hold Space to speak, and release it when you finish.")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error("Welcome speech delivery failed ({})", type(error).__name__)
            if self.bridge:
                self.bridge.close()
                self.dialog_finished = True
            await self.notify({"type": "speech_error"})

    async def _reply(self, transcript):
        try:
            reply = await self.bridge.caller_turn(transcript)
            if reply.status in {"complete", "ended", "failed", "history_limit"}:
                self.dialog_finished = True
                self.bridge.close()
                await self.notify({"type": "dialog_ended", "status": reply.status})
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error("Dialog speech delivery failed ({})", type(error).__name__)
            self.dialog_finished = True
            self.bridge.close()
            await self.notify({"type": "speech_error"})

    async def _interrupt_reply(self):
        self.output.muted = True
        if self.reply_task:
            self.reply_task.cancel()
            await asyncio.gather(self.reply_task, return_exceptions=True)
            self.reply_task = None
            if self.bridge and self.bridge.dialog.ended and not self.dialog_finished:
                # Cancellation during a business API call has an unknown outcome.
                self.dialog_finished = True
                self.bridge.close()
                await self.notify({"type": "dialog_ended", "status": "interrupted"})

    async def speak(self, text: str):
        """Queue a bounded English speech request; usable by DialogVoiceBridge."""
        if not text.strip():
            return
        if len(text) > 2000:
            raise ValueError("Speech request exceeds 2000 characters")
        async with self.speech_lock:
            self.output.muted = False
            self.output.failed = False
            barrier = SpeechCompletionFrame()
            await self.worker.queue_frame(TTSSpeakFrame(text, append_to_context=False))
            await self.worker.queue_frame(barrier)
            await asyncio.wait_for(barrier.completed.wait(), timeout=180)
            if self.output.failed:
                raise RuntimeError("Speech synthesis failed")

    async def pause(self):
        """Supply bounded silence after microphone release."""
        await self._consume(FlushRecognitionFrame())

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
        if self.reply_task:
            self.reply_task.cancel()
            await asyncio.gather(self.reply_task, return_exceptions=True)
            self.reply_task = None
        if self.bridge:
            self.bridge.close()
        if self.running:
            await self.worker.cancel()
            await asyncio.gather(self.running, return_exceptions=True)


class SpeechOutput(FrameProcessor):
    """Send only PCM to the browser; never expose synthesized text or internal errors."""

    def __init__(self, notify):
        """Keep a private output gate for interrupted sessions."""
        super().__init__()
        self.notify = notify
        self.muted = False
        self.failed = False

    async def process_frame(self, frame, direction):
        """Forward bounded PCM frames and safe synthesis failure notifications."""
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM:
            if isinstance(frame, TTSAudioRawFrame):
                for offset in range(0, len(frame.audio), 3200):
                    if self.muted:
                        break
                    chunk = frame.audio[offset : offset + 3200]
                    await self.notify(chunk)
                    # Pace playback and keep transport buffering bounded to 100 ms chunks.
                    await asyncio.sleep(len(chunk) / 32000)
            elif isinstance(frame, ErrorFrame):
                await self.notify({"type": "speech_error"})
            elif isinstance(frame, SpeechCompletionFrame):
                frame.completed.set()
        await self.push_frame(frame, direction)
