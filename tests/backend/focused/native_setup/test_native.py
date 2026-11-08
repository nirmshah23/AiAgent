"""Native launcher safety and configuration checks without a deployment database."""

import importlib.util
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

SOURCE = Path(__file__).resolve().parents[4] / "scripts/native.py"


@pytest.fixture
def native(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("native_workflow", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.os, "environ", module.os.environ.copy())
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "RUNTIME", tmp_path)
    monkeypatch.setattr(module, "STATE", tmp_path / "state.json")
    return module


def test_configuration_requires_file(native):
    with pytest.raises(ValueError, match="Create .env"):
        native.configure()


def test_configuration_preserves_literal_values_and_resolves_paths(native, monkeypatch):
    (native.ROOT / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg://voice:secret@localhost/voice\n"
        "PARAKEET_MODEL_PATH=models/parakeet\nSESSION_DEBUG_DIR=session-debug\n"
        "BUSINESS_API_HEADERS=${DO_NOT_EXPAND}\n"
    )
    monkeypatch.setenv("DATABASE_URL", "inherited")
    monkeypatch.setattr(sys, "path", sys.path.copy())
    native.configure()
    assert native.os.environ["DATABASE_URL"].endswith("localhost/voice")
    assert Path(native.os.environ["PARAKEET_MODEL_PATH"]) == native.ROOT / "models/parakeet"
    assert native.os.environ["BUSINESS_API_HEADERS"] == "${DO_NOT_EXPAND}"


@pytest.mark.parametrize("database", ["postgres", "template0", "template1"])
def test_system_database_is_rejected_before_connect(native, monkeypatch, database):
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://voice:hidden@localhost/{database}")
    with pytest.raises(ValueError, match="dedicated"):
        native.check()


def test_failed_connection_does_not_disclose_credentials(native, monkeypatch, capsys):
    import sqlalchemy

    def fail(*_args, **_kwargs):
        raise RuntimeError("sensitive password")

    engine = SimpleNamespace(connect=fail, dispose=lambda: None)
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://voice:private-password@localhost/voice"
    )
    with pytest.raises(ValueError, match="PostgreSQL connection failed") as failure:
        native.check()
    assert "private-password" not in capsys.readouterr().out
    assert "sensitive password" not in str(failure.value)


def test_missing_model_prevents_start_before_migrations(native, monkeypatch):
    monkeypatch.setattr(native, "configure", lambda: None)

    def missing():
        raise ValueError("Missing prepared model artifact")

    monkeypatch.setattr(native, "check", missing)
    monkeypatch.setattr(native.subprocess, "run", lambda *_a, **_k: pytest.fail("migration ran"))
    with pytest.raises(ValueError, match="Missing prepared model"):
        native.start(1)


def test_stop_is_idempotent_when_no_supervisor_exists(native, capsys):
    native.stop(1)
    native.stop(1)
    assert capsys.readouterr().out.count("already stopped") == 2


def test_unreachable_supervisor_never_kills_a_process(native, monkeypatch):
    native.STATE.write_text("{}")

    def unreachable(_action):
        raise OSError("connection refused")

    monkeypatch.setattr(native, "control", unreachable)
    monkeypatch.setattr(native.subprocess, "run", lambda *_a, **_k: pytest.fail("process killed"))
    with pytest.raises(ValueError, match="no process was killed"):
        native.stop(1)
    assert native.STATE.exists()


def test_occupied_port_prevents_migration(native, monkeypatch):
    monkeypatch.setattr(native, "configure", lambda: None)
    monkeypatch.setattr(native, "check", lambda: None)
    cli = native.ROOT / "apps/frontend/node_modules/@angular/cli/bin/ng.js"
    cli.parent.mkdir(parents=True)
    cli.touch()
    monkeypatch.setattr(native.subprocess, "run", lambda *_a, **_k: pytest.fail("migration ran"))
    with socket.socket() as occupied:
        try:
            occupied.bind(("127.0.0.1", 8000))
        except OSError:
            pass  # An existing listener also satisfies the occupied-port scenario.
        with pytest.raises(ValueError, match="Port 8000 is occupied"):
            native.start(1)


def test_authenticated_control_requests_graceful_backend_shutdown(native, monkeypatch):
    class FakeServer:
        should_exit = False

        def __init__(self, _config):
            pass

        def run(self):
            state = json.loads(native.STATE.read_text())
            bad = Request(f"http://127.0.0.1:{state['port']}/stop", method="POST")
            with pytest.raises(HTTPError) as error:
                urlopen(bad, timeout=2)
            assert error.value.code == 403
            assert not self.should_exit
            assert native.control("stop") == b"ok"
            assert self.should_exit

    monkeypatch.setitem(
        sys.modules, "uvicorn", SimpleNamespace(Server=FakeServer, Config=lambda *_a, **_k: None)
    )
    native.supervise(1)
    assert not native.STATE.exists()


def test_startup_timeout_requests_stop_without_forcing_backend(native, monkeypatch):
    monkeypatch.setattr(native, "configure", lambda: None)
    monkeypatch.setattr(native, "check", lambda: None)
    cli = native.ROOT / "apps/frontend/node_modules/@angular/cli/bin/ng.js"
    cli.parent.mkdir(parents=True)
    cli.touch()

    # A real socket context is unnecessary: port validation is covered separately.
    class AvailablePort:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def bind(self, _address):
            pass

    monkeypatch.setattr(native.socket, "socket", AvailablePort)
    monkeypatch.setattr(native.subprocess, "run", lambda *_a, **_k: None)

    def spawn(*_args, **_kwargs):
        native.STATE.write_text("{}")
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr(native.subprocess, "Popen", spawn)
    clock = iter([0, 0, 2])
    monkeypatch.setattr(native.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(native.time, "sleep", lambda _seconds: None)

    def unavailable(*_a, **_k):
        raise OSError("not ready")

    monkeypatch.setattr(native, "urlopen", unavailable)
    actions = []
    monkeypatch.setattr(native, "control", actions.append)
    with pytest.raises(ValueError, match="Startup timed out"):
        native.start(1)
    assert actions == ["stop"]


def test_repeated_start_checks_owned_supervisor_without_migration(native, monkeypatch):
    native.STATE.write_text("{}")
    actions = []
    monkeypatch.setattr(native, "control", actions.append)
    monkeypatch.setattr(native, "configure", lambda: pytest.fail("started twice"))
    native.start(1)
    assert actions == ["status"]
