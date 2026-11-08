"""Single-database session metadata and short-lived transactions."""

import os
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """Application metadata registry owned by Alembic."""


class VoiceSession(Base):
    """Connection summary containing no audio or transcript."""

    __tablename__ = "voice_sessions"
    __table_args__ = (CheckConstraint("audio_bytes >= 0"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))
    audio_bytes: Mapped[int] = mapped_column(Integer, default=0)


def make_engine():
    """Build a bounded connection pool for the explicitly configured database."""
    return create_engine(
        os.environ["DATABASE_URL"], pool_pre_ping=True, pool_size=5, max_overflow=5
    )


def save_session(engine, session_id, started_at, audio_bytes, status):
    """Persist the final connection summary in one transaction."""
    # A short transaction after streaming; no connection is held while listening.
    with sessionmaker(engine).begin() as db:
        db.add(
            VoiceSession(
                id=session_id,
                started_at=started_at,
                ended_at=datetime.now().astimezone(),
                status=status,
                audio_bytes=audio_bytes,
            )
        )
