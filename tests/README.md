# Test discovery and execution

Dialog engine checks are discovered under `tests/backend/focused/dialog/test_*.py`. Run `npm run test:backend:focused:dialog` from the root; its launcher is `tests/scripts/backend/start_backend_focused_dialog.ps1`. On Linux use `apps/backend/.venv/bin/python -m pytest -c tests/backend/pytest.ini --confcutdir=tests/backend tests/backend/focused/dialog`. Install the base backend requirements and pytest/httpx/ruff first. These checks use fake model adapters, mocked HTTP and isolated SQLite, including policy persistence and migration upgrade/downgrade. They do not verify real model inference, PostgreSQL, voice playback or latency. Optional model packages install from `apps/backend/requirements-dialog.txt`; see [dialog setup](../docs/dialog-orchestration.md).

Dialog increment verification: 34 focused dialog tests, the 12 existing voice-capture tests, Ruff lint/format checks and example-policy validation passed on Windows/Python 3.12. Optional model package installation and concrete runtime-interface inspection also passed. Model weights/inference, INT8 quality, performance, live PostgreSQL migration and Linux container integration remain unverified. No browser behavior changed.

For both application backend modules, run `apps/backend/.venv/Scripts/python.exe -m pytest -c tests/backend/pytest.ini --confcutdir=tests/backend tests/backend/focused` on Windows (substitute `.venv/bin/python` on Linux). Lint/format checks apply to `apps/backend` and `tests/backend/focused`.

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

Backend tests are discovered under `tests/backend/focused/voice_capture/test_*.py`. Browser tests are discovered under `tests/user_interface/focused/voice_capture/*.spec.ts` by `apps/frontend/playwright.config.ts`. Screenshots and reports are untracked under `apps/frontend/test-results`. Protocol tests replace metadata writes and must not be described as persistence integration tests. The same focused suite includes real bundled CPU Silero/Smart Turn inference using a recorded 16 kHz speech fixture, checks turn events and analyzer cleanup, and rejects raw audio logging. The real pipeline now also requires the English Vosk model described in [setup](../docs/voice-capture.md#english-speech-recognition). It exercises recognition ingestion alongside audio analysis; it does not assert transcription accuracy or run an LLM or synthesis. No performance benchmark or full speech workflow suite exists yet.

Root package scripts provide `build:ui`, `test:backend:focused:voice-capture`, and `test:ui:focused:voice-capture`. The backend script uses the Windows virtual environment executable. On Linux invoke `apps/backend/.venv/bin/python -m pytest -c tests/backend/pytest.ini --confcutdir=tests/backend tests/backend/focused/voice_capture` instead. The dedicated pytest configuration avoids inheriting upstream Pipecat fixture and plugin requirements.

Angular unit tests are colocated as `src/app/*.spec.ts`, run by Angular's Vitest builder using `tsconfig.spec.json`. From the root, use `npm run test:ui:unit`.

For integration acceptance, start Compose, verify the health check, hold/release Space in the browser, end the session, and check that `voice_sessions` contains its final byte count and timestamps. Also verify browser microphone permission denial and disconnect/reconnect. Run these against the dedicated local database, never a shared database. Full spoken response and inference latency checks remain pending; English speech recognition is integrated.

The backend container can be checked independently of PostgreSQL with `docker build -f apps/backend/Dockerfile -t voice-audio-check .`. Browser tests use a simulated server; they do not measure physical echo cancellation, noise reduction, normalization quality, or conversational endpoint accuracy.

Audio integration verification: 12 backend focused tests, 4 Angular unit tests, 4 Playwright capture checks, the frontend production build, Ruff checks, and the backend Docker image build passed. The Linux container also passed a CPU pipeline startup/PCM ingestion/cleanup smoke check. This does not establish full Compose/PostgreSQL integration or acoustic/performance acceptance.

Vosk integration verification: the 12 existing backend focused tests and Ruff checks passed on Windows/Python 3.12 with Vosk 0.3.45 and `vosk-model-small-en-us-0.15`. A separate real-audio processor smoke check confirmed nonempty final transcription frames across two consecutive utterances and no text for silence. Recognition accuracy, performance/concurrency, the updated Linux image, and full Compose/browser integration have not been verified for this change.
