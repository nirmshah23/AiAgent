"""Repository-local Windows lifecycle; never stop unrelated processes or PostgreSQL."""

import argparse
import hmac
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/backend"
RUNTIME = ROOT / ".local-run"
STATE = RUNTIME / "state.json"


def configure():
    from dotenv import dotenv_values

    if sys.version_info[:2] != (3, 12):
        raise ValueError("Use the Python 3.12 backend virtual environment")
    if not (ROOT / ".env").is_file():
        raise ValueError("Create .env from .env.example first")
    values = dotenv_values(ROOT / ".env", interpolate=False)
    os.environ.update({key: value for key, value in values.items() if value is not None})
    for key in (
        "PARAKEET_MODEL_PATH",
        "VOSK_MODEL_PATH",
        "PIPER_MODEL_PATH",
        "LAYA_MODEL_PATH",
        "GLINER_MODEL_PATH",
        "SESSION_DEBUG_DIR",
    ):
        if os.getenv(key):
            os.environ[key] = str((ROOT / os.environ[key]).resolve())
    if not os.getenv("DATABASE_URL"):
        raise ValueError("Set DATABASE_URL in .env")
    sys.path.insert(0, str(BACKEND))


def check():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(os.environ["DATABASE_URL"])
    if url.drivername != "postgresql+psycopg" or url.database in {
        None,
        "postgres",
        "template0",
        "template1",
    }:
        raise ValueError("DATABASE_URL must target a dedicated PostgreSQL application database")
    print("Database target:", url.render_as_string(hide_password=True), flush=True)
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            target = connection.execute(text("select current_database(), current_user")).one()
            print("Connected database/role:", *target, flush=True)
    except Exception:
        raise ValueError(
            "PostgreSQL connection failed; check service, database, role and .env credentials"
        ) from None
    finally:
        engine.dispose()
    provider = os.getenv("STT_PROVIDER", "parakeet")
    if provider not in {"parakeet", "vosk"}:
        raise ValueError("STT_PROVIDER must be parakeet or vosk")
    required = {"PIPER_MODEL_PATH": ["", ".json"]}
    required["PARAKEET_MODEL_PATH" if provider == "parakeet" else "VOSK_MODEL_PATH"] = (
        [
            "config.json",
            "vocab.txt",
            "encoder-model.onnx",
            "encoder-model.onnx.data",
            "decoder_joint-model.onnx",
        ]
        if provider == "parakeet"
        else ["am/final.mdl"]
    )
    if os.getenv("DIALOG_ENABLED", "true").lower() == "true":
        required.update(
            {"LAYA_MODEL_PATH": ["config.json"], "GLINER_MODEL_PATH": ["gliner_config.json"]}
        )
    for key, files in required.items():
        path = Path(os.environ.get(key, "__missing__"))
        for name in files:
            candidate = Path(str(path) + name) if key == "PIPER_MODEL_PATH" else path / name
            if not candidate.is_file():
                raise ValueError(f"Missing prepared model artifact for {key}: {candidate}")
    if provider == "parakeet":
        from voice_api.parakeet_stt import runtime_config

        threads, backend, device, precision = runtime_config()
        print(
            f"Parakeet requested backend={backend}, device={device if backend == 'openvino' else 'CPU'}, "
            f"precision={precision if backend == 'openvino' else 'FP32'}, CPU threads={threads}. "
            "Actual providers and any CPU fallback are logged at model initialization.",
            flush=True,
        )
    print("Prepared model files found.", flush=True)


def control(action):
    state = json.loads(STATE.read_text())
    request = Request(
        f"http://127.0.0.1:{state['port']}/{action}",
        headers={"Authorization": state["token"]},
        method="POST",
    )
    with urlopen(request, timeout=3) as response:
        return response.read()


def stop(timeout):
    if not STATE.exists():
        print("Application is already stopped.")
        return
    try:
        control("stop")
    except OSError:
        raise ValueError(
            "Supervisor is unreachable. Inspect .local-run logs; no process was killed."
        ) from None
    deadline = time.monotonic() + timeout
    while STATE.exists():
        if time.monotonic() > deadline:
            raise ValueError(
                "Graceful shutdown timed out; no forced backend termination was attempted"
            )
        time.sleep(0.2)
    print("Application stopped; PostgreSQL remains running.")


def supervise(timeout):
    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(
            "voice_api.main:app",
            host="127.0.0.1",
            port=8000,
            ws_max_size=16384,
        )
    )
    token = secrets.token_urlsafe(32)
    frontend = None
    stopping = threading.Event()

    class Control(BaseHTTPRequestHandler):
        def do_POST(self):
            if not hmac.compare_digest(self.headers.get("Authorization", ""), token):
                self.send_error(403)
                return
            if self.path == "/stop":
                stopping.set()
                server.should_exit = True
            elif self.path != "/status":
                self.send_error(404)
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Control)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    STATE.write_text(json.dumps({"port": http.server_port, "token": token}))

    def launch_frontend():
        nonlocal frontend
        deadline = time.monotonic() + timeout
        while not stopping.is_set() and time.monotonic() < deadline:
            try:
                with urlopen("http://127.0.0.1:8000/api/v1/health", timeout=2):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            server.should_exit = True
            return
        if stopping.is_set():
            return
        try:
            frontend = subprocess.Popen(
                [
                    shutil.which("node") or "node",
                    str(ROOT / "apps/frontend/node_modules/@angular/cli/bin/ng.js"),
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--proxy-config",
                    "proxy.json",
                ],
                cwd=ROOT / "apps/frontend",
                shell=False,
            )
        except OSError:
            print("Frontend launch failed; check Node.js and run setup.", flush=True)
            server.should_exit = True
            return
        while not stopping.wait(0.5):
            if frontend.poll() is not None:
                server.should_exit = True
                return

    monitor = threading.Thread(target=launch_frontend, daemon=True)
    monitor.start()
    try:
        server.run()
    finally:
        stopping.set()
        monitor.join(timeout=5)
        if frontend is not None and frontend.poll() is None:
            subprocess.run(["taskkill", "/PID", str(frontend.pid), "/T", "/F"], check=False)
            frontend.wait(timeout=15)
        http.shutdown()
        http.server_close()
        STATE.unlink(missing_ok=True)


def start(timeout):
    if STATE.exists():
        control("status")
        print("Application supervisor is already running.")
        return
    configure()
    check()
    if not (ROOT / "apps/frontend/node_modules/@angular/cli/bin/ng.js").is_file():
        raise ValueError("Frontend dependencies missing; run setup first")
    for port in (8000, 4200):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise ValueError(
                    f"Port {port} is occupied; stop its owner before starting"
                ) from None
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True)
    RUNTIME.mkdir(exist_ok=True)
    with (RUNTIME / "application.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "supervise", "--timeout", str(timeout)],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError("Application startup failed; inspect .local-run/application.log")
        try:
            with urlopen("http://127.0.0.1:4200", timeout=2):
                with urlopen("http://127.0.0.1:8000/api/v1/health", timeout=2):
                    print("Application ready: http://localhost:4200")
                    return
        except OSError:
            time.sleep(0.5)
    if STATE.exists():
        control("stop")
    raise ValueError(
        "Startup timed out; graceful shutdown requested. Inspect .local-run/application.log"
    )


def main():
    import msvcrt

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "restart", "check", "supervise"])
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.action == "supervise":
        configure()
        supervise(args.timeout)
        return
    RUNTIME.mkdir(exist_ok=True)
    with (RUNTIME / "command.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise ValueError(
                "Another lifecycle command is running; wait for it to finish"
            ) from None
        try:
            if args.action in {"stop", "restart"}:
                stop(args.timeout)
            if args.action in {"start", "restart"}:
                start(args.timeout)
            elif args.action == "check":
                configure()
                check()
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Native workflow failed: {error}", file=sys.stderr)
        sys.exit(1)
