"""HTTP health and bounded, ephemeral PCM WebSocket transport."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from anyio import CancelScope
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from .database import make_engine, save_session
from .dialog.config import DialogConfig
from .dialog.store import PolicyConflict, load_config, revision, save_config
from .session_debug import SessionDebug


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Own database and shared inference until voice sessions have stopped."""
    dialog_enabled = os.getenv("DIALOG_ENABLED", "true").strip().lower()
    if dialog_enabled not in {"true", "false"}:
        raise ValueError("DIALOG_ENABLED must be true or false")
    app.state.max_sessions = max(1, int(os.getenv("MAX_VOICE_SESSIONS", "2")))
    debug_enabled = os.getenv("SESSION_DEBUG_ENABLED", "false").strip().lower()
    if debug_enabled not in {"true", "false"}:
        raise ValueError("SESSION_DEBUG_ENABLED must be true or false")
    app.state.session_debug = (
        SessionDebug(os.getenv("SESSION_DEBUG_DIR", "session-debug"))
        if debug_enabled == "true"
        else None
    )
    app.state.engine = make_engine()
    app.state.dialog = None
    app.state.active_sessions = 0
    try:
        if dialog_enabled == "true":
            from .dialog.voice_bridge import DialogRuntime

            app.state.dialog = await run_in_threadpool(DialogRuntime, app.state.engine)
        yield
    finally:
        if app.state.dialog:
            await run_in_threadpool(app.state.dialog.close)
        app.state.engine.dispose()


app = FastAPI(title="Voice capture API", version="1.0.0", lifespan=lifespan)


class PolicySnapshot(BaseModel):
    """Versioned policy plus the authoritative schema used by the form editor."""

    configuration: DialogConfig
    revision: str
    json_schema: dict


class PolicyUpdate(BaseModel):
    """Replace a complete validated policy only if its revision still matches."""

    configuration: DialogConfig
    revision: str


@app.get("/api/v1/dialog-policy", response_model=PolicySnapshot)
def get_policy():
    """Read operator configuration, excluding deployment URLs and credentials."""
    config = load_config(app.state.engine)
    return PolicySnapshot(
        configuration=config,
        revision=revision(config),
        json_schema=DialogConfig.model_json_schema(),
    )


@app.put("/api/v1/dialog-policy", response_model=PolicySnapshot)
def update_policy(update: PolicyUpdate, request: Request):
    """Validate and atomically save the operator's policy snapshot."""
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:4200,http://localhost:8080").split(",")
    if request.headers.get("origin") not in origins:
        raise HTTPException(403, "Policy changes require an allowed browser origin")
    runtime = app.state.dialog
    if runtime:
        try:
            runtime._validate(update.configuration)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    try:
        save_config(app.state.engine, update.configuration, update.revision)
    except PolicyConflict as exc:
        raise HTTPException(409, "Configuration changed. Reload before saving again.") from exc
    return PolicySnapshot(
        configuration=update.configuration,
        revision=revision(update.configuration),
        json_schema=DialogConfig.model_json_schema(),
    )


class Health(BaseModel):
    """Database readiness response."""

    status: str


@app.get("/api/v1/health", response_model=Health)
def health():
    """Verify the configured database is reachable."""
    with app.state.engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return Health(status="ok")


@app.websocket("/api/v1/audio")
async def audio(websocket: WebSocket):
    """Receive held-key turns with optional private testing diagnostics."""
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:4200,http://localhost:8080").split(",")
    if websocket.headers.get("origin") not in origins:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    if app.state.active_sessions >= app.state.max_sessions:
        await websocket.close(code=1013, reason="Voice service busy")
        return
    app.state.active_sessions += 1
    session_id, started = uuid4(), datetime.now(UTC)
    total, active, status = 0, False, "disconnected"
    pipeline = None
    debug = app.state.session_debug
    send_lock = asyncio.Lock()
    welcomed = False

    async def notify(message):
        async with send_lock:
            async with asyncio.timeout(5):
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_json(message)

    try:
        from .audio_pipeline import AudioPipeline

        if debug:
            await run_in_threadpool(debug.begin, session_id)
        pipeline = await run_in_threadpool(AudioPipeline, notify)
        if debug:

            async def record_transcript(kind, text):
                await run_in_threadpool(debug.transcript, session_id, kind, text)

            pipeline.stt.record_transcript = record_transcript
            pipeline.record_transcript = record_transcript
        if app.state.dialog:
            dialog = await run_in_threadpool(app.state.dialog.session)
            pipeline.attach_dialog(dialog)
        await pipeline.start()
        await notify({"type": "ready", "session_id": str(session_id)})
        async with asyncio.timeout(1800):
            while True:
                message = await asyncio.wait_for(websocket.receive(), timeout=60)
                if message["type"] == "websocket.disconnect":
                    break
                data = message.get("bytes")
                if data is not None:
                    if not active or not data or len(data) > 16384 or len(data) % 2:
                        await websocket.close(code=1008, reason="Invalid audio frame")
                        break
                    total += len(data)
                    if total > 64 * 1024 * 1024:
                        await websocket.close(code=1009, reason="Session audio limit")
                        break
                    if debug:
                        await run_in_threadpool(debug.audio, session_id, data)
                    await pipeline.feed(data)
                else:
                    command = message.get("text")
                    if command == "welcome" and not welcomed and not active:
                        welcomed = True
                        await pipeline.welcome()
                    elif command == "start" and not active:
                        welcomed = True
                        await pipeline.resume()
                        active = True
                        await notify({"type": "listening"})
                    elif command == "stop" and active:
                        active = False
                        await pipeline.pause()
                        await notify({"type": "paused", "audio_bytes": total})
                    elif command == "ping":
                        await notify({"type": "pong"})
                    elif command == "end":
                        status = "completed"
                        await websocket.close(code=1000)
                        break
                    else:
                        await websocket.close(code=1008, reason="Invalid command")
                        break
    except (WebSocketDisconnect, TimeoutError):
        pass
    finally:
        with CancelScope(shield=True):
            try:
                if pipeline is not None:
                    await pipeline.close()
            finally:
                try:
                    await run_in_threadpool(
                        save_session,
                        app.state.engine,
                        session_id,
                        started,
                        total,
                        status,
                    )
                finally:
                    try:
                        if debug:
                            await run_in_threadpool(debug.finish, session_id, status)
                    finally:
                        app.state.active_sessions -= 1
