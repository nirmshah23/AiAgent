# Test discovery and execution

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

Backend tests are discovered under `tests/backend/focused/voice_capture/test_*.py`. Browser tests are discovered under `tests/user_interface/focused/voice_capture/*.spec.ts` by `apps/frontend/playwright.config.ts`. Screenshots and reports are untracked under `apps/frontend/test-results`. Protocol tests replace metadata writes and must not be described as persistence integration tests. The same focused suite includes real bundled CPU Silero/Smart Turn inference using a recorded 16 kHz speech fixture, checks turn events and analyzer cleanup, and rejects raw audio logging. The real pipeline now also requires the English Vosk model described in [setup](../docs/voice-capture.md#english-speech-recognition). It exercises recognition ingestion alongside audio analysis; it does not assert transcription accuracy or run an LLM. Pipeline initialization also requires the prepared Piper model described in [Piper setup](../docs/voice-capture.md#piper-speech-synthesis); existing tests do not request speech. No performance benchmark or full speech workflow suite exists yet.

Root package scripts provide `build:ui`, `test:backend:focused:voice-capture`, and `test:ui:focused:voice-capture`. The backend script uses the Windows virtual environment executable. The capture launcher explicitly sets `DIALOG_ENABLED=false` for these isolated protocol checks and restores the previous value afterward. On Linux invoke `DIALOG_ENABLED=false apps/backend/.venv/bin/python -m pytest -c tests/backend/pytest.ini --confcutdir=tests/backend tests/backend/focused/voice_capture` instead. The dedicated pytest configuration avoids inheriting upstream Pipecat fixture and plugin requirements.

Angular unit tests are colocated as `src/app/*.spec.ts`, run by Angular's Vitest builder using `tsconfig.spec.json`. From the root, use `npm run test:ui:unit`.

For integration acceptance, start Compose, verify the health check, hold/release Space in the browser, end the session, and check that `voice_sessions` contains its final byte count and timestamps. Also verify browser microphone permission denial and disconnect/reconnect. Run these against the dedicated local database, never a shared database. Full browser-to-live-server spoken-response and inference latency acceptance remain separate; English recognition and dialog-to-Piper wiring are implemented.

The backend container can be checked independently of PostgreSQL with `docker build -f apps/backend/Dockerfile -t voice-audio-check .`. Browser tests use a simulated server; they do not measure physical echo cancellation, noise reduction, normalization quality, or conversational endpoint accuracy.

Audio integration verification: 12 backend focused tests, 4 Angular unit tests, 4 Playwright capture checks, the frontend production build, Ruff checks, and the backend Docker image build passed. The Linux container also passed a CPU pipeline startup/PCM ingestion/cleanup smoke check. This does not establish full Compose/PostgreSQL integration or acoustic/performance acceptance.

Vosk integration verification: the 12 existing backend focused tests and Ruff checks passed on Windows/Python 3.12 with Vosk 0.3.45 and `vosk-model-small-en-us-0.15`. A separate real-audio processor smoke check confirmed nonempty final transcription frames across two consecutive utterances and no text for silence. Recognition accuracy, performance/concurrency, the updated Linux image, and full Compose/browser integration have not been verified for this change.

Piper implementation verification: existing 12 backend focused checks, 4 Angular unit checks, 4 Playwright capture checks, and the UI production build passed on Windows. A real CPU synthesis smoke check produced PCM and verified interruption gating and worker cleanup. A real WebSocket/Piper check verified welcome audio and start/stop/end (database writes mocked); a separate Chromium smoke check verified PCM scheduling, press interruption, and playback-context cleanup. New automated TTS/playback scenarios belong to the separate test-authoring phase required by the testing skill. The Linux API image build and container CPU synthesis/bounded-PCM/interruption/cleanup smoke check passed with read-only mounted weights. A forced native inference failure produced a safe speech_error notification and muted output. Hardware latency/concurrency, acoustic quality and full browser-to-live-server acceptance remain unverified.

Live dialog-to-Piper verification: `npm run test:backend:focused:dialog` passed 34 checks, `npm run test:backend:focused:voice-capture` passed 12 checks through its isolated capture launcher, `npm run test:ui:unit` passed four checks, and `npm run test:ui:focused:voice-capture` passed four checks. UI build, Ruff and Compose build/startup also passed. Additional smoke checks covered multi-turn speech delivery, terminal playback drain, speech errors and interrupted business calls. An all-real native Vosk/Laya/GLiNER-FP32/dialog/Piper request-to-missing-field-response check passed. Chromium also passed against the real Compose stack with recorded microphone input; the dedicated PostgreSQL database recorded a completed session with nonzero bytes. No insurer endpoint was contacted. See [live voice verification](../docs/dialog-orchestration.md#live-voice-verification) for limits and the observed INT8 extraction regression. These smoke checks do not replace a separately authored persistent dialog browser regression suite.

Claim lookup simplification and Piper duration verification: 34 dialog checks, 12 voice-capture checks and four Playwright capture checks passed. Separate smoke checks exercised both new lookup combinations through DialogSession and the HTTP simulator, rejected incomplete criteria/invalid dates, applied the fresh migration chain through `0004` in isolated SQLite, rejected invalid Piper multipliers and confirmed real CPU synthesis produced longer PCM at `1.3` than `1.0`. These smoke checks do not establish spoken identifier/date recognition accuracy or a persistent regression suite for the new rules.

The updated Compose images built successfully. The verified local `voice` database migrated from `0003` to `0004` after policy export; the API became healthy. Both combinations passed in the Linux container using the stored policy, and real Piper CPU synthesis passed with effective `PIPER_LENGTH_SCALE=1.3`. The ignored local policy backup is excluded from Docker build context.
