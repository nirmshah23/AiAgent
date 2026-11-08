---
name: generative-ai-local-inference
description: Select, configure, accelerate, benchmark, and integrate local generative-AI and ML models on the project's Windows 11 Intel Core Ultra 5 system with Intel Arc graphics.
---

# Local Generative AI and ML Inference

Read `AGENTS.md` and the model/framework-specific documentation before changing inference code or dependencies.

## Target machine

- Primary development and experimentation target: Windows 11, Intel Core Ultra 5 (the available machine is Core Ultra 5 125H), and Intel Arc integrated graphics.
- Treat the CPU, Arc GPU, and any NPU exposed by the installed hardware/runtime as resources to evaluate. Detect actual device availability at runtime; do not assume every runtime exposes every device.
- The Arc GPU uses system/shared memory. Check available memory and model requirements rather than treating it like a discrete GPU with dedicated VRAM.

## Device and runtime selection

- Before selecting a model or inference library, verify its current Windows support, supported Intel devices, model formats, operator coverage, and acceleration backend.
- Prefer an Intel-supported acceleration route where it works reliably, such as OpenVINO or a framework's supported Intel GPU backend. Evaluate NPU execution only when the selected runtime and model explicitly support it.
- Do not assume CUDA or NVIDIA-specific packages. Do not install CUDA-only dependencies for this target machine.
- Keep device selection configurable (for example, `AUTO`, `GPU`, `NPU`, or `CPU` only where the chosen runtime supports those values). Provide a clear CPU fallback and surface when fallback occurs.
- Avoid silently claiming acceleration: log or expose the actual execution provider/device selected by the runtime.

## Model selection and resource management

- Prefer models that meet the task's quality requirements while fitting the machine's practical memory and compute limits. Evaluate quantized variants where appropriate.
- Check model size, runtime memory overhead, context length, KV-cache requirements, and concurrent workload costs before downloading or loading weights.
- Start with conservative batch sizes and concurrency. Increase them only after measuring latency, throughput, memory use, and stability on representative inputs.
- Reuse loaded models when appropriate, but provide explicit lifecycle management and release resources when a model is no longer needed.
- Keep model downloads, caches, and generated artifacts in configured locations; do not hardcode user-specific paths or commit model weights and secrets.

## Benchmarking and verification

- Benchmark the actual end-to-end workload, not only a synthetic kernel. Include model load time, warm-up, steady-state latency, throughput, and peak memory where measurable.
- Record model/version, quantization, runtime/version, execution provider/device, input characteristics, and whether CPU fallback occurred so results are reproducible.
- Compare accelerated and CPU execution for correctness as well as performance. Check output quality and numerical tolerances appropriate to the task.
- Add tests that run without an accelerator; accelerator-specific tests should detect unavailable hardware and skip with a clear reason rather than making the entire test suite unusable.
- Recheck compatibility when upgrading drivers, runtimes, model formats, or model versions.

## Implementation principles

- Isolate inference behind a small application-facing interface so model/runtime choices can change without rewriting business logic.
- Keep device/runtime configuration separate from prompts, domain rules, and API contracts.
- Do not make network-hosted inference the default when a suitable local model can meet the requirement. If local execution is unsuitable, explain the limitation and obtain an explicit decision before introducing a hosted provider.
