"""Dialog behavior checks using deterministic inference and isolated persistence."""

import asyncio
import importlib.util
import sys
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps/backend"))
from voice_api.database import Base  # noqa: E402
from voice_api.dialog.api import BusinessAPI  # noqa: E402
from voice_api.dialog.config import APIContract, DialogConfig, Intent  # noqa: E402
from voice_api.dialog.engine import DialogSession, missing_fields  # noqa: E402
from voice_api.dialog.store import DialogPolicy, load_config, save_config  # noqa: E402
from voice_api.dialog.voice_bridge import DialogVoiceBridge  # noqa: E402


def business(name="LOOKUP", **kwargs):
    return Intent(name=name, type="Business", description="Look up an order", **kwargs)


def config(*intents, **kwargs):
    return DialogConfig(intents=DialogConfig().intents + list(intents), **kwargs)


class Inference:
    def __init__(self, scores=None):
        self.scores = scores or {"LOOKUP": 0.95}
        self.classifications = []
        self.extractions = []

    async def classify(self, text, intents):
        self.classifications.append(text)
        return self.scores

    async def extract(self, history, intent):
        self.extractions.append((history.copy(), intent.name))
        values = {}
        for text in history:
            for token in text.split():
                if "=" in token:
                    key, value = token.split("=", 1)
                    if key in {f.name for f in intent.fields}:
                        values[key] = value
        return values


class API:
    def __init__(self):
        self.calls = []

    async def call(self, contract, values):
        self.calls.append((contract.endpoint, values.copy()))
        return {"status": "shipped"}


def lookup(**kwargs):
    return business(
        fields=[{"name": "order_id"}, {"name": "email"}, {"name": "postcode"}],
        rules=[
            {"conditions": [{"field": "order_id"}]},
            {"conditions": [{"field": "email"}, {"field": "postcode"}]},
        ],
        **kwargs,
    )


def test_alternative_rules_and_minimum_missing_fields():
    intent = lookup()
    assert missing_fields(intent, {}) == ["order_id"]
    assert missing_fields(intent, {"order_id": "42"}) == []
    assert missing_fields(intent, {"email": "a@b.com", "postcode": "400001"}) == []
    assert missing_fields(intent, {"email": "a@b.com"}) == ["order_id"]
    assert missing_fields(business(), {}) == []


def test_api_bindings_participate_in_minimum_selection():
    intent = lookup(api=APIContract(endpoint="orders", query={"email": "email", "zip": "postcode"}))
    assert missing_fields(intent, {}) == ["email", "postcode"]


@pytest.mark.parametrize(
    "condition,valid,invalid",
    [
        ({"operator": "equals", "value": "yes"}, "yes", "no"),
        ({"operator": "one_of", "value": ["yes", "ok"]}, "ok", "no"),
        ({"operator": "matches", "value": r"\d{4}"}, "1234", "123"),
    ],
)
def test_rule_predicates_reject_invalid_values(condition, valid, invalid):
    intent = business(
        fields=[{"name": "answer"}],
        rules=[
            {
                "conditions": [{"field": "answer", **condition}],
            }
        ],
    )
    assert missing_fields(intent, {"answer": valid}) == []
    assert missing_fields(intent, {"answer": invalid}) == ["answer"]


def test_missing_followup_preserves_intents_history_and_defers_all_apis():
    async def scenario():
        inference = Inference({"LOOKUP": 0.99, "SECOND": 0.98})
        api = API()
        policy = config(
            lookup(
                api=APIContract(
                    endpoint="orders", query={"id": "order_id"}, response={"status": "status"}
                ),
                responses=["Your order is {status}."],
            ),
            business(
                "SECOND",
                fields=[{"name": "phone"}],
                rules=[{"conditions": [{"field": "phone"}]}],
                responses=["Thank you."],
            ),
        )
        session = DialogSession(policy, inference, inference, api)
        assert session.welcome().texts == ["Welcome. How can I help you?"]
        assert session.welcome().texts == []
        first = await session.respond("look up my order")
        assert first.missing == {"LOOKUP": ["order_id"], "SECOND": ["phone"]}
        assert api.calls == []
        second = await session.respond("order_id=42")
        assert second.missing == {"SECOND": ["phone"]}
        assert api.calls == []
        third = await session.respond("phone=123")
        assert third.status == "complete"
        assert third.texts == ["Your order is shipped.", "Thank you."]
        assert api.calls == [("orders", {"order_id": "42"})]
        assert len(inference.classifications) == 3
        assert inference.extractions[-1][0] == ["look up my order", "order_id=42", "phone=123"]
        session.close()
        assert session.history == []

    asyncio.run(scenario())


def test_threshold_is_strict_and_clarification_accumulates_history():
    async def scenario():
        inference = Inference({"LOOKUP": 0.8, "INVENTED": 1})
        session = DialogSession(config(business()), inference, inference, API())
        assert (await session.respond("something")).status == "clarify"
        inference.scores = {"LOOKUP": 0.81}
        assert (await session.respond("order lookup")).status == "complete"
        assert inference.classifications == ["something", "something\norder lookup"]

    asyncio.run(scenario())


def test_followup_merges_new_intents_without_erasing_existing_pending_work():
    async def scenario():
        inference = Inference()
        session = DialogSession(
            config(lookup(), business("SECOND", responses=["Second done."])),
            inference,
            inference,
            API(),
        )
        assert (await session.respond("lookup")).missing == {"LOOKUP": ["order_id"]}
        inference.scores = {"SECOND": 0.99, "LOOKUP": 0.01}
        reply = await session.respond("order_id=42 and second request")
        assert reply.status == "complete"
        assert reply.texts == ["Second done."]
        assert session.completed == {"LOOKUP", "SECOND"}
        assert (await session.respond("duplicate")).status == "ended"

    asyncio.run(scenario())


def test_bridge_model_failure_uses_safe_script_and_discards_caller_data():
    async def scenario():
        class FailedInference(Inference):
            async def classify(self, *_):
                raise ValueError("private caller content")

        inference = FailedInference()
        session = DialogSession(config(business()), inference, inference, API())
        spoken = []

        async def speak(text):
            spoken.append(text)

        bridge = DialogVoiceBridge(session, speak)
        assert (await bridge.caller_turn("sensitive text")).status == "failed"
        assert spoken == [session.config.failure_template]
        assert session.history == []

    asyncio.run(scenario())


def test_transition_waits_without_repeating_completed_business_call():
    async def scenario():
        inference, api = Inference(), API()
        session = DialogSession(
            config(
                business(api=APIContract(endpoint="orders"), next_intent="SECOND"),
                business(
                    "SECOND",
                    fields=[{"name": "phone"}],
                    rules=[{"conditions": [{"field": "phone"}]}],
                    next_intent="END",
                ),
            ),
            inference,
            inference,
            api,
        )
        assert (await session.respond("look up my order")).missing == {"SECOND": ["phone"]}
        assert len(api.calls) == 1
        result = await session.respond("phone=123")
        assert result.status == "ended"
        assert result.texts == ["Goodbye."]
        assert len(api.calls) == 1
        assert (await session.respond("again")).status == "ended"

    asyncio.run(scenario())


def test_goodbye_runs_after_other_identified_intents():
    async def scenario():
        inference, api = Inference({"LOOKUP": 0.99, "END": 0.99}), API()
        session = DialogSession(
            config(business(api=APIContract(endpoint="orders"))), inference, inference, api
        )
        assert (await session.respond("check my order then goodbye")).status == "ended"
        assert len(api.calls) == 1

    asyncio.run(scenario())


def test_failure_and_cancelled_side_effect_are_never_retried():
    async def scenario(error):
        class FailedAPI:
            async def call(self, *_):
                raise error

        inference = Inference()
        session = DialogSession(
            config(business(api=APIContract(endpoint="orders"))), inference, inference, FailedAPI()
        )
        if isinstance(error, asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await session.respond("order")
        else:
            assert (await session.respond("order")).status == "failed"
        assert (await session.respond("again")).status == "ended"

    asyncio.run(scenario(ValueError("sensitive upstream error")))
    asyncio.run(scenario(asyncio.CancelledError()))


def test_history_limit_fails_without_silently_truncating():
    async def scenario():
        inference = Inference()
        session = DialogSession(
            config(lookup(), max_history_chars=1000), inference, inference, API()
        )
        assert (await session.respond("x" * 1001)).status == "history_limit"
        assert session.history == []

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "changes",
    [
        {"next_intent": "MISSING"},
        {"next_intent": "LOOKUP"},
        {"fields": [{"name": "id"}, {"name": "id"}]},
        {"rules": [{"conditions": [{"field": "unknown"}]}]},
        {"responses": ["{secret.__class__}"]},
        {"responses": ["{unbound}"]},
        {"missing_template": "{unbound}"},
    ],
)
def test_configuration_rejects_invalid_references_and_templates(changes):
    with pytest.raises((ValidationError, ValueError)):
        config(business(**changes))


def test_policy_roundtrip_isolated_from_session_snapshot():
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                DialogPolicy.__table__.insert().values(
                    id=1, configuration=DialogConfig().model_dump(mode="json")
                )
            )
        policy = config(lookup())
        save_config(engine, policy)
        assert load_config(engine) == policy
        inference = Inference()
        session = DialogSession(policy, inference, inference, API())
        policy.intents[-1].description = "changed"
        assert session.intents["LOOKUP"].description == "Look up an order"
        with engine.connect() as connection:
            assert len(connection.execute(select(DialogPolicy)).all()) == 1
    finally:
        engine.dispose()


def test_migration_seeds_valid_policy_and_preserves_existing_session_table():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    path = ROOT / "apps/backend/migrations/versions/0002_dialog_policy.py"
    spec = importlib.util.spec_from_file_location("dialog_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE voice_sessions (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO voice_sessions VALUES (42)")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            payload = connection.execute(select(DialogPolicy.configuration)).scalar_one()
            assert DialogConfig.model_validate(payload) == DialogConfig()
            assert connection.exec_driver_sql("SELECT id FROM voice_sessions").scalar_one() == 42
            migration.downgrade()
        assert "dialog_policy" not in inspect(connection).get_table_names()
    engine.dispose()


def test_api_bindings_response_mapping_and_no_redirects():
    async def scenario():
        def handler(request):
            assert request.url == "https://business.example/orders?id=42"
            assert request.headers["authorization"] == "Bearer test-only"
            return httpx.Response(200, json={"order": {"state": "shipped"}})

        api = BusinessAPI(
            {"orders": "https://business.example/orders"},
            {"orders": {"authorization": "Bearer test-only"}},
            transport=httpx.MockTransport(handler),
        )
        contract = APIContract(
            endpoint="orders", query={"id": "order_id"}, response={"status": "order.state"}
        )
        assert await api.call(contract, {"order_id": "42"}) == {"status": "shipped"}
        api.transport = httpx.MockTransport(
            lambda _: httpx.Response(302, headers={"location": "/private"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            await api.call(contract, {"order_id": "42"})

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"status": {"nested": "invalid"}}),
        httpx.Response(200, content=b"x" * (1024 * 1024 + 1)),
    ],
)
def test_api_errors_are_not_rendered_as_success(response):
    async def scenario():
        api = BusinessAPI(
            {"orders": "https://business.example/orders"},
            transport=httpx.MockTransport(lambda _: response),
        )
        with pytest.raises((ValueError, httpx.HTTPError)):
            await api.call(APIContract(endpoint="orders", response={"status": "status"}), {})

    asyncio.run(scenario())


def test_voice_bridge_delivers_welcome_and_speech_without_transport_knowledge():
    async def scenario():
        inference = Inference()
        session = DialogSession(config(business(responses=["Done."])), inference, inference, API())
        spoken = []

        async def speak(text):
            spoken.append(text)

        bridge = DialogVoiceBridge(session, speak)
        await bridge.start()
        assert (await bridge.caller_turn("lookup")).status == "complete"
        assert spoken == ["Welcome. How can I help you?", "Done."]
        bridge.close()
        assert session.history == []

    asyncio.run(scenario())
