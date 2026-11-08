"""Operator policy API contract checks against an isolated application database."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "apps/backend"))
from voice_api.database import Base  # noqa: E402
from voice_api.dialog.config import DialogConfig  # noqa: E402
from voice_api.dialog.store import DialogPolicy  # noqa: E402
from voice_api.main import app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        db.add(DialogPolicy(id=1, configuration=DialogConfig().model_dump(mode="json")))
    monkeypatch.setattr(app.state, "engine", engine, raising=False)
    monkeypatch.setattr(app.state, "dialog", None, raising=False)
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:4200")
    # No lifespan: inference and deployment database are deliberately excluded.
    yield TestClient(app, headers={"Origin": "http://localhost:4200"})
    engine.dispose()


def test_policy_crud_and_stale_revision_preserve_saved_data(client):
    snapshot = client.get("/api/v1/dialog-policy").json()
    assert "Intent" in snapshot["json_schema"]["$defs"]
    payload = {key: snapshot[key] for key in ("revision", "configuration")}
    payload["configuration"]["intents"].append(
        {"name": "LOOKUP", "type": "Business", "description": "Lookup", "responses": ["Found."]}
    )
    saved = client.put("/api/v1/dialog-policy", json=payload)
    assert saved.status_code == 200
    assert saved.json()["revision"] != snapshot["revision"]
    assert client.put("/api/v1/dialog-policy", json=payload).status_code == 409
    payload = {key: saved.json()[key] for key in ("revision", "configuration")}
    payload["configuration"]["intents"][-1]["description"] = "Changed description"
    saved = client.put("/api/v1/dialog-policy", json=payload).json()
    assert saved["configuration"]["intents"][-1]["description"] == "Changed description"
    payload = {key: saved[key] for key in ("revision", "configuration")}
    payload["configuration"]["intents"].pop()
    assert client.put("/api/v1/dialog-policy", json=payload).status_code == 200
    assert len(client.get("/api/v1/dialog-policy").json()["configuration"]["intents"]) == 2


@pytest.mark.parametrize("invalid", ["reserved", "regex", "reference", "cycle", "duplicate"])
def test_invalid_policy_is_rejected_without_writing(client, invalid):
    original = client.get("/api/v1/dialog-policy").json()
    payload = {key: original[key] for key in ("revision", "configuration")}
    intents = payload["configuration"]["intents"]
    if invalid == "reserved":
        intents.pop()
    elif invalid == "regex":
        intents[1]["fields"] = [{"name": "id", "regex": "["}]
    elif invalid == "reference":
        intents[1]["next_intent"] = "UNKNOWN"
    elif invalid == "cycle":
        intents[1]["next_intent"] = "END"
    else:
        intents.append(intents[1])
    assert client.put("/api/v1/dialog-policy", json=payload).status_code == 422
    assert client.get("/api/v1/dialog-policy").json()["revision"] == original["revision"]


@pytest.mark.parametrize("origin", ["https://untrusted.example", "null", ""])
def test_policy_write_rejects_unapproved_origins(client, origin):
    snapshot = client.get("/api/v1/dialog-policy").json()
    payload = {key: snapshot[key] for key in ("revision", "configuration")}
    assert (
        client.put("/api/v1/dialog-policy", json=payload, headers={"Origin": origin}).status_code
        == 403
    )
