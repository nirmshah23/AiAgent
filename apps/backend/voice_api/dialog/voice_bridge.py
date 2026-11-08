"""A narrow integration seam: completed caller turns in, speech requests out."""

from collections.abc import Awaitable, Callable

from .engine import DialogSession


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
