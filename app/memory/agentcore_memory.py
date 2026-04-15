"""AgentCore Memory abstraction with a local fallback implementation."""

from __future__ import annotations

from typing import Protocol

from app.memory.models import MemoryEvent, SessionStateSnapshot
from app.memory.session_store import InMemorySessionStore, SessionStore
from app.schemas.session import SessionContext


class AgentCoreMemoryBackend(Protocol):
    """Adapter contract for a future AgentCore Memory integration."""

    async def create_session(self, context: SessionContext) -> SessionStateSnapshot:
        """Create a new memory session."""

    async def append_event(
        self,
        session_id: str,
        event: MemoryEvent,
    ) -> SessionStateSnapshot:
        """Append an event to the memory session."""

    async def list_events(self, session_id: str) -> list[MemoryEvent]:
        """List stored events for a session."""

    async def get_session_state(self, session_id: str) -> SessionStateSnapshot:
        """Get the current derived session state."""


class AgentCoreMemorySessionStore:
    """Session store facade that can be backed by AgentCore later."""

    def __init__(
        self,
        *,
        backend: AgentCoreMemoryBackend | None = None,
        fallback_store: SessionStore | None = None,
    ) -> None:
        self._backend = backend
        self._fallback_store = fallback_store or InMemorySessionStore()

    async def create_session(self, context: SessionContext) -> SessionStateSnapshot:
        """Create a session using the configured backend or fallback store."""
        return await self._active_store().create_session(context)

    async def append_event(
        self,
        session_id: str,
        event: MemoryEvent,
    ) -> SessionStateSnapshot:
        """Append an event using the configured backend or fallback store."""
        return await self._active_store().append_event(session_id, event)

    async def list_events(self, session_id: str) -> list[MemoryEvent]:
        """List events using the configured backend or fallback store."""
        return await self._active_store().list_events(session_id)

    async def get_session_state(self, session_id: str) -> SessionStateSnapshot:
        """Fetch the current state using the configured backend or fallback."""
        return await self._active_store().get_session_state(session_id)

    def _active_store(self) -> AgentCoreMemoryBackend | SessionStore:
        return self._backend or self._fallback_store
