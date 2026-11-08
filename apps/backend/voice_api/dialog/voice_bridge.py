"""A narrow integration seam: completed caller turns in, speech requests out."""

from collections.abc import Awaitable, Callable

from .engine import DialogSession


class DialogRuntime:
    """Own shared local inference and create isolated database-policy sessions."""

    def __init__(self, engine):
        """Load once on a worker thread, failing before accepting calls."""
        import json
        import os

        from pydantic import TypeAdapter

        from .api import BusinessAPI
        from .claim_simulator import simulated_claim_api
        from .providers import LocalModels
        from .store import load_config

        self.engine = engine
        config = load_config(engine)
        mode = os.getenv("DIALOG_API_MODE", "live")
        if mode == "simulated":
            self.api = simulated_claim_api()
        elif mode == "live":
            endpoints = TypeAdapter(dict[str, str]).validate_python(
                json.loads(os.getenv("BUSINESS_API_ENDPOINTS") or "{}"), strict=True
            )
            headers = TypeAdapter(dict[str, dict[str, str]]).validate_python(
                json.loads(os.getenv("BUSINESS_API_HEADERS") or "{}"), strict=True
            )
            self.api = BusinessAPI(endpoints, headers)
        else:
            raise ValueError("DIALOG_API_MODE must be live or simulated")
        self.entity_threshold = config.entity_threshold
        self._validate(config)
        quantize = os.getenv("GLINER_QUANTIZE", "false").strip().lower()
        if quantize not in {"true", "false"}:
            raise ValueError("GLINER_QUANTIZE must be true or false")
        self.models = LocalModels(
            os.getenv("LAYA_MODEL_PATH", "models/laya"),
            os.getenv("GLINER_MODEL_PATH", "models/gliner-small-v2.1"),
            self.entity_threshold,
            quantize=quantize == "true",
        )

    def _validate(self, config):
        if config.entity_threshold != self.entity_threshold:
            raise ValueError("Restart the API after changing the entity threshold")
        if any(i.api and i.api.endpoint not in self.api.endpoints for i in config.intents):
            raise ValueError("Dialog policy references an unconfigured business API alias")

    def session(self):
        """Read a fresh policy snapshot in a short synchronous transaction."""
        from .store import load_config

        config = load_config(self.engine)
        self._validate(config)
        return DialogSession(config, self.models, self.models, self.api)

    def close(self):
        """Join inference only after voice sessions have closed."""
        self.models.close()


class DialogVoiceBridge:
    """Delegate speech and interruption ownership to the voice orchestration layer."""

    def __init__(self, dialog: DialogSession, speak: Callable[[str], Awaitable[None]]):
        """Inject an asynchronous speech delivery function, never a text chat transport."""
        self.dialog, self.speak = dialog, speak

    async def start(self):
        """Request the welcome script before accepting caller turns."""
        for text in self.dialog.welcome().texts:
            await self.speak(text)

    async def caller_turn(self, transcript: str):
        """Handle one finalized full caller turn and deliver its dialog reply."""
        from .engine import DialogReply

        try:
            reply = await self.dialog.respond(transcript)
        except Exception:
            # Model/configuration failures must not expose caller data through exceptions.
            self.dialog.close()
            reply = DialogReply([self.dialog.config.failure_template], "failed")
        for text in reply.texts:
            await self.speak(text)
        return reply

    def close(self):
        """Erase ephemeral dialog content when the owning voice session closes."""
        self.dialog.close()
