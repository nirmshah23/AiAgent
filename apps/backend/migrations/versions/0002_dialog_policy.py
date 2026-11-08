"""Add dialog configuration to the single shared application database."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    """Create a policy without changing session metadata or persisting caller content."""
    policy = op.create_table(
        "dialog_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.CheckConstraint("id = 1", name="dialog_policy_singleton"),
    )
    op.bulk_insert(
        policy,
        [
            {
                "id": 1,
                "configuration": {
                    "intents": [
                        {
                            "name": "WELCOME",
                            "type": "General",
                            "description": "Greeting or start of a call",
                            "responses": ["Welcome. How can I help you?"],
                        },
                        {
                            "name": "END",
                            "type": "General",
                            "description": "End the conversation or say goodbye",
                            "responses": ["Goodbye."],
                        },
                    ],
                },
            }
        ],
    )


def downgrade():
    """Remove configured dialog policy (destructive)."""
    op.drop_table("dialog_policy")
