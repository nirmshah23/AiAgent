"""Serve the real policy API on a disposable SQLite database, without inference."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps/backend"))
from voice_api.database import Base  # noqa: E402
from voice_api.dialog.config import DialogConfig  # noqa: E402
from voice_api.dialog.store import DialogPolicy  # noqa: E402
from voice_api.main import app  # noqa: E402

with TemporaryDirectory(prefix="policy-browser-") as folder:
    engine = create_engine(f"sqlite:///{Path(folder) / 'policy.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        db.add(DialogPolicy(id=1, configuration=DialogConfig().model_dump(mode="json")))
    app.state.engine = engine
    app.state.dialog = None
    import os

    os.environ["ALLOWED_ORIGINS"] = "http://localhost:4211"
    try:
        uvicorn.run(app, host="127.0.0.1", port=8011, lifespan="off")
    finally:
        engine.dispose()
