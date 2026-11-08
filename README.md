# Web Voice Chatbot

An English-only, web-based voice chatbot project built on [Pipecat](https://github.com/pipecat-ai/pipecat). The first application increment captures browser audio while Space is held and streams it to FastAPI. Local Piper TTS streams the configured dialog welcome, clarification prompts, business responses and goodbye to browser playback. Scope excludes user authentication, typed chat, video, multilingual support, and multi-tenancy.

## Current status

A separate [dialog engine and configuration layer](docs/dialog-orchestration.md) now supports configurable General/Business intents, alternative sufficient-field rules, business API bindings, missing-field prompts, response templates and next-intent transitions. CPU adapters use the `laya` package for intent classification and Regex plus GLiNER-small (FP32 by default; optional INT8) for intent-specific extraction. PostgreSQL policy storage and an operator import/export command are implemented; Alembic revision `0003` seeds Welcome/End scripts and a Claim Status business intent with alternative field rules and response templates. An explicit offline HTTP simulator supplies synthetic claim responses; see the [Claim Status setup](docs/dialog-orchestration.md#claim-status-seed-and-simulation). Revision `0004` updates the demo to accept a claim number alone or member ID plus birth/service dates, without caller type. Piper speech duration is configurable through `PIPER_LENGTH_SCALE`, default `1.3`. The engine is connected to finalized caller turns and Piper playback. Shared CPU Laya/GLiNER models load at API startup, and each connection gets its own database policy snapshot. The default local demo explicitly uses the synthetic Claim Status API; real insurer connectivity is not configured. Model quality and latency still require measurement.

The repository contains the imported Pipecat framework plus an Angular 21 / Angular Material push-to-talk client in `apps/frontend` and a FastAPI WebSocket API in `apps/backend`. The browser uses Web Audio and an AudioWorklet to stream mono 16 kHz PCM16 only while Space is held; key release and focus loss stop microphone tracks. PostgreSQL stores session metadata through SQLAlchemy, with Alembic managing the single application database. Audio passes through a Pipecat pipeline with provider-independent local speech recognition (Parakeet FP32 ONNX CPU by default, or Vosk through `STT_PROVIDER`), Silero VAD and local Smart Turn v3 endpointing and can be captured in private latest-session debug files for local testing. Browser capture requests AEC, noise suppression, and automatic gain control before 16 kHz PCM16 encoding.

The application runs natively on Windows 11 using a Python 3.12 backend environment, Angular development server and a dedicated database on the existing local PostgreSQL server. See [native setup and lifecycle](docs/native-windows.md). Run `scripts/native.ps1 setup`, configure ignored `.env`, provision the database and prepare models, then run `scripts/native.ps1 start`. Open http://localhost:4200. Docker is not required; old Docker volumes are untouched.

The experimental machine has an Intel Core Ultra 5 125H and Intel Arc integrated graphics. Native inference defaults to CPU PyTorch and ONNX CPU execution. Parakeet also supports an optional ONNX Runtime OpenVINO plugin with explicit Intel device selection, provider logging and CPU fallback; Arc GPU recognition was smoke-tested. See [configuration and benchmarks](docs/voice-capture.md#optional-intel-openvino-execution). NPU inference and full hardware performance acceptance remain unverified. Native PostgreSQL migration, startup/restart, welcome and generated-response PCM delivery, persisted session metadata, and Angular API proxy smoke checks passed; see the [test guide](tests/README.md). Previous container verification is retained as historical evidence.

The voice workspace uses a responsive side-by-side desktop layout and stacked narrow-screen controls, with expandable setup tips. Holding Space outside interactive controls prevents page scrolling, including repeated keydown events.

The **Intent settings** operator screen supports adding, editing and deleting intents and all nested policy configuration, with validation, save-conflict detection and protected WELCOME/END intents. Changes apply to new calls. API URLs and credentials remain deployment-owned. The application remains unauthenticated and intended for local/private access; see the [configuration workflow](docs/dialog-orchestration.md#browser-configuration-workflow).

Latest-session testing artifacts are available in `session-debug/input.wav`, `transcripts.jsonl`, and `session.json` when enabled in the native configuration. They remain after disconnect and are replaced when a new accepted session starts. See [debug capture](docs/voice-capture.md#latest-session-debug-capture) for retention and concurrency limits.

## Voice workflow

1. The user starts a browser session and grants microphone access.
2. A streaming audio transport connects the browser to a Pipecat session.
3. Voice activity detection and turn handling feed English speech recognition.
4. The dialog engine uses Laya to classify intents, Regex and GLiNER-small to extract fields, and database-configured rules/APIs/templates to choose replies; speech synthesis streams English audio back to the browser.
5. Interruption handling stops obsolete speech when the user speaks again; stopping or disconnecting releases session resources.

The initial transport is a bounded WebSocket PCM stream; its [contract](docs/voice-capture.md#api-and-websocket-contract) is implemented with Pipecat audio analysis; English recognition defaults to Parakeet TDT v3 FP32 ONNX on CPU; set `STT_PROVIDER=vosk` to restore Vosk without code changes. Prepare both model directories for environment-only switching. Completed caller turns reach the dialog engine through `DialogVoiceBridge`, and its generated replies stream through Piper. Pipecat retains asynchronous processing and interruption ownership. Workflow completion drains speech before the browser ends the session. Prefer local inference where practical for this hardware; any external service dependency must be explicit and configurable.

## Development and deployment

Follow the [native Windows workflow](docs/native-windows.md) for prerequisites, PostgreSQL provisioning, configuration, migrations, start, stop and restart. Both application servers bind to loopback. PostgreSQL is managed independently; stopping the application does not stop the database. Model caches, debug recordings and supervisor logs remain private ignored files. Authentication is deferred; this workflow is for local experimental use.

## Intel hardware strategy

Optimize for responsive conversation and useful concurrency rather than maximum utilization percentages. First record the exact processor and graphics device, RAM, graphics memory, operating system, drivers, and inference runtime versions.

Evaluate OpenVINO-compatible speech recognition, language, and speech synthesis models. Benchmark supported quantization and CPU/GPU placement before committing to a runtime. Reserve CPU capacity for audio processing, transport, and session orchestration; avoid oversubscribing inference threads. Consider an NPU only after confirming its presence and runtime/model support.

Parakeet has configurable OpenVINO execution and a repeatable CPU/GPU benchmark; other Intel acceleration still requires separate driver/runtime/model validation. Retain the CPU baseline until representative benchmarks justify a change.

For each candidate configuration, measure time to first audible response, speech recognition latency, language-model time to first token, speech synthesis time to first audio, interruption responsiveness, CPU/GPU usage, memory consumption, and concurrent-session behavior. Record warm-up conditions, model versions, audio samples, and quality observations. See the [Parakeet verification record](tests/README.md#parakeet-openvino-verification) for the limited GPU measurements; full conversational performance is not yet verified.

## Repository guide

- [AGENTS.md](AGENTS.md): project objectives, engineering constraints, documentation maintenance, and skill routing.
- [Documentation index](docs/index.md): application setup, API contract, persistence, and verification.
- [apps/](apps/): Angular Material client and FastAPI application.
- `.agents/skills/`: preserved local implementation and testing guidance.
- [src/pipecat/](src/pipecat/): imported Pipecat implementation.
- [examples/](examples/): upstream examples; these are references rather than the finished chatbot.
- [tests/](tests/): upstream test suite.
- [pyproject.toml](pyproject.toml): Python package metadata, dependencies, and tooling.
- [Pipecat documentation](https://docs.pipecat.ai/): framework documentation.

## Verification and maintenance

Follow the repository testing skill and the relevant implementation skills. During application development, verify microphone permission failures, connection failures, silence, English speech input/output, user interruptions, session stop/reconnect, and resource cleanup. Use Playwright for browser flows and inspect substantial UI changes at desktop and narrower widths. Test CPU fallback and Intel acceleration separately; report unverified environments explicitly.

Keep this README current in the same change as project behavior, contracts, configuration, deployment, or operational instructions. Distinguish plans from implemented behavior, verify links and commands, and link to authoritative detailed documentation instead of duplicating it.

## Upstream and license

This project builds on Pipecat. Preserve upstream copyright and license notices; see [LICENSE](LICENSE). The Git `upstream` remote points to Pipecat, while `origin` points to this project's repository.
