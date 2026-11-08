"""Seed Claim Status in the shared application policy; preserve operator configuration."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SEED = {
    "intents": [
        {
            "name": "WELCOME",
            "type": "General",
            "description": "Greeting or start of a call",
            "responses": [
                "Welcome. I can help you check a claim status. Are you calling as a member or a provider?"
            ],
        },
        {
            "name": "CLAIM_STATUS",
            "type": "Business",
            "description": "Claim Status: check insurance claim status, payment, denial or pending information for a member or provider.",
            "fields": [
                {
                    "name": "callerType",
                    "label": "caller type MEMBER or PROVIDER",
                    "normalize": "upper",
                },
                {"name": "claimNumber", "label": "claim number", "normalize": "strip"},
                {"name": "memberId", "label": "member identifier", "normalize": "strip"},
                {"name": "dateOfBirth", "label": "date of birth YYYY-MM-DD", "normalize": "strip"},
                {
                    "name": "dateOfService",
                    "label": "date of service YYYY-MM-DD",
                    "normalize": "strip",
                },
                {"name": "providerNpi", "label": "provider NPI", "normalize": "digits"},
                {"name": "taxId", "label": "provider tax identifier", "normalize": "strip"},
                {"name": "authCode", "label": "IVR validation token", "normalize": "strip"},
                {
                    "name": "searchType",
                    "label": "search type SPECIFIC_CLAIM or RECENT_CLAIMS",
                    "normalize": "upper",
                },
                {"name": "maxResults", "label": "maximum results", "normalize": "digits"},
            ],
            "rules": [
                {
                    "conditions": [
                        {"field": "callerType", "operator": "equals", "value": "MEMBER"},
                        {"field": "claimNumber", "operator": "present"},
                        {"field": "memberId", "operator": "present"},
                        {
                            "field": "dateOfBirth",
                            "operator": "matches",
                            "value": "\\d{4}-\\d{2}-\\d{2}",
                        },
                    ]
                },
                {
                    "conditions": [
                        {"field": "callerType", "operator": "equals", "value": "MEMBER"},
                        {"field": "memberId", "operator": "present"},
                        {
                            "field": "dateOfBirth",
                            "operator": "matches",
                            "value": "\\d{4}-\\d{2}-\\d{2}",
                        },
                        {
                            "field": "dateOfService",
                            "operator": "matches",
                            "value": "\\d{4}-\\d{2}-\\d{2}",
                        },
                    ]
                },
                {
                    "conditions": [
                        {"field": "callerType", "operator": "equals", "value": "PROVIDER"},
                        {"field": "providerNpi", "operator": "matches", "value": "\\d{10}"},
                        {"field": "taxId", "operator": "present"},
                        {"field": "claimNumber", "operator": "present"},
                    ]
                },
            ],
            "api": {
                "endpoint": "claim_status",
                "method": "GET",
                "query": {"callerType": "callerType"},
                "optional_query": {
                    "claimNumber": "claimNumber",
                    "memberId": "memberId",
                    "dateOfBirth": "dateOfBirth",
                    "dateOfService": "dateOfService",
                    "providerNpi": "providerNpi",
                    "taxId": "taxId",
                    "authCode": "authCode",
                    "searchType": "searchType",
                    "maxResults": "maxResults",
                },
                "response": {
                    "status": "claims.0.claimStatusSpeechText",
                    "claim_number": "claims.0.claimNumber",
                },
            },
            "missing_template": "To check your claim status, please provide or correct: {missing_fields}. Use MEMBER or PROVIDER for callerType, ten digits for providerNpi, and YYYY-MM-DD for dates.",
            "responses": ["This is a simulated claim lookup. Claim {claim_number}. {status}"],
            "next_intent": "END",
        },
        {
            "name": "END",
            "type": "General",
            "description": "End the conversation or say goodbye",
            "responses": ["Thank you for calling. Goodbye."],
        },
    ]
}


def upgrade():
    """Add missing seed intents and refresh untouched default scripts."""
    policy = sa.table(
        "dialog_policy", sa.column("id", sa.Integer), sa.column("configuration", sa.JSON)
    )
    connection = op.get_bind()
    config = connection.execute(
        sa.select(policy.c.configuration).where(policy.c.id == 1)
    ).scalar_one()
    config = dict(config)
    intents = list(config.get("intents", []))
    originals = {"WELCOME": "Welcome. How can I help you?", "END": "Goodbye."}
    for intent in intents:
        if intent.get("responses") == [originals.get(intent["name"])]:
            replacement = next(i for i in SEED["intents"] if i["name"] == intent["name"])
            intent["responses"] = replacement["responses"]
    names = {intent["name"] for intent in intents}
    for intent in SEED["intents"]:
        if intent["name"] not in names:
            intents.append(intent)
    config["intents"] = intents
    connection.execute(policy.update().where(policy.c.id == 1).values(configuration=config))


def downgrade():
    """Preserve operator-owned policy data when reverting the revision."""
    # Policy is operator-owned data. Keep seeded/customized intents on downgrade.
    pass
