# Voice capture application

## Implemented scope

`apps/frontend` is a standalone Angular 21.2.25 application with Angular Material 21.2.14. `apps/backend` is a FastAPI application. One PostgreSQL database, `voice`, owns all application data; there is no tenancy or authentication. These applications do not modify the imported Pipecat library.

The browser connects before requesting microphone access. Holding Space requests mono microphone audio, creates a 16 kHz Web Audio `AudioContext`, and uses an AudioWorklet to encode signed 16-bit little-endian PCM. Releasing Space stops tracks, disconnects nodes, closes the context, and prevents queued worklet messages from being transmitted. Key repeat is ignored. Blur, hidden documents, page exit, microphone removal, and session termination also stop capture. Permission prompts may outlast a press; audio from a late permission result is stopped without transmission. Space on interactive controls retains normal keyboard behavior; move focus outside a button to talk.

The backend validates frames and runs a per-connection Pipecat pipeline using Silero VAD and `LocalSmartTurnAnalyzerV3` on CPU. It does **not** run speech recognition, an LLM, synthesis, or playback yet. No audio or transcripts are persisted. Only the session UUID, start/end timestamps, completion status, and received byte count are stored after each connection ends. Process crashes can lose this final metadata; active sessions are not durable. No historical session browsing API is provided.

## Local Windows development

Use Node 24, Python 3.12, and PostgreSQL 17. From the repository root:

```powershell
uv venv apps/backend/.venv --python 3.12
uv pip install --python apps/backend/.venv/Scripts/python.exe -r apps/backend/requirements.txt
# This shallow import has a non-version Git tag; use a local build version.
$env:SETUPTOOLS_SCM_PRETEND_VERSION = '1.3.0.dev0'
uv pip install --python apps/backend/.venv/Scripts/python.exe -e .
$env:DATABASE_URL = 'postgresql+psycopg://voice:YOUR_PASSWORD@localhost:5432/voice'
$env:ALLOWED_ORIGINS = 'http://localhost:4200'
Set-Location apps/backend
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn voice_api.main:app --host 127.0.0.1 --port 8000 --ws-max-size 16384
```

Provision that dedicated database and role before migrating. Check the effective `DATABASE_URL`; Alembic prints the target with the password hidden. Migration `0001` creates only `voice_sessions` in the single application database. Alembic owns schema changes; application startup never creates tables. Downgrading removes session metadata and is destructive.

In another terminal:

```powershell
Set-Location apps/frontend
npm ci
npm start
```

Open `http://localhost:4200`. The development server proxies `/api` HTTP and WebSocket requests to port 8000. The browser always uses its own origin; no service URL is embedded in the client.

## Docker Compose

Docker Desktop must be running with the Linux engine on Windows. On Linux, use Docker Engine with the Compose plugin. From the root:

```powershell
Copy-Item .env.example .env
# Set a random URL-safe POSTGRES_PASSWORD in .env before starting.
docker compose up --build -d
docker compose logs api migrate
docker compose down
```

On Linux use `cp .env.example .env` instead of `Copy-Item`. Open `http://localhost:8080`. PostgreSQL has no published port. A named volume preserves metadata. The migration service waits for database readiness; API startup waits for migrations and the frontend waits for API readiness. Nginx serves only compiled frontend assets and proxies `/api`. Source files and database data are not static assets.

This configuration binds only to loopback and provides no authentication. Remote deployment requires an HTTPS reverse proxy, a suitable network exposure policy, and `ALLOWED_ORIGINS` set to the exact public origin. Microphone access requires HTTPS except for localhost. Do not expose the development server publicly. Silero and Smart Turn use bundled ONNX weights and CPU inference. No accelerator or GPU passthrough is configured. The API image installs the repository Pipecat package, so its build context is the repository root. The local build version `1.3.0.dev0` is packaging metadata, not an upstream release claim.

The pinned Angular skill versions currently produce development dependency audit findings (21 total: 16 moderate and 5 high at initial verification); `npm audit --omit=dev` reports zero. Framework versions have been retained as required by the project skills. Review the development tooling advisories before exposing or upgrading that tooling.

## API and WebSocket contract

FastAPI publishes HTTP OpenAPI at `/openapi.json` and interactive docs at `/docs` on backend port 8000 in local development. `GET /api/v1/health` checks database connectivity and returns `{"status":"ok"}`. It returns an error when the database is unavailable. The frontend currently uses only WebSockets, which OpenAPI does not describe.

`/api/v1/audio` accepts WebSockets only from configured `ALLOWED_ORIGINS` (comma separated). Protocol:

| Direction | Message | Meaning |
| --- | --- | --- |
| Server | `{"type":"ready","session_id":"UUID"}` | Session ready |
| Client | text `start` | Begin a held-key turn |
| Server | `{"type":"listening"}` | Start accepted |
| Client | binary PCM | Mono 16 kHz signed PCM16 LE; no WAV header |
| Client | text `stop` | End turn; no further binary frames until start |
| Server | `{"type":"paused","audio_bytes":N}` | Cumulative session bytes accepted |
| Server | `{"type":"speech_started"}` | Silero detected speech |
| Server | `{"type":"turn_ended"}` | Conversational turn ended (Smart Turn or safety timeout) |
| Client | text `ping` | Keep idle session alive (every 20 seconds) |
| Server | `{"type":"pong"}` | Keepalive response |
| Client | text `end` | Complete session and close |

Frames must be nonempty, even length, and at most 16 KiB. Unexpected commands, duplicate starts/stops, and audio outside a turn close with 1008. Audio exceeding 64 MiB per session closes with 1009. Sessions expire after 30 minutes or 60 seconds without messages. The browser terminates a session when its outbound buffer exceeds 64 KiB instead of accumulating stale speech. Ended sessions require an explicit new start. Payloads are not logged or echoed. The worklet normally emits 128-sample frames; pipeline ingestion is acknowledged before accepting another frame. Latency benchmarks remain future work.


## Audio preprocessing and endpointing

Capture requests browser `echoCancellation`, `noiseSuppression`, and `autoGainControl` for acoustic echo removal, noise reduction, and automatic level normalization. These are best-effort browser constraints, not a guarantee that a particular device implements them. The microphone is never monitored through local speakers: the worklet output is silence. Actual acoustic feedback and double-talk acceptance require physical microphone/speaker testing once response playback exists; headphones reduce acoustic coupling.

Web Audio converts the device stream to a mono 16 kHz context; the worklet clamps float samples to [-1, 1] and encodes PCM16 little-endian. This is the sole transport format, avoiding lossy codec latency. WAV, MP3, Opus, and other encoded payloads are unsupported: callers must decode/resample before sending. PCM magnitude alone cannot distinguish a mislabelled codec, so clients must obey the contract. Automatic gain control is streaming normalization, not offline peak or LUFS normalization.

Pipecat owns asynchronous processing, interruption frames, and cleanup. Silero uses its default thresholds and a 0.2-second stop interval. Smart Turn uses its bundled v3.2 CPU model with one inference thread and `wait_for_transcript=False` because STT is not yet connected. Model construction runs off the event loop. Space remains the capture gate: while held, silence is available for natural endpointing. On release, up to 3.5 seconds of paced synthetic silence lets Smart Turn finish an incomplete turn without reopening the microphone; a new press cancels that tail. Silence is excluded from received byte metadata. A disconnected session cancels the pipeline and its analyzer resources. No audio is persisted; enabling `PIPECAT_SMART_TURN_LOG_DATA` is rejected.

The client currently ignores the additive speech/turn events. They do not generate a spoken response. Browser AEC/noise reduction quality, speech endpoint accuracy, concurrency, and Intel device acceleration require separate acceptance measurements. No GPU/NPU capability or latency target is claimed.
