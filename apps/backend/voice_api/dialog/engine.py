"""Session-local dialog state and rule evaluation without voice responsibilities."""

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

import regex

from .config import APIContract, DialogConfig, Intent


class Classifier(Protocol):
    """Identify any number of intents with independent confidence scores."""

    async def classify(self, text: str, intents: list[Intent]) -> dict[str, float]:
        """Return supported intent names and their positive confidence."""
        ...


class Extractor(Protocol):
    """Extract only fields belonging to a selected intent."""

    async def extract(self, history: list[str], intent: Intent) -> dict[str, str]:
        """Normalize fields across all caller responses."""
        ...


class APICaller(Protocol):
    """Execute a configured business contract and return template values."""

    async def call(self, contract: APIContract, entities: dict[str, str]) -> dict[str, str]:
        """Perform one call; never automatically retry a side effect."""
        ...


@dataclass
class DialogReply:
    """Text for the voice layer to synthesize, plus internal dialog status."""

    texts: list[str] = field(default_factory=list)
    status: str = "listening"
    missing: dict[str, list[str]] = field(default_factory=dict)


def missing_fields(intent: Intent, values: dict[str, str]) -> list[str]:
    """Choose the first smallest unsatisfied rule, adding required API bindings."""
    alternatives = []
    for rule in intent.rules:
        missing = []
        for condition in rule.conditions:
            value = values.get(condition.field)
            valid = value is not None and value != ""
            if valid and condition.operator == "equals":
                valid = value == condition.value
            elif valid and condition.operator == "one_of":
                valid = value in condition.value
            elif valid and condition.operator == "matches":
                valid = regex.fullmatch(condition.value, value, timeout=0.05) is not None
            if not valid and condition.field not in missing:
                missing.append(condition.field)
        alternatives.append(missing)
    required = []
    if intent.api:
        for name in [*intent.api.query.values(), *intent.api.body.values()]:
            if not values.get(name) and name not in required:
                required.append(name)
    candidates = [list(dict.fromkeys(fields + required)) for fields in alternatives or [[]]]
    return min(candidates, key=len)


class DialogSession:
    """Preserve pending work and ephemeral caller history across clarification turns."""

    def __init__(
        self, config: DialogConfig, classifier: Classifier, extractor: Extractor, api: APICaller
    ):
        """Use a private configuration snapshot and injected inference/API adapters."""
        self.config = config.model_copy(deep=True)
        self.intents = {i.name: i for i in self.config.intents}
        self.classifier, self.extractor, self.api = classifier, extractor, api
        self.history: list[str] = []
        self.pending: list[str] = []
        self.completed: set[str] = set()
        self.ended = False
        self.started = False
        self.lock = asyncio.Lock()

    def welcome(self) -> DialogReply:
        """Read the WELCOME script once at session start."""
        if self.started:
            return DialogReply()
        self.started = True
        intent = self.intents["WELCOME"]
        self.pending = [intent.next_intent] if intent.next_intent else []
        return DialogReply(texts=intent.responses[:1])

    async def respond(self, text: str) -> DialogReply:
        """Evaluate every pending intent before making any business API calls."""
        async with self.lock:
            if self.ended:
                return DialogReply(status="ended")
            if not text.strip():
                return DialogReply()
            if sum(map(len, self.history)) + len(text) > self.config.max_history_chars:
                # Do not silently truncate history and lose previously supplied fields.
                self.ended = True
                return DialogReply([self.config.failure_template], status="history_limit")
            self.history.append(text.strip())
            scores = await self.classifier.classify(
                "\n".join(self.history),
                [intent for intent in self.config.intents if intent.name != "WELCOME"],
            )
            for name in self.intents:
                if (
                    name in scores
                    and name != "WELCOME"
                    and name not in self.completed
                    and name not in self.pending
                    and scores[name] > self.config.confidence_threshold
                ):
                    self.pending.append(name)
            if not self.pending:
                return DialogReply([self.config.clarification_template], "clarify")
            # A goodbye accompanying a business request must not discard that request.
            self.pending.sort(key=lambda name: name == "END")

            texts = []
            while self.pending:
                extracted = {}
                missing = {}
                for name in self.pending:
                    intent = self.intents[name]
                    values = await self.extractor.extract(self.history, intent)
                    extracted[name] = values
                    needed = missing_fields(intent, values)
                    if needed:
                        missing[name] = needed
                if missing:
                    prompts = [
                        self.intents[name].missing_template.format(
                            intent=name, missing_fields=", ".join(fields)
                        )
                        for name, fields in missing.items()
                    ]
                    return DialogReply(texts + prompts, "missing", missing)

                # All currently identified intents are sufficient before execution begins.
                batch = list(self.pending)
                for name in batch:
                    intent = self.intents[name]
                    try:
                        values = (
                            await self.api.call(intent.api, extracted[name]) if intent.api else {}
                        )
                        if intent.responses:
                            # Stable rotation avoids random, irreproducible response selection.
                            template = intent.responses[len(self.completed) % len(intent.responses)]
                            texts.append(template.format_map(values))
                    except asyncio.CancelledError:
                        # An interrupted in-flight side effect has unknown outcome. Never replay it.
                        self.ended = True
                        raise
                    except Exception:
                        self.ended = True
                        return DialogReply(texts + [self.config.failure_template], "failed")
                    self.pending.remove(name)
                    self.completed.add(name)
                    if name == "END":
                        self.pending.clear()
                        self.ended = True
                        return DialogReply(texts, "ended")
                    target = intent.next_intent
                    if target and target not in self.completed and target not in self.pending:
                        self.pending.append(target)
            self.ended = True
            return DialogReply(texts, "complete")

    def close(self):
        """Discard caller history and pending work at disconnect."""
        self.ended = True
        self.history.clear()
        self.pending.clear()
        self.completed.clear()
