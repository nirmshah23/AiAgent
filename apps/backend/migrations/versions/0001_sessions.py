"""Create session metadata in the single application database."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create the application session metadata table."""
    op.create_table(
        "voice_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("audio_bytes", sa.Integer(), nullable=False),
        sa.CheckConstraint("audio_bytes >= 0"),
    )


def downgrade():
    """Remove the table and all stored session metadata."""
    op.drop_table("voice_sessions")
