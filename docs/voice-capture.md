# Voice capture application

## Implemented scope

`apps/frontend` is a standalone Angular 21.2.25 application with Angular Material 21.2.14. `apps/backend` is a FastAPI application. One PostgreSQL database, `voice`, owns all application data; there is no tenancy or authentication. These applications do not modify the imported Pipecat library.

The separate [dialog engine](dialog-orchestration.md) now has database-backed configuration and Laya/Regex/GLiNER adapters. It is connected to completed caller turns; generated reply audio uses the existing binary WebSocket playback path. Migration `0002` adds shared dialog policy alongside session metadata; capture stores no caller transcripts.

The browser connects before requesting microphone access. Holding Space requests mono microphone audio, creates a 16 kHz Web Audio `AudioContext`, and uses an AudioWorklet to encode signed 16-bit little-endian PCM. Releasing Space stops tracks, disconnects nodes, closes the context, and prevents queued worklet messages from being transmitted. Key repeat is ignored. Blur, hidden documents, page exit, microphone removal, and session termination also stop capture. Permission prompts may outlast a press; audio from a late permission result is stopped without transmission. Space on interactive controls retains normal keyboard behavior; move focus outside a button to talk.

The backend validates frames and runs a per-connection Pipecat pipeline using Silero VAD and `LocalSmartTurnAnalyzerV3` on CPU. Vosk performs local English speech recognition on CPU before the user aggregator. Local Piper synthesis and browser playback deliver the database-configured welcome and generated dialog replies. Laya classifies intent and GLiNER extracts fields on CPU (FP32 by default; optional INT8); no free-form generative LLM is used. Optional latest-session debug capture stores private WAV audio and transcript events on disk (enabled in the local Compose demo; see below). Only the session UUID, start/end timestamps, completion status, and received byte count are stored after each connection ends. Process crashes can lose this final metadata; active sessions are not durable. No historical session browsing API is provided.

## English speech recognition

Install the pinned backend requirements and download the [small US English model](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip). Extract it into the repository's ignored `models/` directory so `models/vosk-model-small-en-us-0.15/am/final.mdl` exists. This is a CPU baseline, not a measured best model for the target hardware. Only an English model is supported; language follows the installed weights rather than automatic detection.

Set `VOSK_MODEL_PATH` to the absolute extracted model directory for native development. Compose mounts `./models` read-only at `/models` and sets the corresponding container path. Download/extraction is a prerequisite on both Windows and Linux; sessions never download weights. A missing or invalid model prevents pipeline creation. Weights are shared within the process, with a separate recognizer per connection. Restart the API after changing weights.

The Pipecat processor sends preprocessed mono 16 kHz PCM16 to Vosk in order, decodes off the event loop, and emits nonempty final `TranscriptionFrame` objects to the existing user aggregator. Vosk endpoint results are emitted while streaming; releasing Space explicitly finalizes pending words before synthetic silence. Transcripts are internal only: they are not logged or sent to the browser; optional debug capture records finalized recognition results and completed caller turns. Disconnect cancels pending speech rather than delivering a final transcript. Browser controls and WebSocket messages are unchanged. No transcript UI is implemented; complete turn text stays internal and drives dialog responses.

## Piper speech synthesis

The backend uses pinned `piper-tts==1.3.0` and Pipecat's `PiperTTSService` on CPU. Prepare the English voice before starting the API, from the repository root after installing backend requirements:

```powershell
New-Item -ItemType Directory -Force models/piper | Out-Null
apps/backend/.venv/Scripts/python.exe -m piper.download_voices --download-dir models/piper en_US-lessac-medium
```

On Linux, use `mkdir -p models/piper` and `apps/backend/.venv/bin/python` instead. Both `en_US-lessac-medium.onnx` and its `.onnx.json` configuration must exist. Set `PIPER_MODEL_PATH` to the absolute ONNX path for native startup; Compose uses `/models/piper/en_US-lessac-medium.onnx` in the existing read-only model mount. Sessions reject missing weights or non-English voice configurations and never download Piper weights. Restart the API after changing model files. Set `PIPER_LENGTH_SCALE` (default `1.3`) to a finite positive duration multiplier; larger values slow speech, and `1.0` uses normal duration. This explicitly overrides the voice JSON length scale. Compose reads it from `.env`; native PowerShell can use `$env:PIPER_LENGTH_SCALE = "1.3"`. Restart the API after changing it. The engine is GPL-3.0; inspect the chosen voice's model card for its separate license before distribution. See the [maintained Piper project](https://github.com/OHF-Voice/piper1-gpl).

Starting a browser session unlocks a separate playback AudioContext. Once ready, the client requests the database-configured spoken welcome, without opening the microphone. `AudioPipeline.speak(text)` queues interruptible `TTSSpeakFrame` requests (maximum 2000 characters) through `DialogVoiceBridge`. The speech function waits for a downstream PCM completion barrier so replies remain ordered and terminal workflows drain their final speech. No caller text is accepted through the browser. Piper audio is resampled by Pipecat to mono 16 kHz PCM16 and sent in paced chunks of at most 100 ms. The client schedules playback with a 15-second maximum queue and reports suspended/unavailable playback. Holding Space clears playback immediately, suppresses stale incoming audio until the server acknowledges the new capture turn, and interrupts server synthesis when capture starts. Session termination stops sources and closes both audio contexts. Speech errors produce a generic status without exposing response text. Upstream Piper/TTS debug logs that contain synthesized text are disabled.

The dialog runtime is shared, while each session owns a Piper instance; memory use and concurrent-session throughput remain unmeasured. CPU is the only configured device; no Intel GPU/OpenVINO acceleration is claimed. Windows native synthesis, PCM delivery, interruption gating, safe inference-failure notification and worker cleanup were smoke-tested. The Linux API image built successfully and passed a CPU Piper synthesis/bounded-PCM/interruption/cleanup smoke check with read-only mounted weights. Chromium playback scheduling, interruption and context cleanup were checked against a simulated WebSocket peer. Chromium also passed a voice-to-generated-reply flow against the live Compose stack with real CPU models and recorded microphone input; PostgreSQL recorded a completed session with nonzero received bytes. Physical sound quality, echo/double-talk, domain extraction accuracy and latency/concurrency remain separate checks.

## Local Windows development

Use Node 24, Python 3.12, and PostgreSQL 17. From the repository root:

```powershell
uv venv apps/backend/.venv --python 3.12
uv pip install --python apps/backend/.venv/Scripts/python.exe -r apps/backend/requirements-dialog.txt
# This shallow import has a non-version Git tag; use a local build version.
$env:SETUPTOOLS_SCM_PRETEND_VERSION = '1.3.0.dev0'
uv pip install --python apps/backend/.venv/Scripts/python.exe -e .
$env:DATABASE_URL = 'postgresql+psycopg://voice:YOUR_PASSWORD@localhost:5432/voice'
$env:ALLOWED_ORIGINS = 'http://localhost:4200'
$env:VOSK_MODEL_PATH = (Resolve-Path models/vosk-model-small-en-us-0.15).Path
$env:PIPER_MODEL_PATH = (Resolve-Path models/piper/en_US-lessac-medium.onnx).Path
$env:LAYA_MODEL_PATH = (Resolve-Path models/laya).Path
$env:GLINER_MODEL_PATH = (Resolve-Path models/gliner-small-v2.1).Path
$env:DIALOG_API_MODE = 'simulated'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
Set-Location apps/backend
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn voice_api.main:app --host 127.0.0.1 --port 8000 --ws-max-size 16384
```

Prepare the [dialog models](dialog-orchestration.md#local-inference-adapters), Vosk model and Piper voice before these startup commands. Provision that dedicated database and role before migrating. Check the effective `DATABASE_URL`; Alembic prints the target with the password hidden. Migration `0001` creates `voice_sessions`; `0002` creates and seeds `dialog_policy` in the same application database; `0003` adds the Claim Status seed while preserving operator customization. Alembic owns schema changes; application startup never creates tables. Downgrading `0002` deletes configured dialog policy; downgrading `0001` deletes session metadata.

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
| Client | text `welcome` | Request the configured welcome once before capture starts |
| Server | binary PCM | Synthesized mono 16 kHz PCM16 LE, no header, at most 3200 bytes per message |
| Server | `{"type":"speech_error"}` | Speech output failed; no internal error details |
| Client | text `start` | Begin a held-key turn |
| Server | `{"type":"listening"}` | Start accepted |
| Client | binary PCM | Mono 16 kHz signed PCM16 LE; no WAV header |
| Client | text `stop` | End turn; no further binary frames until start |
| Server | `{"type":"paused","audio_bytes":N}` | Cumulative session bytes accepted |
| Server | `{"type":"speech_started"}` | Silero detected speech |
| Server | `{"type":"turn_ended"}` | Conversational turn ended (Smart Turn or safety timeout) |
| Client | text `ping` | Keep idle session alive (every 20 seconds) |
| Server | `{"type":"pong"}` | Keepalive response |
| Server | `{"type":"dialog_ended","status":"ended"}` | Terminal workflow status after speech delivery; browser drains playback then ends the session |
| Client | text `end` | Complete session and close |

Client audio frames must be nonempty, even length, and at most 16 KiB. Unexpected commands, duplicate starts/stops, and audio outside a turn close with 1008. Audio exceeding 64 MiB per session closes with 1009. Sessions expire after 30 minutes or 60 seconds without messages. The browser terminates a session when its outbound buffer exceeds 64 KiB instead of accumulating stale speech. Ended sessions require an explicit new start. Payloads are not logged or echoed. The worklet normally emits 128-sample frames; pipeline ingestion is acknowledged before accepting another frame. Latency benchmarks remain future work.


## Audio preprocessing and endpointing

Capture requests browser `echoCancellation`, `noiseSuppression`, and `autoGainControl` for acoustic echo removal, noise reduction, and automatic level normalization. These are best-effort browser constraints, not a guarantee that a particular device implements them. The microphone is never monitored through local speakers: the worklet output is silence. Actual acoustic feedback and double-talk acceptance require physical microphone/speaker testing; headphones reduce acoustic coupling.

Web Audio converts the device stream to a mono 16 kHz context; the worklet clamps float samples to [-1, 1] and encodes PCM16 little-endian. This is the sole transport format, avoiding lossy codec latency. WAV, MP3, Opus, and other encoded payloads are unsupported: callers must decode/resample before sending. PCM magnitude alone cannot distinguish a mislabelled codec, so clients must obey the contract. Automatic gain control is streaming normalization, not offline peak or LUFS normalization.

Pipecat owns asynchronous processing, interruption frames, and cleanup. Silero uses its default thresholds and a 0.2-second stop interval. Smart Turn uses its bundled v3.2 CPU model with one inference thread and `wait_for_transcript=True` so the completed turn includes finalized Vosk text before dialog processing. Model construction runs off the event loop. Space remains the capture gate: while held, silence is available for natural endpointing. On release, up to 3.5 seconds of paced synthetic silence lets Smart Turn finish an incomplete turn without reopening the microphone; a new press cancels that tail. Silence is excluded from received byte metadata. A disconnected session cancels the pipeline and its analyzer resources. Debug capture excludes this synthetic silence; enabling `PIPECAT_SMART_TURN_LOG_DATA` is rejected.

The client clears queued playback on speech-start events and ignores turn-end events. Completed turns invoke the dialog engine and synthesize its generated response texts. Browser AEC/noise reduction quality, speech endpoint accuracy, concurrency, and Intel device acceleration require separate acceptance measurements. No GPU/NPU capability or latency target is claimed.

## Latest-session debug capture

For local testing, Compose enables `SESSION_DEBUG_ENABLED=true` and mounts the repository's ignored `session-debug/` directory at `/session-debug`. Recreate the API after changing configuration with `docker compose up -d --build api`. Native execution defaults to disabled; set `SESSION_DEBUG_ENABLED=true` and optionally `SESSION_DEBUG_DIR` (default `session-debug`, relative to the backend working directory).

Open `session-debug/input.wav` in a media player and `session-debug/transcripts.jsonl` in a text editor. `session.json` identifies the session and final connection status. WAV is mono 16 kHz PCM16 containing accepted microphone chunks, without generated replies or synthetic endpoint silence. Pauses between capture presses are concatenated. Transcript JSON lines contain UTC timestamps, audio offsets in seconds, and `recognition` (final Vosk segments) or `caller_turn` (completed text reaching the dialog handler) events. Empty recognition produces no transcript event; compare the WAV when speech was missed. Offsets identify processed audio boundaries, not word alignment. Pending recognition is still cancelled on disconnect, so an abrupt disconnect can leave audio without final text.

Files are flushed during capture and retained after disconnect for inspection. The next accepted session replaces only these three files, even if its pipeline startup subsequently fails. If sessions overlap, only the newest session is recorded; older sessions continue normally and cannot append to or close its files. Use one API worker/process for this local debug feature; cross-process rotation is unsupported. Existing transport limits bound input audio to 64 MiB and 30 minutes per session. Copy files elsewhere before starting another session if you want to retain them.

Set `SESSION_DEBUG_ENABLED=false` to stop new captures. Existing artifacts remain until manually removed or replaced by the next enabled session. Files are excluded from Git and Docker build context and are not served by HTTP or stored in PostgreSQL. Disk write failures fail the session rather than silently losing diagnostics. This is a testing facility, not durable recording or historical session storage.
