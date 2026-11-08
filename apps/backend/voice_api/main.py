"""HTTP health and bounded, ephemeral PCM WebSocket transport."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from anyio import CancelScope
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from .database import make_engine, save_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Own the application's database engine lifecycle."""
    app.state.engine = make_engine()
    try:
        yield
    finally:
        app.state.engine.dispose()


app = FastAPI(title="Voice capture API", version="1.0.0", lifespan=lifespan)


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
    """Receive held-key turns without persisting microphone content."""
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:4200,http://localhost:8080").split(",")
    if websocket.headers.get("origin") not in origins:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    session_id, started = uuid4(), datetime.now(UTC)
    total, active, status = 0, False, "disconnected"
    pipeline = None
    send_lock = asyncio.Lock()

    async def notify(message):
        async with send_lock:
            await websocket.send_json(message)

    try:
        from .audio_pipeline import AudioPipeline

        pipeline = await run_in_threadpool(AudioPipeline, notify)
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
                    await pipeline.feed(data)
                else:
                    command = message.get("text")
                    if command == "start" and not active:
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
                await run_in_threadpool(
                    save_session,
                    app.state.engine,
                    session_id,
                    started,
                    total,
                    status,
                )
