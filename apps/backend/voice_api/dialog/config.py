"""Validated database configuration for intent-specific dialog behavior."""

import re
from string import Formatter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConfigModel(BaseModel):
    """Reject misspelled configuration keys."""

    model_config = ConfigDict(extra="forbid")


def placeholders(template: str) -> set[str]:
    """Accept simple named substitutions only, without Python attribute access."""
    names = set()
    for _, name, spec, conversion in Formatter().parse(template):
        if name is not None:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name) or spec or conversion:
                raise ValueError("Templates accept only simple {name} placeholders")
            names.add(name)
    return names


class EntityField(ConfigModel):
    """Intent-specific deterministic and model-based extraction instructions."""

    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z_0-9]*$")
    label: str | None = None
    regex: str | None = Field(default=None, max_length=500)
    normalize: Literal["strip", "lower", "upper", "digits"] = "strip"

    @model_validator(mode="after")
    def validate_pattern(self):
        """Compile administrative patterns before accepting a configuration."""
        if self.regex:
            try:
                re.compile(self.regex)
            except re.error as exc:
                raise ValueError("Invalid extraction regular expression") from exc
        return self


class Condition(ConfigModel):
    """A declarative predicate; no executable expressions are stored."""

    field: str
    operator: Literal["present", "equals", "one_of", "matches"] = "present"
    value: str | list[str] | None = None

    @model_validator(mode="after")
    def validate_operand(self):
        """Require the operand appropriate to each operator."""
        if self.operator in {"equals", "matches"} and not isinstance(self.value, str):
            raise ValueError("equals/matches require a string")
        if self.operator == "one_of" and not isinstance(self.value, list):
            raise ValueError("one_of requires a list")
        if self.operator == "matches":
            try:
                re.compile(self.value)
            except re.error as exc:
                raise ValueError("Invalid condition regular expression") from exc
        return self


class Rule(ConfigModel):
    """All conditions must succeed; rules for an intent are alternatives."""

    conditions: list[Condition] = Field(min_length=1)


class APIContract(ConfigModel):
    """A fixed server-side destination with entity-to-request bindings."""

    endpoint: str = Field(pattern=r"^[A-Za-z_][A-Za-z_0-9]*$")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    query: dict[str, str] = Field(default_factory=dict)
    optional_query: dict[str, str] = Field(default_factory=dict)
    body: dict[str, str] = Field(default_factory=dict)
    response: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=10, gt=0, le=60)


class Intent(ConfigModel):
    """Optional rules, API, templates and transition for one configured intent."""

    name: str = Field(pattern=r"^[A-Z][A-Z_0-9]*$")
    type: Literal["General", "Business"]
    description: str = Field(min_length=1)
    fields: list[EntityField] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    api: APIContract | None = None
    responses: list[str] = Field(default_factory=list)
    missing_template: str = "Please provide {missing_fields}."
    next_intent: str | None = None

    @model_validator(mode="after")
    def validate_references(self):
        """Reject unknown fields, ambiguous labels and invalid template bindings."""
        names = {field.name for field in self.fields}
        if len(names) != len(self.fields):
            raise ValueError("Duplicate field name")
        labels = [field.label for field in self.fields if field.label]
        if len(labels) != len(set(labels)):
            raise ValueError("Entity labels must be unique within an intent")
        references = {c.field for r in self.rules for c in r.conditions}
        if self.api:
            references.update(self.api.query.values())
            references.update(self.api.body.values())
            references.update(self.api.optional_query.values())
        if not references <= names:
            raise ValueError("Rules/API reference unknown entity fields")
        response_names = set(self.api.response) if self.api else set()
        for template in self.responses:
            if not placeholders(template) <= response_names:
                raise ValueError("Response placeholder lacks an API response binding")
        if not placeholders(self.missing_template) <= {"missing_fields", "intent"}:
            raise ValueError("Missing templates accept {missing_fields} and {intent}")
        return self


class DialogConfig(ConfigModel):
    """One application configuration, snapshotted per conversation."""

    confidence_threshold: float = Field(default=0.8, ge=0, le=1)
    entity_threshold: float = Field(default=0.5, ge=0, le=1)
    clarification_template: str = "Please clarify what you would like help with."
    failure_template: str = "I could not complete that request. Please try again later."
    max_history_chars: int = Field(default=32000, ge=1000, le=1000000)
    intents: list[Intent] = Field(
        default_factory=lambda: [
            Intent(
                name="WELCOME",
                type="General",
                description="Greeting or start of a call",
                responses=["Welcome. How can I help you?"],
            ),
            Intent(
                name="END",
                type="General",
                description="End the conversation or say goodbye",
                responses=["Goodbye."],
            ),
        ]
    )

    @model_validator(mode="after")
    def validate_graph(self):
        """Ensure transitions are resolvable and cannot loop indefinitely."""
        by_name = {intent.name: intent for intent in self.intents}
        if len(by_name) != len(self.intents):
            raise ValueError("Intent names must be unique across both types")
        for name in ("WELCOME", "END"):
            if name not in by_name or by_name[name].type != "General":
                raise ValueError("WELCOME and END must be General intents")
        for intent in self.intents:
            seen = set()
            current = intent
            while current.next_intent:
                if current.name in seen:
                    raise ValueError("Cyclic next_intent transition")
                seen.add(current.name)
                if current.next_intent not in by_name:
                    raise ValueError("Unknown next_intent")
                current = by_name[current.next_intent]
        if placeholders(self.clarification_template) or placeholders(self.failure_template):
            raise ValueError("Clarification/failure templates cannot contain placeholders")
        welcome = by_name["WELCOME"]
        if welcome.api or welcome.rules or any(placeholders(t) for t in welcome.responses):
            raise ValueError("WELCOME must be a script without API/rule dependencies")
        return self
