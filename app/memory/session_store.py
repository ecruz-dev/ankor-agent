"""Session store abstractions and local in-memory implementation."""

from __future__ import annotations

from typing import Protocol, cast

from fastapi import status

from app.memory.models import (
    AssistantReplyEvent,
    ConfirmationStateChangeEvent,
    MemoryEvent,
    SessionStateSnapshot,
    ToolRequestEvent,
    ToolResultEvent,
    UserUtteranceEvent,
)
from app.schemas.session import ConfirmationStatus, SessionContext
from app.utils.errors import AppError


class SessionStoreError(AppError):
    """Base error for session store failures."""


class SessionAlreadyExistsError(SessionStoreError):
    """Raised when a session already exists."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Session '{session_id}' already exists",
            error_code="session_already_exists",
            status_code=status.HTTP_409_CONFLICT,
        )


class SessionNotFoundError(SessionStoreError):
    """Raised when a session cannot be found."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Session '{session_id}' was not found",
            error_code="session_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class SessionEventMismatchError(SessionStoreError):
    """Raised when an event does not match the target session."""

    def __init__(self, expected_session_id: str, actual_session_id: str) -> None:
        super().__init__(
            (
                "Session event does not match the target session: "
                f"expected '{expected_session_id}', got '{actual_session_id}'"
            ),
            error_code="session_event_mismatch",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class SessionStore(Protocol):
    """Abstract interface for short-term session memory."""

    async def create_session(self, context: SessionContext) -> SessionStateSnapshot:
        """Create a new session."""

    async def append_event(
        self,
        session_id: str,
        event: MemoryEvent,
    ) -> SessionStateSnapshot:
        """Append an event to an existing session."""

    async def list_events(self, session_id: str) -> list[MemoryEvent]:
        """List all events for a session in append order."""

    async def get_session_state(self, session_id: str) -> SessionStateSnapshot:
        """Return the current derived state for a session."""


class InMemorySessionStore:
    """In-memory session store for local development and tests."""

    def __init__(self) -> None:
        self._states: dict[str, SessionStateSnapshot] = {}
        self._events: dict[str, list[MemoryEvent]] = {}

    async def create_session(self, context: SessionContext) -> SessionStateSnapshot:
        session_id = context.session_id
        if session_id in self._states:
            raise SessionAlreadyExistsError(session_id)

        state = SessionStateSnapshot.from_context(context)
        self._states[session_id] = state
        self._events[session_id] = []
        return state.model_copy(deep=True)

    async def append_event(
        self,
        session_id: str,
        event: MemoryEvent,
    ) -> SessionStateSnapshot:
        state = self._require_state(session_id)
        if event.session_id != session_id:
            raise SessionEventMismatchError(session_id, event.session_id)

        self._events[session_id].append(event.model_copy(deep=True))
        updated_state = self._apply_event(state, event)
        self._states[session_id] = updated_state
        return updated_state.model_copy(deep=True)

    async def list_events(self, session_id: str) -> list[MemoryEvent]:
        self._require_state(session_id)
        return [
            cast(MemoryEvent, event.model_copy(deep=True))
            for event in self._events[session_id]
        ]

    async def get_session_state(self, session_id: str) -> SessionStateSnapshot:
        return self._require_state(session_id).model_copy(deep=True)

    def _require_state(self, session_id: str) -> SessionStateSnapshot:
        state = self._states.get(session_id)
        if state is None:
            raise SessionNotFoundError(session_id)
        return state

    @staticmethod
    def _apply_event(
        state: SessionStateSnapshot,
        event: MemoryEvent,
    ) -> SessionStateSnapshot:
        updates: dict[str, object] = {
            "updated_at": event.created_at,
            "event_count": state.event_count + 1,
        }

        if isinstance(event, UserUtteranceEvent):
            updates["last_user_utterance"] = event.text
        elif isinstance(event, AssistantReplyEvent):
            updates["last_assistant_reply"] = event.text
        elif isinstance(event, (ToolRequestEvent, ToolResultEvent)):
            updates["last_tool_name"] = event.tool_name
        elif isinstance(event, ConfirmationStateChangeEvent):
            if event.current_status is not None:
                updates["resolution_status"] = event.current_status
            if event.current_confirmation_status is not None:
                updates["confirmation_status"] = event.current_confirmation_status
                updates["pending_confirmation_tool"] = (
                    event.confirmation_tool_name
                    if event.current_confirmation_status is ConfirmationStatus.PENDING
                    else None
                )
            updates["last_confirmation_reason"] = event.reason

        return state.model_copy(update=updates, deep=True)
