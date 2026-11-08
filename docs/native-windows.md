# Native Windows operation

Use Windows 11, Node.js 24, Python 3.12 and an existing local PostgreSQL server. PostgreSQL 18 is installed on the experimental machine. Docker is not required. The default Python 3.14 is not the backend environment.

## Setup and database provisioning

From the repository root:

```powershell
.\scripts\native.ps1 setup
```

Setup creates a Python 3.12 virtual environment, installs CPU PyTorch and application dependencies, runs `npm ci`, and copies `.env.example` only if `.env` does not exist. It does not create databases, run migrations or download models. Install Python 3.12 first, or use `uv`, which can obtain it. Existing environments must use Python 3.12.

Using pgAdmin or `psql -h 127.0.0.1 -U postgres -d postgres`, connect with existing administrator credentials. Run these statements separately, outside a transaction:

```sql
CREATE ROLE voice LOGIN;
```

Set its password interactively with psql's `\password voice`, then run:

```sql
CREATE DATABASE voice OWNER voice;
```

If either name exists, inspect ownership and contents before reusing it; choose fresh names if needed. Set `DATABASE_URL` in ignored `.env` to this dedicated role/database. Percent-encode reserved password characters. Never target `postgres`, template databases or unrelated application databases. No Docker data is imported and old Docker volumes remain untouched.

## Configuration and models

Use `.env.example` as the configuration reference and add missing settings to an existing `.env`. File values override inherited variables. The launcher reads values without shell execution or interpolation. Relative model and debug paths resolve against the repository root. Direct Alembic or Uvicorn commands do not automatically load this configuration.

Prepare the [dialog models](dialog-orchestration.md#local-inference-adapters), selected [speech recognition model](voice-capture.md#english-speech-recognition), and [Piper voice](voice-capture.md#piper-speech-synthesis) before startup. Preparation is a separate explicit network operation. Inspect hardware and available memory first; budget several GB for Parakeet plus dialog models and runtime overhead. Application inference defaults to CPU; Parakeet supports optional [OpenVINO execution](voice-capture.md#optional-intel-openvino-execution). NPU inference remains unverified. No models are downloaded by setup or startup.

Native inspection found a Core Ultra 5 125H, approximately 15.5 GiB RAM, Intel Arc Graphics (driver 32.0.101.5763), and Intel AI Boost. The baseline ONNX runtime exposed CPU and Azure providers. The optional OpenVINO plugin now detects Arc GPU, Intel AI Boost NPU and CPU; Parakeet GPU execution was exercised separately. PyTorch is 2.15.0+cpu. See the [Parakeet verification record](../tests/README.md#parakeet-openvino-verification) for measured acceleration and its limits.

## Lifecycle

```powershell
.\scripts\native.ps1 check
.\scripts\native.ps1 start
.\scripts\native.ps1 stop
.\scripts\native.ps1 restart -WaitTimeoutSeconds 600
```

Commands work from other directories when invoked by absolute path. Root npm aliases are `app:setup`, `app:check`, `app:start`, `app:stop` and `app:restart`.

Start checks the database and model files, rejects occupied ports, prints the target with its password hidden, applies Alembic migrations, starts FastAPI on `127.0.0.1:8000`, waits for API health, and starts Angular on `127.0.0.1:4200`. Open **http://localhost:4200**. Angular proxies `/api` HTTP and WebSocket traffic to FastAPI.

Stop requests graceful Uvicorn shutdown so sessions and inference workers can clean up, then terminates its own frontend process tree. PostgreSQL stays running. Restart ends active calls and repeats migration/startup. Database data, models and debug artifacts are retained. No automatic rollback is attempted; back up important data before migrations.

Private logs and authenticated supervisor state live in ignored `.local-run/`. Inspect `application.log` after failures. Startup timeout requests graceful shutdown; native inference may still be finishing. An unreachable supervisor never causes automatic process termination. Verify the previous application exited before removing stale `state.json` and retrying. Do not run simultaneous lifecycle commands.

Migrations own the single application schema: `0001` creates session metadata, `0002` adds dialog policy, `0003` seeds Claim Status, and `0004` simplifies lookup rules. Startup never creates tables implicitly. No tenant schemas exist.

The experimental template enables latest-session recording in ignored `session-debug/`. Disable `SESSION_DEBUG_ENABLED` when recordings are unwanted. The unauthenticated application binds to loopback; localhost supports browser microphone access. Windows services and remote hosting are outside this workflow.

## Verification

Run existing commands in the [test guide](../tests/README.md). Isolated SQLite and mocked browser checks do not establish real PostgreSQL, real-model or acoustic acceptance. Verify native welcome/reply playback, interruption, stop/reconnect and session persistence separately. Record unverified checks explicitly. Previous container results are historical evidence only.
