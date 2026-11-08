"""Exercise adapter contracts without downloading model weights."""

import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps/backend"))
from voice_api.dialog.config import Intent  # noqa: E402
from voice_api.dialog.providers import LocalModels  # noqa: E402


@pytest.fixture
def models(monkeypatch, tmp_path):
    class Agent:
        def __init__(self, path, device):
            assert device == "cpu"
            self.calls = []

        def predict_long(self, text, questions):
            self.calls.append((text, questions))
            return {"answers": {name: {"noul": 0.95} for name in questions}}

    class GLiNER:
        config = SimpleNamespace(max_len=20)

        @classmethod
        def from_pretrained(cls, path, **kwargs):
            assert kwargs == {"map_location": "cpu", "local_files_only": True, "quantize": "int8"}
            return cls()

        def eval(self):
            return self

        def prepare_batch(self, text, labels):
            return {"tokens": [text.split()]}

        def predict_entities(self, text, labels, threshold):
            assert labels == ["order identifier"]
            assert threshold == 0.5
            return [{"label": "order identifier", "text": "999", "start": 0}]

    monkeypatch.setitem(sys.modules, "laya", SimpleNamespace(Agent=Agent))
    monkeypatch.setitem(sys.modules, "gliner", SimpleNamespace(GLiNER=GLiNER))
    model = LocalModels(str(tmp_path), str(tmp_path))
    try:
        yield model
    finally:
        model.close()


def test_independent_intent_questions_return_multiple_positive_scores(models):
    async def scenario():
        intents = [Intent(name=name, type="Business", description=name) for name in ["A", "B"]]
        assert await models.classify("both please", intents) == {"A": 0.95, "B": 0.95}
        text, questions = models.laya.calls[0]
        assert text == "both please"
        assert all(question["type"] == "noul" for question in questions.values())

    asyncio.run(scenario())


def test_regex_precedence_and_newest_values_across_all_responses(models):
    async def scenario():
        intent = Intent(
            name="ORDER",
            type="Business",
            description="order",
            fields=[
                {
                    "name": "order_id",
                    "label": "order identifier",
                    "regex": r"id=(\d+)",
                    "normalize": "digits",
                },
                {"name": "code", "regex": r"code=(\w+)", "normalize": "upper"},
            ],
        )
        result = await models.extract(["id=123 code=abc", "id=456"], intent)
        assert result == {"order_id": "456", "code": "ABC"}

    asyncio.run(scenario())


def test_long_extraction_rejects_silent_model_truncation(models):
    async def scenario():
        intent = Intent(
            name="ORDER",
            type="Business",
            description="order",
            fields=[
                {
                    "name": "order_id",
                    "label": "order identifier",
                }
            ],
        )
        with pytest.raises(ValueError, match="input limit"):
            await models.extract(["word " * 21], intent)

    asyncio.run(scenario())


def test_regex_only_fields_do_not_invoke_gliner(models):
    async def scenario():
        intent = Intent(
            name="ORDER",
            type="Business",
            description="order",
            fields=[
                {
                    "name": "order_id",
                    "regex": r"id=(\d+)",
                }
            ],
        )
        assert await models.extract(["id=123"], intent) == {"order_id": "123"}

    asyncio.run(scenario())


@pytest.mark.parametrize("native_failure", [False, True])
def test_cancelled_inference_keeps_admission_until_native_work_finishes(models, native_failure):
    async def scenario():
        started = asyncio.Event()
        release = threading.Event()
        loop = asyncio.get_running_loop()
        second_started = []

        def native_call():
            loop.call_soon_threadsafe(started.set)
            assert release.wait(timeout=5)
            if native_failure:
                raise ValueError("native failure after cancellation")

        first = asyncio.create_task(models._run(native_call))
        await started.wait()
        first.cancel()
        second = asyncio.create_task(models._run(lambda: second_started.append(True)))
        await asyncio.sleep(0)
        assert not first.done()
        assert second_started == []
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        await second
        assert second_started == [True]

    asyncio.run(scenario())
