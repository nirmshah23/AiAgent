# Voice capture application

## Implemented scope

`apps/frontend` is a standalone Angular 21.2.25 application with Angular Material 21.2.14. `apps/backend` is a FastAPI application. One PostgreSQL database, `voice`, owns all application data; there is no tenancy or authentication. These applications do not modify the imported Pipecat library.

The separate [dialog engine](dialog-orchestration.md) now has database-backed configuration and Laya/Regex/GLiNER adapters. It is connected to completed caller turns; generated reply audio uses the existing binary WebSocket playback path. Migration `0002` adds shared dialog policy alongside session metadata; capture stores no caller transcripts.

The browser connects before requesting microphone access. Holding Space requests mono microphone audio, creates a 16 kHz Web Audio `AudioContext`, and uses an AudioWorklet to encode signed 16-bit little-endian PCM. Releasing Space stops tracks, disconnects nodes, closes the context, and prevents queued worklet messages from being transmitted. Key repeat is ignored. Blur, hidden documents, page exit, microphone removal, and session termination also stop capture. Permission prompts may outlast a press; audio from a late permission result is stopped without transmission. Space on interactive controls retains normal keyboard behavior; move focus outside a button to talk.

The backend validates frames and runs a per-connection Pipecat pipeline using Silero VAD and `LocalSmartTurnAnalyzerV3` on CPU. A provider-neutral speech recognition component runs Parakeet FP32 ONNX on CPU by default; Vosk remains selectable through `STT_PROVIDER`. Both emit final transcripts before the user aggregator. Local Piper synthesis and browser playback deliver the database-configured welcome and generated dialog replies. Laya classifies intent and GLiNER extracts fields on CPU (FP32 by default; optional INT8); no free-form generative LLM is used. Optional latest-session debug capture stores private WAV audio and transcript events on disk (enabled in the native experimental configuration; see below). Only the session UUID, start/end timestamps, completion status, and received byte count are stored after each connection ends. Process crashes can lose this final metadata; active sessions are not durable. No historical session browsing API is provided.

## English speech recognition

The application uses `voice_api.stt.LocalSTT`, a Pipecat adapter around the `Recognizer` PCM interface (`accept`, `flush`, `close`). The dialog engine and WebSocket transport do not depend on a particular recognition provider. Set `STT_PROVIDER=parakeet` (default) or `STT_PROVIDER=vosk`; unknown values fail pipeline creation. Restart/recreate the API after changing the environment. Both providers are installed in the native environment; switching requires an API restart.

### Parakeet FP32 ONNX (default)

Install the pinned backend requirements, then prepare the local model from the repository root:

```powershell
apps/backend/.venv/Scripts/python.exe scripts/prepare_parakeet.py
$env:STT_PROVIDER = 'parakeet'
$env:PARAKEET_MODEL_PATH = (Resolve-Path models/parakeet-tdt-0.6b-v3).Path
$env:STT_CPU_THREADS = '4'
```

The preparation script downloads the pinned [Parakeet TDT 0.6B v3 ONNX export](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx) into ignored `models/parakeet-tdt-0.6b-v3/`, including the FP32 encoder, external tensor data, decoder/joint network, configuration and vocabulary. Budget several GB for download, disk and inference memory; actual memory and concurrent-session capacity need measurement. Preparation needs network access; run it before setting offline Hub mode. The underlying NVIDIA model is CC-BY-4.0; retain attribution when distributing weights. `onnx-asr==0.12.0` supplies NumPy preprocessing and TDT decoding. The CPU default explicitly selects `CPUExecutionProvider` and `quantization=None`; GGUF and INT8 files are not used. Optional Intel OpenVINO execution is described below. `STT_CPU_THREADS` accepts 1-32, defaults to 4, and controls ONNX intra-operation threads (inter-operation threads: 1).

The native launcher resolves PARAKEET_MODEL_PATH against the repository root. Local model construction fails if required files are absent; sessions never download weights. Weights are shared within the process and inference is serialized across connections; buffers and segmentation VAD remain private to each connection.

Parakeet transcribes buffered segments rather than incremental words. A session-local Silero VAD finalizes a segment after approximately 0.6 seconds of silence while Space remains held. Release explicitly finalizes remaining detected speech before the synthetic silence tail. Silence-only input does not invoke recognition. A half-second rolling pre-roll protects word onsets; continuous speech is split at approximately 20 seconds to bound memory and model input length. A forced split can cut a word and affect identifier accuracy. Smart Turn still owns conversational turn completion. The multilingual weights are used for the English-only workflow; this integration does not enforce language detection or add supported languages.

### Optional Intel OpenVINO execution

From the repository root, install the separate plugin into the existing native environment:

```powershell
apps/backend/.venv/Scripts/python.exe -m pip install -r apps/backend/requirements-openvino.txt
```

Keep the standard `onnxruntime` package; the `onnxruntime-ep-openvino` plugin registers alongside it. Do not install the deprecated replacement `onnxruntime-openvino` package. The optional requirements pin the tested plugin and require ONNX Runtime 1.31.1 or newer. See the [official plugin instructions](https://github.com/onnxruntime/onnxruntime-ep-openvino/blob/main/docs/QuickStart.md).

Set these values in ignored `.env`, then restart the API through the native launcher:

```dotenv
STT_PROVIDER=parakeet
PARAKEET_BACKEND=openvino
PARAKEET_OPENVINO_DEVICE=GPU
PARAKEET_OPENVINO_PRECISION=FP32
STT_CPU_THREADS=4
```

`PARAKEET_BACKEND` accepts `cpu` (default) or `openvino`. OpenVINO device selection accepts `GPU`, `CPU`, or `NPU`; unavailable devices trigger a logged CPU fallback. NPU recognition is experimental and unverified; detection alone does not establish model support. Precision accepts `FP32` (default) or `FP16`, applied as an OpenVINO inference precision hint to the existing FP32 weights. FP16 quality requires separate validation. Invalid settings fail configuration validation.

Only Parakeet model sessions receive the OpenVINO device; NumPy preprocessing, resampling, Silero, Smart Turn, Piper and dialog models retain their existing CPU paths. ONNX Runtime can place unsupported graph operations on CPU. Model initialization logs the requested hardware/precision and the actual encoder/decoder provider lists through the Uvicorn logger. Provider presence alone does not prove all nodes execute on GPU; use the benchmark profiles below. Missing plugins, unavailable devices, model initialization errors and accelerated inference errors produce an explicit warning and a shared CPU fallback. Inference errors retry the same utterance once on CPU; CPU errors still propagate. Native work remains serialized and cancellation waits for it to finish. Return to the baseline with `PARAKEET_BACKEND=cpu` and an API restart.

Cold OpenVINO compilation and first inference can be slow. The API currently constructs recognition on the first browser session and allows 60 seconds for readiness; cold GPU initialization may approach or exceed that limit on a busy machine. Benchmark before enabling it for calls. No model compilation cache or startup warm-up is enabled.

Run each backend separately to avoid holding two copies of the model in shared memory:

```powershell
apps/backend/.venv/Scripts/python.exe scripts/benchmark_parakeet.py --backend cpu
apps/backend/.venv/Scripts/python.exe scripts/benchmark_parakeet.py --backend openvino --device GPU --profile
```

The benchmark uses the existing 5.06-second speech fixture by default, performs one cold inference and three warm runs, reports runtime/device/precision, load and inference timings, real-time factor, provider lists and transcript SHA-256 fingerprints. Matching fingerprints compare exact output without printing text; they do not establish recognition accuracy. `--audio` accepts another 16 kHz mono PCM16 WAV; `--runs`, `--threads` and `--precision` control the comparison. Benchmark failures stop rather than silently measuring CPU fallback. Optional node profiles are private ignored files in `.local-run/parakeet-profiles/`; their execution counts identify OpenVINO versus CPU graph work, not GPU utilization percentages. Memory, concurrent calls, long utterances and physical acoustic quality need separate acceptance.

### Vosk fallback

Download the [small US English model](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip) and extract it so `models/vosk-model-small-en-us-0.15/am/final.mdl` exists. Set `VOSK_MODEL_PATH` to its absolute directory for native startup; the native environment template supplies its repository-relative path. Keep these files prepared to switch back using only `STT_PROVIDER=vosk`. Vosk retains incremental endpoint recognition and explicit finalization on release, with shared weights and a private decoder per connection.

Set STT_PROVIDER in .env, then run scripts/native.ps1 restart. This ends active calls. Retain both model directories for environment-only switching.

### Recognition lifecycle

Both providers consume ordered mono 16 kHz PCM16 off the event loop and emit nonempty final `TranscriptionFrame` objects. Native inference already running is awaited on cancellation before session state is released; disconnect discards pending audio without finalizing it. Transcripts are internal only: they are not logged or sent to the browser; optional debug capture records recognition results and completed caller turns. Complete caller text drives the dialog engine. Recognition quality, especially exact alphanumeric identifiers, must be checked separately from transport success.

## Piper speech synthesis

The backend uses pinned `piper-tts==1.3.0` and Pipecat's `PiperTTSService` on CPU. Prepare the English voice before starting the API, from the repository root after installing backend requirements:

```powershell
New-Item -ItemType Directory -Force models/piper | Out-Null
apps/backend/.venv/Scripts/python.exe -m piper.download_voices --download-dir models/piper en_US-lessac-medium
```

Both `en_US-lessac-medium.onnx` and its `.onnx.json` configuration must exist. Set `PIPER_MODEL_PATH` to the absolute ONNX path for native startup; the native launcher also accepts repository-relative paths. Sessions reject missing weights or non-English voice configurations and never download Piper weights. Restart the API after changing model files. Set `PIPER_LENGTH_SCALE` (default `1.3`) to a finite positive duration multiplier; larger values slow speech, and `1.0` uses normal duration. This explicitly overrides the voice JSON length scale. The native launcher reads it from `.env`; direct PowerShell invocation can use `$env:PIPER_LENGTH_SCALE = "1.3"`. Restart the API after changing it. The engine is GPL-3.0; inspect the chosen voice's model card for its separate license before distribution. See the [maintained Piper project](https://github.com/OHF-Voice/piper1-gpl).

Starting a browser session unlocks a separate playback AudioContext. Once ready, the client requests the database-configured spoken welcome, without opening the microphone. `AudioPipeline.speak(text)` queues interruptible `TTSSpeakFrame` requests (maximum 2000 characters) through `DialogVoiceBridge`. The speech function waits for a downstream PCM completion barrier so replies remain ordered and terminal workflows drain their final speech. No caller text is accepted through the browser. Piper audio is resampled by Pipecat to mono 16 kHz PCM16 and sent in paced chunks of at most 100 ms. The client schedules playback with a 15-second maximum queue and reports suspended/unavailable playback. Holding Space clears playback immediately, suppresses stale incoming audio until the server acknowledges the new capture turn, and interrupts server synthesis when capture starts. Session termination stops sources and closes both audio contexts. Speech errors produce a generic status without exposing response text. Upstream Piper/TTS debug logs that contain synthesized text are disabled.

The dialog runtime is shared, while each session owns a Piper instance; memory use and concurrent-session throughput remain unmeasured. CPU is the only configured device; no Intel GPU/OpenVINO acceleration is claimed. Windows native synthesis, PCM delivery, interruption gating, safe inference-failure notification and worker cleanup were smoke-tested. Historical container verification: the Linux API image built successfully and passed a CPU Piper synthesis/bounded-PCM/interruption/cleanup smoke check with read-only mounted weights. Chromium playback scheduling, interruption and context cleanup were checked against a simulated WebSocket peer. Chromium also passed a voice-to-generated-reply flow against the former Compose stack with real CPU models and recorded microphone input; PostgreSQL recorded a completed session with nonzero received bytes. Physical sound quality, echo/double-talk, domain extraction accuracy and latency/concurrency remain separate checks.

## Local Windows development

See [native Windows setup and lifecycle](native-windows.md) for prerequisites, local PostgreSQL provisioning, configuration, migrations, start/stop/restart and troubleshooting. Docker is no longer required.

The browser allows up to 60 seconds for session readiness while native recognition models load. Native CPU Piper synthesis uses a 30-second audio-context idle safety timeout so cold synthesis can exceed Pipecat's generic three-second default. Completed synthesis closes its context explicitly; interruption, cancellation and pipeline cleanup remain owned by Pipecat.

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

The client clears queued playback on speech-start events and ignores turn-end events. Completed turns invoke the dialog engine and synthesize its generated response texts. Browser AEC/noise reduction quality, speech endpoint accuracy and concurrent conversation latency require separate acceptance measurements. Parakeet Arc GPU smoke measurements are recorded in the [test guide](../tests/README.md#parakeet-openvino-verification); other components retain CPU execution and no conversational latency target is claimed.

## Latest-session debug capture

For local testing, .env.example enables SESSION_DEBUG_ENABLED=true and sets SESSION_DEBUG_DIR=session-debug, resolved against the repository root by the native launcher. Restart after changes. Direct backend execution defaults to capture disabled and resolves relative paths against its working directory.

Open `session-debug/input.wav` in a media player and `session-debug/transcripts.jsonl` in a text editor. `session.json` identifies the session and final connection status. WAV is mono 16 kHz PCM16 containing accepted microphone chunks, without generated replies or synthetic endpoint silence. Pauses between capture presses are concatenated. Transcript JSON lines contain UTC timestamps, audio offsets in seconds, and `recognition` (final recognition segments) or `caller_turn` (completed text reaching the dialog handler) events. Empty recognition produces no transcript event; compare the WAV when speech was missed. Offsets identify processed audio boundaries, not word alignment. Pending recognition is still cancelled on disconnect, so an abrupt disconnect can leave audio without final text.

Files are flushed during capture and retained after disconnect for inspection. The next accepted session replaces only these three files, even if its pipeline startup subsequently fails. If sessions overlap, only the newest session is recorded; older sessions continue normally and cannot append to or close its files. Use one API worker/process for this local debug feature; cross-process rotation is unsupported. Existing transport limits bound input audio to 64 MiB and 30 minutes per session. Copy files elsewhere before starting another session if you want to retain them.

Set `SESSION_DEBUG_ENABLED=false` to stop new captures. Existing artifacts remain until manually removed or replaced by the next enabled session. Files are excluded from Git and Docker build context and are not served by HTTP or stored in PostgreSQL. Disk write failures fail the session rather than silently losing diagnostics. This is a testing facility, not durable recording or historical session storage.
