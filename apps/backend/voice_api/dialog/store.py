"""Single-application-database dialog policy snapshots and operator CLI."""

import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import JSON, CheckConstraint, Integer, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from ..database import Base, make_engine
from .config import DialogConfig


class DialogPolicy(Base):
    """One validated JSON policy; no transcripts, API credentials or caller entities."""

    __tablename__ = "dialog_policy"
    __table_args__ = (CheckConstraint("id = 1", name="dialog_policy_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)


def load_config(engine) -> DialogConfig:
    """Read and validate policy within a short transaction."""
    with sessionmaker(engine)() as db:
        record = db.get(DialogPolicy, 1)
        if record is None:
            raise ValueError("Dialog policy missing; apply Alembic migrations")
        return DialogConfig.model_validate(record.configuration)


def revision(config: DialogConfig) -> str:
    """Stable content revision shared by CLI and browser policy snapshots."""
    return hashlib.sha256(
        json.dumps(config.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()


class PolicyConflict(ValueError):
    """The submitted snapshot is no longer current."""


def save_config(engine, config: DialogConfig, expected_revision: str | None = None):
    """Replace the policy atomically; connected calls retain their own snapshot."""
    with sessionmaker(engine).begin() as db:
        record = db.scalar(select(DialogPolicy).where(DialogPolicy.id == 1).with_for_update())
        if record is None:
            raise ValueError("Dialog policy missing; apply Alembic migrations")
        if (
            expected_revision is not None
            and revision(DialogConfig.model_validate(record.configuration)) != expected_revision
        ):
            raise PolicyConflict("Policy changed; reload before saving")
        record.configuration = config.model_dump(mode="json")


def main():
    """Export or import configuration from the operator command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "import"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    config = (
        DialogConfig.model_validate_json(args.path.read_text(encoding="utf-8"))
        if args.action == "import"
        else None
    )
    engine = make_engine()
    try:
        print("Dialog policy target:", engine.url.render_as_string(hide_password=True))
        if config is not None:
            save_config(engine, config)
        else:
            args.path.write_text(
                json.dumps(load_config(engine).model_dump(mode="json"), indent=2) + "\n",
                encoding="utf-8",
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
