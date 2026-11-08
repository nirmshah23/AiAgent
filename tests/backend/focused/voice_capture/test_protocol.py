"""Protocol tests isolate database writes; these are not PostgreSQL integration tests."""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "apps" / "backend"))
from voice_api import main  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    """Run the real protocol handler with an isolated metadata sink."""
    save = Mock()
    monkeypatch.setattr(main, "make_engine", Mock(return_value=Mock()))
    monkeypatch.setattr(main, "save_session", save)
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:4200")
    with TestClient(main.app) as api:
        yield api, save


def test_held_turn_counts_audio_and_completes_metadata(client):
    """Accept multiple turns and persist their combined byte count."""
    api, save = client
    with api.websocket_connect("/api/v1/audio", headers={"origin": "http://localhost:4200"}) as ws:
        assert ws.receive_json()["type"] == "ready"
        for _ in range(2):
            ws.send_text("start")
            assert ws.receive_json() == {"type": "listening"}
            ws.send_bytes(b"\x00\x00" * 128)
            ws.send_text("stop")
            assert ws.receive_json()["type"] == "paused"
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}
        ws.send_text("end")
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1000
    assert save.call_args.args[3:] == (512, "completed")


@pytest.mark.parametrize("payload", [b"\x00\x00", "stop", "unknown"])
def test_rejects_audio_or_invalid_commands_outside_turn(client, payload):
    """Do not accept audio until a start command establishes a turn."""
    api, _ = client
    with api.websocket_connect("/api/v1/audio", headers={"origin": "http://localhost:4200"}) as ws:
        ws.receive_json()
        if isinstance(payload, bytes):
            ws.send_bytes(payload)
        else:
            ws.send_text(payload)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1008


@pytest.mark.parametrize("payload", [b"", b"x", bytes(16386)])
def test_rejects_invalid_pcm_frames(client, payload):
    """Reject empty, odd-length, and oversized payloads."""
    api, _ = client
    with api.websocket_connect("/api/v1/audio", headers={"origin": "http://localhost:4200"}) as ws:
        ws.receive_json()
        ws.send_text("start")
        ws.receive_json()
        ws.send_bytes(payload)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1008


def test_rejects_unconfigured_origin_without_persistence(client):
    """Reject a different browser origin before allocating a session."""
    api, save = client
    with pytest.raises(WebSocketDisconnect):
        with api.websocket_connect("/api/v1/audio", headers={"origin": "https://other.example"}):
            pass
    save.assert_not_called()
