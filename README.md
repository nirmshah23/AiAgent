# Web Voice Chatbot

An English-only, web-based voice chatbot project built on [Pipecat](https://github.com/pipecat-ai/pipecat). The first application increment captures browser audio while Space is held and streams it to FastAPI. Spoken responses remain planned. Scope excludes user authentication, typed chat, video, multilingual support, and multi-tenancy.

## Current status

A separate [dialog engine and configuration layer](docs/dialog-orchestration.md) now supports configurable General/Business intents, alternative sufficient-field rules, business API bindings, missing-field prompts, response templates and next-intent transitions. Optional CPU adapters use the `laya` package for intent classification and Regex plus INT8 GLiNER-small for intent-specific extraction. PostgreSQL policy storage and an operator import/export command are implemented; the default General intents are WELCOME and END, with no business intents seeded. The engine is not connected to the live voice pipeline yet. Real model inference, quality and latency remain unverified; speech synthesis/playback remain planned.

The repository contains the imported Pipecat framework plus an Angular 21 / Angular Material push-to-talk client in `apps/frontend` and a FastAPI WebSocket API in `apps/backend`. The browser uses Web Audio and an AudioWorklet to stream mono 16 kHz PCM16 only while Space is held; key release and focus loss stop microphone tracks. PostgreSQL stores session metadata through SQLAlchemy, with Alembic managing the single application database. Audio passes through a Pipecat pipeline with local English Vosk recognition, Silero VAD and local Smart Turn v3 endpointing and is not stored. Browser capture requests AEC, noise suppression, and automatic gain control before 16 kHz PCM16 encoding.

Dockerfiles and [Compose configuration](compose.yaml) package the frontend, API, migration job, and PostgreSQL. See [application setup and transport contract](docs/voice-capture.md) for working startup commands. The backend image builds on Docker Desktop?s Linux engine, and CPU pipeline startup, PCM ingestion, and cleanup were smoke-tested inside it. Full PostgreSQL/Compose workflow verification remains separate. Local English Vosk speech recognition is integrated after browser preprocessing. Live dialog integration, spoken replies, and hardware benchmarks remain unimplemented. CPU audio analysis is integrated; physical acoustic quality and speech endpoint accuracy remain to be measured.

The intended workflow is Windows development in VS Code with Docker Desktop, followed by deployment of Linux containers using Docker Compose on a Linux host. Native inspection identified an Intel Core Ultra 5 125H, about 16 GB RAM and Intel Arc Graphics. Exact GPU variant, usable graphics memory and Linux/container device visibility remain unverified; see the [hardware observations](docs/dialog-orchestration.md#local-inference-adapters).

## Planned voice workflow

1. The user starts a browser session and grants microphone access.
2. A streaming audio transport connects the browser to a Pipecat session.
3. Voice activity detection and turn handling feed English speech recognition.
4. The separate dialog engine uses Laya to classify intents, Regex and INT8 GLiNER-small to extract fields, and database-configured rules/APIs/templates to choose replies; speech synthesis streams English audio back to the browser.
5. Interruption handling stops obsolete speech when the user speaks again; stopping or disconnecting releases session resources.

The initial transport is a bounded WebSocket PCM stream; its [contract](docs/voice-capture.md#api-and-websocket-contract) is implemented with Pipecat audio analysis; English recognition uses Vosk. Dialog logic is implemented separately, while its live voice integration and spoken response stages remain planned. Future integration must reuse Pipecat's asynchronous streaming model. Prefer local inference where practical for this hardware; any external service dependency must be explicit and configurable.

## Development and deployment

- Use VS Code on Windows and Docker Desktop in Linux-container mode. WSL integration or a development container can provide a consistent Linux toolchain.
- Package the application and any required inference services with Docker Compose. Record actual service names, ports, health checks, environment variables, model downloads, and startup/shutdown commands when these files exist.
- Use persistent volumes for model caches and necessary runtime data. Keep credentials out of source control and images; add a sanitized environment template when configuration is introduced.
- Provide a CPU configuration for development and a separately verified Intel acceleration configuration. Document host drivers, container runtime dependencies, device permissions, and resource limits for each supported environment.
- Browser microphone access requires a secure context, typically HTTPS or localhost. Document deployment TLS and transport networking when the browser integration is implemented.
- Authentication is intentionally deferred. Make the intended network exposure explicit when deployment is added; do not store raw audio or transcripts by default without an explicit product decision.

## Intel hardware strategy

Optimize for responsive conversation and useful concurrency rather than maximum utilization percentages. First record the exact processor and graphics device, RAM, graphics memory, operating system, drivers, and inference runtime versions.

Evaluate OpenVINO-compatible speech recognition, language, and speech synthesis models. Benchmark supported quantization and CPU/GPU placement before committing to a runtime. Reserve CPU capacity for audio processing, transport, and session orchestration; avoid oversubscribing inference threads. Consider an NPU only after confirming its presence and runtime/model support.

On native Linux, supported Intel graphics workloads can access GPU render devices through `/dev/dri` with appropriate drivers and container permissions. Select only the devices and permissions the inference service requires. See [OpenVINO accelerator configuration](https://docs.openvino.ai/2026/model-server/ovms_docs_target_devices.html).

Docker Desktop's documented Windows GPU support uses NVIDIA GPU paravirtualization. Do not assume that an Intel Arc GPU is available to Linux containers simply because Docker Desktop is installed. Intel/WSL acceleration requires separate validation of the host, runtime, and container path; maintain a CPU fallback and verify full acceleration on the Linux deployment host. See [Docker Desktop GPU support](https://docs.docker.com/desktop/features/gpu/).

For each candidate configuration, measure time to first audible response, speech recognition latency, language-model time to first token, speech synthesis time to first audio, interruption responsiveness, CPU/GPU usage, memory consumption, and concurrent-session behavior. Record warm-up conditions, model versions, audio samples, and quality observations. No acceleration or performance claim is verified yet.

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
