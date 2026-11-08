# Web Voice Chatbot

A planned English-only, web-based voice chatbot built on [Pipecat](https://github.com/pipecat-ai/pipecat). Users will speak through their browser microphone and hear spoken responses. Initial scope excludes user authentication, typed chat, video, and multilingual support. Accessible start, stop, mute, connection status, and error controls remain part of the voice interface.

## Current status

This repository contains the imported Pipecat Python framework, its examples, and tests. The application-specific browser client, voice pipeline configuration, model selection, Docker images, and Docker Compose deployment have not yet been implemented. There is no application startup command or verified hardware benchmark yet.

The intended workflow is Windows development in VS Code with Docker Desktop, followed by deployment of Linux containers using Docker Compose on a Linux host. The target hardware is an Intel Core Ultra 5 processor with Intel Arc graphics. Exact hardware variants and available memory remain to be confirmed.

## Planned voice workflow

1. The user starts a browser session and grants microphone access.
2. A streaming audio transport connects the browser to a Pipecat session.
3. Voice activity detection and turn handling feed English speech recognition.
4. A language model generates a response, and speech synthesis streams English audio back to the browser.
5. Interruption handling stops obsolete speech when the user speaks again; stopping or disconnecting releases session resources.

Transport, model providers, and application API contracts must be selected and documented during implementation. Reuse Pipecat's asynchronous streaming model. Prefer local inference where practical for this hardware; any external service dependency must be explicit and configurable.

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
- `.agents/skills/`: preserved local implementation and testing guidance.
- [src/pipecat/](src/pipecat/): imported Pipecat implementation.
- [examples/](examples/): upstream examples; these are references rather than the finished chatbot.
- [tests/](tests/): upstream test suite.
- [pyproject.toml](pyproject.toml): Python package metadata, dependencies, and tooling.
- [Pipecat documentation](https://docs.pipecat.ai/): framework documentation.

## Verification and maintenance

Follow the repository testing skill and the relevant implementation skills. During application development, verify microphone permission failures, connection failures, silence, English speech input/output, user interruptions, session stop/reconnect, and resource cleanup. Use Playwright for browser flows and inspect substantial UI changes at desktop and narrower widths. Test CPU fallback and Intel acceleration separately; report unverified environments explicitly.

Keep this README current in the same change as project behavior, contracts, configuration, deployment, or operational instructions. Distinguish plans from implemented behavior, verify links and commands, and link to authoritative detailed documentation instead of duplicating it. Add a documentation index when the project needs additional guides.

## Upstream and license

This project builds on Pipecat. Preserve upstream copyright and license notices; see [LICENSE](LICENSE). The Git `upstream` remote points to Pipecat, while `origin` points to this project's repository.
