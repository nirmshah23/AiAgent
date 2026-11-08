Native Windows is the current application workflow; see [setup and lifecycle](../docs/native-windows.md). Container results below are historical evidence from the removed deployment workflow.

# Test discovery and execution

Native lifecycle checks are discovered under `tests/backend/focused/native_setup/test_*.py`. Run `npm run test:backend:focused:native-setup`; these checks cover literal environment loading, repository-relative paths, dedicated database targeting, credential redaction, missing models, occupied ports, authenticated graceful shutdown, and safe repeated stop. They do not connect to the deployment database.

Dialog engine checks are discovered under `tests/backend/focused/dialog/test_*.py`. Run `npm run test:backend:focused:dialog` from the root; its launcher is `tests/scripts/backend/start_backend_focused_dialog.ps1`. On Linux use `apps/backend/.venv/bin/python -m pytest -c tests/backend/pytest.ini --confcutdir=tests/backend tests/backend/focused/dialog`. Install the base backend requirements and pytest/httpx/ruff first. These checks use fake model adapters, mocked HTTP and isolated SQLite, including policy persistence and migration upgrade/downgrade. They do not verify real model inference, PostgreSQL, voice playback or latency. Optional model packages install from `apps/backend/requirements-dialog.txt`; see [dialog setup](../docs/dialog-orchestration.md).

Dialog increment verification: 34 focused dialog tests, the 12 existing voice-capture tests, Ruff lint/format checks and example-policy validation passed on Windows/Python 3.12. Optional model package installation and concrete runtime-interface inspection also passed. Model weights/inference, INT8 quality, performance, live PostgreSQL migration and Linux container integration remain unverified. No browser behavior changed.

For both application backend modules, set `DIALOG_ENABLED=false` and run `apps/backend/.venv/Scripts/python.exe -m pytest -c tests/backend/pytest.ini --confcutdir=tests/backend tests/backend/focused` on Windows (substitute `.venv/bin/python` on Linux). This isolates capture protocol tests from shared inference startup; live-dialog acceptance must use enabled runtime separately. Lint/format checks apply to `apps/backend` and `tests/backend/focused`.

Application checks are separate from the imported Pipecat tests. Install backend development tools into the isolated application environment:

```powershell
uv pip install --python apps/backend/.venv/Scripts/python.exe pytest httpx ruff
$env:SETUPTOOLS_SCM_PRETEND_VERSION = '1.3.0.dev0'
uv pip install --python apps/backend/.venv/Scripts/python.exe -e .
npm run test:backend:focused:voice-capture
apps/backend/.venv/Scripts/ruff check apps/backend tests/backend/focused/voice_capture
apps/backend/.venv/Scripts/ruff format --check apps/backend tests/backend/focused/voice_capture
```

Browser checks use Playwright with synthetic microphone input and a simulated WebSocket peer. They test actual Web Audio capture in Chromium but do not verify PostgreSQL or the real server from the browser:

```powershell
Set-Location apps/frontend
npm ci
npx playwright install chromium
npm run build
npx ng test --watch=false
npm run test:ui:focused:voice-capture
```

Backend tests are discovered under `tests/backend/focused/voice_capture/test_*.py`. Browser tests are discovered under `tests/user_interface/focused/voice_capture/*.spec.ts` by `apps/frontend/playwright.config.ts`. Screenshots and reports are untracked under `apps/frontend/test-results`. Protocol tests replace metadata writes and must not be described as persistence integration tests. The same focused suite includes real bundled CPU Silero/Smart Turn inference using a recorded 16 kHz speech fixture, checks turn events and analyzer cleanup, and rejects raw audio logging. The real pipeline also requires the selected recognition model described in [setup](../docs/voice-capture.md#english-speech-recognition): Parakeet FP32 ONNX by default, or Vosk with `STT_PROVIDER=vosk`. Set its absolute model path before running from another working directory. Run the voice focused suite separately with each provider to verify switching. It exercises recognition ingestion alongside audio analysis; it does not assert transcription accuracy or run an LLM. Pipeline initialization also requires the prepared Piper model described in [Piper setup](../docs/voice-capture.md#piper-speech-synthesis); existing tests do not request speech. No performance benchmark or full speech workflow suite exists yet.

Root package scripts provide `build:ui`, `test:backend:focused:voice-capture`, and `test:ui:focused:voice-capture`. The backend script uses the Windows virtual environment executable. The capture launcher explicitly sets `DIALOG_ENABLED=false` for these isolated protocol checks and restores the previous value afterward. On Linux invoke `DIALOG_ENABLED=false apps/backend/.venv/bin/python -m pytest -c tests/backend/pytest.ini --confcutdir=tests/backend tests/backend/focused/voice_capture` instead. The dedicated pytest configuration avoids inheriting upstream Pipecat fixture and plugin requirements.

Angular unit tests are colocated as `src/app/*.spec.ts`, run by Angular's Vitest builder using `tsconfig.spec.json`. From the root, use `npm run test:ui:unit`.

For integration acceptance, run `scripts/native.ps1 start`, verify the health check, hold/release Space in the browser, end the session, and check that `voice_sessions` contains its final byte count and timestamps. Also verify browser microphone permission denial and disconnect/reconnect. Run these against the dedicated local database, never a shared database. Full browser-to-live-server spoken-response and inference latency acceptance remain separate; English recognition and dialog-to-Piper wiring are implemented.

Use `scripts/native.ps1 check` and `start` to verify native runtime and PostgreSQL integration separately from isolated checks.

Audio integration verification: 12 backend focused tests, 4 Angular unit tests, 4 Playwright capture checks, the frontend production build, Ruff checks, and the backend Docker image build passed. The Linux container also passed a CPU pipeline startup/PCM ingestion/cleanup smoke check. This does not establish full Compose/PostgreSQL integration or acoustic/performance acceptance.

Vosk integration verification: the 12 existing backend focused tests and Ruff checks passed on Windows/Python 3.12 with Vosk 0.3.45 and `vosk-model-small-en-us-0.15`. A separate real-audio processor smoke check confirmed nonempty final transcription frames across two consecutive utterances and no text for silence. Recognition accuracy, performance/concurrency, the updated Linux image, and full Compose/browser integration have not been verified for this change.

Piper implementation verification: existing 12 backend focused checks, 4 Angular unit checks, 4 Playwright capture checks, and the UI production build passed on Windows. A real CPU synthesis smoke check produced PCM and verified interruption gating and worker cleanup. A real WebSocket/Piper check verified welcome audio and start/stop/end (database writes mocked); a separate Chromium smoke check verified PCM scheduling, press interruption, and playback-context cleanup. New automated TTS/playback scenarios belong to the separate test-authoring phase required by the testing skill. The Linux API image build and container CPU synthesis/bounded-PCM/interruption/cleanup smoke check passed with read-only mounted weights. A forced native inference failure produced a safe speech_error notification and muted output. Hardware latency/concurrency, acoustic quality and full browser-to-live-server acceptance remain unverified.

Live dialog-to-Piper verification: `npm run test:backend:focused:dialog` passed 34 checks, `npm run test:backend:focused:voice-capture` passed 12 checks through its isolated capture launcher, `npm run test:ui:unit` passed four checks, and `npm run test:ui:focused:voice-capture` passed four checks. UI build, Ruff and Compose build/startup also passed. Additional smoke checks covered multi-turn speech delivery, terminal playback drain, speech errors and interrupted business calls. An all-real native Vosk/Laya/GLiNER-FP32/dialog/Piper request-to-missing-field-response check passed. Chromium also passed against the real Compose stack with recorded microphone input; the dedicated PostgreSQL database recorded a completed session with nonzero bytes. No insurer endpoint was contacted. See [live voice verification](../docs/dialog-orchestration.md#live-voice-verification) for limits and the observed INT8 extraction regression. These smoke checks do not replace a separately authored persistent dialog browser regression suite.

Claim lookup simplification and Piper duration verification: 34 dialog checks, 12 voice-capture checks and four Playwright capture checks passed. Separate smoke checks exercised both new lookup combinations through DialogSession and the HTTP simulator, rejected incomplete criteria/invalid dates, applied the fresh migration chain through `0004` in isolated SQLite, rejected invalid Piper multipliers and confirmed real CPU synthesis produced longer PCM at `1.3` than `1.0`. These smoke checks do not establish spoken identifier/date recognition accuracy or a persistent regression suite for the new rules.

The updated Compose images built successfully. The verified local `voice` database migrated from `0003` to `0004` after policy export; the API became healthy. Both combinations passed in the Linux container using the stored policy, and real Piper CPU synthesis passed with effective `PIPER_LENGTH_SCALE=1.3`. The ignored local policy backup is excluded from Docker build context.

Intent configuration checks: `npm run test:backend:focused:dialog` includes policy API validation, create/edit/delete, stale revisions and rejected origins against isolated SQLite. `npm run test:ui:unit` includes dynamic schema controls and preservation of edits after a save conflict. `npm run test:ui:focused:dialog` uses `apps/frontend/playwright.dialog.config.ts`, discovers `tests/user_interface/focused/dialog`, and starts a disposable real FastAPI/SQLite service on 8011 and Angular on 4211. It requires the backend virtual environment and installed Chromium; its Python path adapts to Windows/Linux. It does not start models, access the deployment database, or measure PostgreSQL concurrent locking. Screenshots are saved under `apps/frontend/test-results/dialog`. Existing voice browser checks remain under their separate configuration.

Intent editor verification on Windows: 43 dialog backend checks, 12 capture backend checks, seven Angular unit checks, two policy browser checks and four existing capture browser checks passed. Production UI build and backend Ruff lint/format checks passed. Desktop (1440px) and narrow (390px, including expanded nested controls) screenshots were inspected. Policy browser checks use real HTTP and isolated SQLite; deployment PostgreSQL concurrency, enabled-model alias/threshold enforcement and container acceptance were not exercised by this browser suite.

Latest-session debug capture verification: 12 voice focused checks and 43 dialog focused checks passed. The eight WebSocket protocol checks also passed with SESSION_DEBUG_ENABLED=true and an isolated temporary artifact directory. Separate filesystem smoke checks verified WAV readability during capture, transcript output, replacement, and stale-session isolation. Backend Ruff lint/format checks passed. Container acceptance and capture latency remain unmeasured; no new persistent tests were authored in this implementation phase.

Native Windows workflow verification: setup completed with Python 3.12 and CPU PyTorch, including npm ci. The 43 dialog checks, 12 capture checks, 13 native lifecycle checks, nine Angular unit checks, six Playwright checks, production frontend build and backend Ruff lint/format checks passed. Native startup from another working directory, repeated start, graceful stop and restart passed. A dedicated fresh `voice_native` database and application role were created on the existing PostgreSQL 18 server; migrations reached `0004` and seeded policy. A real native WebSocket smoke check received welcome and generated response PCM and persisted a completed session with 161,998 received audio bytes. Chromium verified the native page, Angular API proxy and stored intent editor. A disposable PostgreSQL cluster was used for initial migration/startup verification and stopped afterward; existing Docker volumes were untouched. Physical acoustic quality, domain recognition accuracy, hardware latency/concurrency and Intel acceleration remain unverified.

Native cold Piper synthesis initially exceeded the generic three-second audio-context idle limit. The application now uses a 30-second safety timeout while retaining Pipecat's explicit context completion and interruption/cancellation ownership. Real CPU welcome and generated-response delivery passed after this adjustment.

Real native Chromium smoke verification passed again after a full API restart (cold model load), covering voice capture with recorded microphone input, welcome/generated PCM, press interruption, session end and reconnect. This is browser/runtime integration evidence, not physical microphone or acoustic acceptance. Angular connection setup now allows up to 60 seconds for cold native recognition model loading; unit tests verify delayed readiness and eventual timeout.

## Parakeet OpenVINO verification

On 9 November 2026, native Windows 11 checks used Core Ultra 5 125H, Intel Arc integrated graphics (driver 32.0.101.5763), approximately 15.5 GiB system RAM, Python 3.12.15, ONNX Runtime 1.31.1 and `onnxruntime-ep-openvino==1.8.1`. The existing pinned Parakeet TDT 0.6B v3 FP32 ONNX export was used without quantization, with four CPU intra-op threads and serialized batch-one inference. The plugin detected CPU, Arc GPU and Intel AI Boost NPU; NPU recognition was not attempted.

The [benchmark commands](../docs/voice-capture.md#optional-intel-openvino-execution) ran the bundled 5.062-second speech WAV once cold and three times warm per backend, in separate processes:

| Backend | Model load | First inference | Warm inference median | Warm real-time factor |
| --- | --- | --- | --- | --- |
| ONNX CPU FP32 | 5.65 s | 1.46 s | 0.456 s | 0.090 |
| OpenVINO Arc GPU FP32 hint, profiling enabled | 12.19 s | 1.43 s | 0.347 s | 0.068 |

All transcript fingerprints matched exactly across both backends and all runs. The GPU encoder/decoder execution profiles recorded 156 OpenVINO graph-node executions and no CPU graph-node executions; both sessions reported OpenVINO followed by CPU fallback. Preprocessing/resampling and the remaining voice components still use CPU. No whole-model CPU fallback occurred in the GPU benchmark. Profile artifacts remain private under ignored `.local-run/parakeet-profiles/`.

These are small, sequential smoke measurements on a busy machine, not a general speedup guarantee. GPU warm runs ranged from 0.316 to 1.137 seconds. An earlier first GPU initialization took 43.79 seconds plus 14.62 seconds for first inference; compilation state and system load materially affect cold timings. Different input lengths may introduce new compilation costs. Memory peaks, hardware utilization, long utterances, concurrent calls, FP16 quality, NPU execution and browser-to-audible-response latency were not measured.

The existing full backend focused suite passed 68 checks with the CPU default. The 12 voice-capture checks also passed with `PARAKEET_BACKEND=openvino`, `PARAKEET_OPENVINO_DEVICE=GPU`, `PARAKEET_OPENVINO_PRECISION=FP32` and `DIALOG_ENABLED=false`, covering real audio ingestion, turn handling and cleanup. Backend and changed-script Ruff lint/format checks passed. Separate in-process smoke checks verified initialization fallback, inference-error retry and shared CPU retention, propagation of CPU errors, recovery after a failed CPU allocation, and invalid configuration rejection. These temporary smoke checks do not replace persistent regression tests; no tests were authored in this implementation phase. See the configuration guide for optional installation and provider diagnostics.
