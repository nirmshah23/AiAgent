# Voice capture application

## Implemented scope

`apps/frontend` is a standalone Angular 21.2.25 application with Angular Material 21.2.14. `apps/backend` is a FastAPI application. One PostgreSQL database, `voice`, owns all application data; there is no tenancy or authentication. These applications do not modify the imported Pipecat library.

The separate [dialog engine](dialog-orchestration.md) now has database-backed configuration and Laya/Regex/GLiNER adapters. It is connected to completed caller turns; generated reply audio uses the existing binary WebSocket playback path. Migration `0002` adds shared dialog policy alongside session metadata; capture stores no caller transcripts.

The browser connects before requesting microphone access. Holding Space requests mono microphone audio, creates a 16 kHz Web Audio `AudioContext`, and uses an AudioWorklet to encode signed 16-bit little-endian PCM. Releasing Space stops tracks, disconnects nodes, closes the context, and prevents queued worklet messages from being transmitted. Key repeat is ignored. Blur, hidden documents, page exit, microphone removal, and session termination also stop capture. Permission prompts may outlast a press; audio from a late permission result is stopped without transmission. Space on interactive controls retains normal keyboard behavior; move focus outside a button to talk.

The backend validates frames and runs a per-connection Pipecat pipeline using Silero VAD and `LocalSmartTurnAnalyzerV3` on CPU. A provider-neutral speech recognition component runs Parakeet FP32 ONNX on CPU by default; Vosk remains selectable through `STT_PROVIDER`. Both emit final transcripts before the user aggregator. Local Piper synthesis and browser playback deliver the database-configured welcome and generated dialog replies. Laya classifies intent and GLiNER extracts fields on CPU (FP32 by default; optional INT8); no free-form generative LLM is used. Optional latest-session debug capture stores private WAV audio and transcript events on disk (enabled in the local Compose demo; see below). Only the session UUID, start/end timestamps, completion status, and received byte count are stored after each connection ends. Process crashes can lose this final metadata; active sessions are not durable. No historical session browsing API is provided.

## English speech recognition

The application uses `voice_api.stt.LocalSTT`, a Pipecat adapter around the `Recognizer` PCM interface (`accept`, `flush`, `close`). The dialog engine and WebSocket transport do not depend on a particular recognition provider. Set `STT_PROVIDER=parakeet` (default) or `STT_PROVIDER=vosk`; unknown values fail pipeline creation. Restart/recreate the API after changing the environment. Both providers are installed in the same image, so switching requires no source change or rebuild after this image is built.

### Parakeet FP32 ONNX (default)

Install the pinned backend requirements, then prepare the local model from the repository root:

```powershell
apps/backend/.venv/Scripts/python.exe scripts/prepare_parakeet.py
$env:STT_PROVIDER = 'parakeet'
$env:PARAKEET_MODEL_PATH = (Resolve-Path models/parakeet-tdt-0.6b-v3).Path
$env:STT_CPU_THREADS = '4'
```

On Linux substitute `apps/backend/.venv/bin/python`. The preparation script downloads the pinned [Parakeet TDT 0.6B v3 ONNX export](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx) into ignored `models/parakeet-tdt-0.6b-v3/`, including the FP32 encoder, external tensor data, decoder/joint network, configuration and vocabulary. Budget several GB for download, disk and inference memory; actual memory and concurrent-session capacity need measurement. Preparation needs network access; run it before setting offline Hub mode. The underlying NVIDIA model is CC-BY-4.0; retain attribution when distributing weights. `onnx-asr==0.12.0` supplies NumPy preprocessing and TDT decoding. Inference explicitly selects `CPUExecutionProvider` and `quantization=None`; GGUF and INT8 files are not used. No OpenVINO/GPU/NPU acceleration is configured. `STT_CPU_THREADS` accepts 1-32, defaults to 4, and controls ONNX intra-operation threads (inter-operation threads: 1).

Compose mounts the prepared directory read-only at `/models/parakeet-tdt-0.6b-v3`. Native startup requires an absolute `PARAKEET_MODEL_PATH`. Local model construction fails if required files are absent; sessions never download weights. Weights are shared within the process and inference is serialized across connections; buffers and segmentation VAD remain private to each connection.

Parakeet transcribes buffered segments rather than incremental words. A session-local Silero VAD finalizes a segment after approximately 0.6 seconds of silence while Space remains held. Release explicitly finalizes remaining detected speech before the synthetic silence tail. Silence-only input does not invoke recognition. A half-second rolling pre-roll protects word onsets; continuous speech is split at approximately 20 seconds to bound memory and model input length. A forced split can cut a word and affect identifier accuracy. Smart Turn still owns conversational turn completion. The multilingual weights are used for the English-only workflow; this integration does not enforce language detection or add supported languages.

### Vosk fallback

Download the [small US English model](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip) and extract it so `models/vosk-model-small-en-us-0.15/am/final.mdl` exists. Set `VOSK_MODEL_PATH` to its absolute directory for native startup; Compose already sets `/models/vosk-model-small-en-us-0.15`. Keep these files prepared to switch back using only `STT_PROVIDER=vosk`. Vosk retains incremental endpoint recognition and explicit finalization on release, with shared weights and a private decoder per connection.

For Compose, set `STT_PROVIDER=parakeet` or `STT_PROVIDER=vosk` in `.env`, then run `docker compose up -d --no-deps --force-recreate --wait api web`. Recreating the web proxy refreshes its API address. This ends active calls and uses the currently built image; build the updated image first with `docker compose build api`. Retain both model directories for environment-only switching.

### Recognition lifecycle

Both providers consume ordered mono 16 kHz PCM16 off the event loop and emit nonempty final `TranscriptionFrame` objects. Native inference already running is awaited on cancellation before session state is released; disconnect discards pending audio without finalizing it. Transcripts are internal only: they are not logged or sent to the browser; optional debug capture records recognition results and completed caller turns. Complete caller text drives the dialog engine. Recognition quality, especially exact alphanumeric identifiers, must be checked separately from transport success.

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
$env:STT_PROVIDER = 'parakeet'
$env:PARAKEET_MODEL_PATH = (Resolve-Path models/parakeet-tdt-0.6b-v3).Path
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

Prepare the [dialog models](dialog-orchestration.md#local-inference-adapters), selected [speech recognition model](#english-speech-recognition) and Piper voice before these startup commands. Provision that dedicated database and role before migrating. Check the effective `DATABASE_URL`; Alembic prints the target with the password hidden. Migration `0001` creates `voice_sessions`; `0002` creates and seeds `dialog_policy` in the same application database; `0003` adds the Claim Status seed while preserving operator customization. Alembic owns schema changes; application startup never creates tables. Downgrading `0002` deletes configured dialog policy; downgrading `0001` deletes session metadata.

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

### Rebuild and redeploy

After configuring `.env` and preparing the models above, run from the repository root:

```powershell
.\scripts\redeploy.ps1
# Optional clean build and longer startup timeout:
.\scripts\redeploy.ps1 -NoCache -WaitTimeoutSeconds 600
```

The script requires PowerShell 5.1+ and Docker Compose v2.20+ with Linux containers. On Linux with PowerShell installed, use `pwsh -File ./scripts/redeploy.ps1`. It uses the current local checkout, repository `.env`, and `compose.yaml` regardless of the caller's directory; it does not pull Git changes or download models. Use the same Compose project name (`COMPOSE_PROJECT_NAME` if customized) as the existing deployment.

It validates Compose configuration without printing secrets, builds the API/migration/frontend images before stopping the app, starts and waits for PostgreSQL, stops web/API (ending active calls), and runs Alembic against the single shared application database `voice` at `db:5432`. It then recreates web/API and waits for API health and running services (300 seconds by default). Web has no separate health check; this is not a browser or voice acceptance test.

Database volumes, model files, and session-debug files are preserved. Back up important database data before upgrading: migrations can change schema and policy data. Failure returns a nonzero exit code; migration/startup failures can leave the application unavailable. Inspect `docker compose logs --tail 100 api db`, correct the problem, and rerun. The migration container's output appears in the script terminal. There is no automatic rollback. Existing HTTPS and remote-access requirements above still apply.

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

Pipecat owns asynchronous processing, interruption frames, and cleanup. Silero uses its default thresholds and a 0.2-second stop interval. Smart Turn uses its bundled v3.2 CPU model with one inference thread and `wait_for_transcript=True` so the completed turn includes finalized recognition text before dialog processing. Model construction runs off the event loop. Space remains the capture gate: while held, silence is available for natural endpointing. On release, up to 3.5 seconds of paced synthetic silence lets Smart Turn finish an incomplete turn without reopening the microphone; a new press cancels that tail. Silence is excluded from received byte metadata. A disconnected session cancels the pipeline and its analyzer resources. Debug capture excludes this synthetic silence; enabling `PIPECAT_SMART_TURN_LOG_DATA` is rejected.

The client clears queued playback on speech-start events and ignores turn-end events. Completed turns invoke the dialog engine and synthesize its generated response texts. Browser AEC/noise reduction quality, speech endpoint accuracy, concurrency, and Intel device acceleration require separate acceptance measurements. No GPU/NPU capability or latency target is claimed.

## Latest-session debug capture

For local testing, Compose enables `SESSION_DEBUG_ENABLED=true` and mounts the repository's ignored `session-debug/` directory at `/session-debug`. Recreate the API after changing configuration with `docker compose up -d --build api`. Native execution defaults to disabled; set `SESSION_DEBUG_ENABLED=true` and optionally `SESSION_DEBUG_DIR` (default `session-debug`, relative to the backend working directory).

Open `session-debug/input.wav` in a media player and `session-debug/transcripts.jsonl` in a text editor. `session.json` identifies the session and final connection status. WAV is mono 16 kHz PCM16 containing accepted microphone chunks, without generated replies or synthetic endpoint silence. Pauses between capture presses are concatenated. Transcript JSON lines contain UTC timestamps, audio offsets in seconds, and `recognition` (final recognition segments) or `caller_turn` (completed text reaching the dialog handler) events. Empty recognition produces no transcript event; compare the WAV when speech was missed. Offsets identify processed audio boundaries, not word alignment. Pending recognition is still cancelled on disconnect, so an abrupt disconnect can leave audio without final text.

Files are flushed during capture and retained after disconnect for inspection. The next accepted session replaces only these three files, even if its pipeline startup subsequently fails. If sessions overlap, only the newest session is recorded; older sessions continue normally and cannot append to or close its files. Use one API worker/process for this local debug feature; cross-process rotation is unsupported. Existing transport limits bound input audio to 64 MiB and 30 minutes per session. Copy files elsewhere before starting another session if you want to retain them.

Set `SESSION_DEBUG_ENABLED=false` to stop new captures. Existing artifacts remain until manually removed or replaced by the next enabled session. Files are excluded from Git and Docker build context and are not served by HTTP or stored in PostgreSQL. Disk write failures fail the session rather than silently losing diagnostics. This is a testing facility, not durable recording or historical session storage.
