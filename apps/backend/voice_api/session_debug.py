"""Private, single-process latest-session diagnostics for local testing."""

import json
import threading
import wave
from datetime import UTC, datetime
from pathlib import Path


class SessionDebug:
    """Replace only owned files; stale sessions cannot modify the latest capture."""

    def __init__(self, directory):
        """Configure the private artifact directory and rotation lock."""
        self.directory = Path(directory)
        self.lock = threading.Lock()
        self.session_id = None
        self.wav = None
        self.stream = None

    def begin(self, session_id):
        """Replace the previous capture before accepting input."""
        with self.lock:
            self._close()
            self.session_id = None
            self.directory.mkdir(parents=True, exist_ok=True)
            for name in ("input.wav", "transcripts.jsonl", "session.json"):
                (self.directory / name).unlink(missing_ok=True)
            self.stream = (self.directory / "input.wav").open("wb")
            self.wav = wave.open(self.stream, "wb")
            self.wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            self.wav.writeframes(b"")
            self.stream.flush()
            (self.directory / "transcripts.jsonl").touch()
            self.session_id = str(session_id)
            self._metadata("active")

    def audio(self, session_id, data):
        """Append microphone PCM and flush a readable WAV header."""
        with self.lock:
            if str(session_id) == self.session_id and self.wav:
                self.wav.writeframes(data)
                self.stream.flush()

    def transcript(self, session_id, kind, text):
        """Append a timestamped recognition or completed-turn event."""
        with self.lock:
            if str(session_id) == self.session_id and self.wav:
                with (self.directory / "transcripts.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "timestamp": datetime.now(UTC).isoformat(),
                                "kind": kind,
                                "audio_offset_seconds": self.wav.getnframes() / 16000,
                                "text": text,
                            }
                        )
                        + "\n"
                    )

    def finish(self, session_id, status):
        """Finalize only the current capture and retain files for inspection."""
        with self.lock:
            if str(session_id) == self.session_id:
                try:
                    self._metadata(status)
                finally:
                    self._close()

    def _metadata(self, status):
        (self.directory / "session.json").write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "status": status,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ),
            encoding="utf-8",
        )

    def _close(self):
        if self.wav:
            self.wav.close()
            self.wav = None
            self.stream.close()
            self.stream = None
