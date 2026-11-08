"""Replace the demo lookup rules in the shared application policy; no schema changes."""

import json

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

SEED = json.loads(r"""
{
  "intents": [
    {
      "name": "WELCOME",
      "type": "General",
      "description": "Greeting or start of a call",
      "responses": [
        "Welcome. I can help you check a claim status. Please provide your claim number. If you do not have it, provide your member ID, date of birth and date of service."
      ]
    },
    {
      "name": "CLAIM_STATUS",
      "type": "Business",
      "description": "Claim Status: check insurance claim status, payment, denial or pending information using a claim number or member details.",
      "fields": [
        {
          "name": "claimNumber",
          "label": "claim number",
          "normalize": "strip"
        },
        {
          "name": "memberId",
          "label": "member identifier",
          "normalize": "strip"
        },
        {
          "name": "dateOfBirth",
          "label": "date of birth YYYY-MM-DD",
          "normalize": "strip"
        },
        {
          "name": "dateOfService",
          "label": "date of service YYYY-MM-DD",
          "normalize": "strip"
        }
      ],
      "rules": [
        {
          "conditions": [
            {
              "field": "claimNumber",
              "operator": "present"
            }
          ]
        },
        {
          "conditions": [
            {
              "field": "memberId",
              "operator": "present"
            },
            {
              "field": "dateOfBirth",
              "operator": "matches",
              "value": "\\d{4}-\\d{2}-\\d{2}"
            },
            {
              "field": "dateOfService",
              "operator": "matches",
              "value": "\\d{4}-\\d{2}-\\d{2}"
            }
          ]
        }
      ],
      "api": {
        "endpoint": "claim_status",
        "method": "GET",
        "query": {},
        "optional_query": {
          "claimNumber": "claimNumber",
          "memberId": "memberId",
          "dateOfBirth": "dateOfBirth",
          "dateOfService": "dateOfService"
        },
        "response": {
          "status": "claims.0.claimStatusSpeechText",
          "claim_number": "claims.0.claimNumber"
        }
      },
      "missing_template": "Please provide your claim number, or your member ID, date of birth and date of service. Use YYYY-MM-DD for dates.",
      "responses": [
        "This is a simulated claim lookup. Claim {claim_number}. {status}"
      ],
      "next_intent": "END"
    },
    {
      "name": "END",
      "type": "General",
      "description": "End the conversation or say goodbye",
      "responses": [
        "Thank you for calling. Goodbye."
      ]
    }
  ]
}
""")


def upgrade():
    """Update only claim/welcome policy; preserve other intents and global settings."""
    policy = sa.table(
        "dialog_policy", sa.column("id", sa.Integer), sa.column("configuration", sa.JSON)
    )
    connection = op.get_bind()
    config = dict(
        connection.execute(sa.select(policy.c.configuration).where(policy.c.id == 1)).scalar_one()
    )
    replacements = {i["name"]: i for i in SEED["intents"] if i["name"] != "END"}
    intents = [replacements.pop(i["name"], i) for i in config.get("intents", [])]
    config["intents"] = intents + list(replacements.values())
    connection.execute(policy.update().where(policy.c.id == 1).values(configuration=config))


def downgrade():
    """Retain operator-owned policy data; export/import is the policy recovery path."""
    pass
