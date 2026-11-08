"""Real CPU audio analysis checks; no external services or database required."""

import asyncio
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps" / "backend"))
from voice_api.audio_pipeline import AudioPipeline  # noqa: E402


def test_speech_and_release_produce_turn_events_and_cleanup():
    """Run bundled speech through Silero and Smart Turn without transcripts."""

    async def scenario():
        events = []

        async def notify(event):
            events.append(event["type"])

        pipeline = await asyncio.to_thread(AudioPipeline, notify)
        await pipeline.start()
        try:
            with wave.open(str(ROOT / "scripts/provider-watch/assets/speech-16k.wav")) as audio:
                assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (
                    16000,
                    1,
                    2,
                )
                while data := audio.readframes(320):
                    await pipeline.feed(data)
                    await asyncio.sleep(0.02)
            await pipeline.pause()
            await asyncio.wait_for(pipeline.silence, timeout=10)
            assert "speech_started" in events
            assert "turn_ended" in events
            assert events.index("speech_started") < events.index("turn_ended")
        finally:
            await pipeline.close()
        assert pipeline.running.done()
        assert pipeline.silence is None
        assert pipeline.analyzer._executor is None

    asyncio.run(scenario())


@pytest.mark.parametrize("value", ["true", " y ", "ON"])
def test_rejects_raw_audio_debug_logging(monkeypatch, value):
    """Deployment settings cannot enable Pipecat's audio file logger."""
    monkeypatch.setenv("PIPECAT_SMART_TURN_LOG_DATA", value)
    with pytest.raises(ValueError, match="audio logging is disabled"):
        AudioPipeline(None)
