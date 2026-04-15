"""Models for short-term session memory."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.session import ConfirmationStatus, ResolutionStatus, SessionContext


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _new_identifier() -> str:
    """Generate a stable identifier for sessions and events."""
    return str(uuid4())


class SessionEventType(str, Enum):
    """Supported short-term memory event types."""

    USER_UTTERANCE = "user_utterance"
    ASSISTANT_REPLY = "assistant_reply"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    CONFIRMATION_STATE_CHANGE = "confirmation_state_change"


class MemoryEvent(BaseModel):
    """Base model for all session memory events."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str = Field(default_factory=_new_identifier, min_length=1)
    session_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utc_now)
    event_type: SessionEventType


class UserUtteranceEvent(MemoryEvent):
    """A user utterance captured during the session."""

    event_type: Literal[SessionEventType.USER_UTTERANCE] = (
        SessionEventType.USER_UTTERANCE
    )
    text: str = Field(min_length=1)


class AssistantReplyEvent(MemoryEvent):
    """An assistant response captured during the session."""

    event_type: Literal[SessionEventType.ASSISTANT_REPLY] = (
        SessionEventType.ASSISTANT_REPLY
    )
    text: str = Field(min_length=1)


class ToolRequestEvent(MemoryEvent):
    """A tool invocation requested by the assistant."""

    event_type: Literal[SessionEventType.TOOL_REQUEST] = SessionEventType.TOOL_REQUEST
    tool_name: str = Field(min_length=1)
    request_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResultEvent(MemoryEvent):
    """The result of a tool invocation."""

    event_type: Literal[SessionEventType.TOOL_RESULT] = SessionEventType.TOOL_RESULT
    tool_name: str = Field(min_length=1)
    request_id: str | None = None
    success: bool = True
    payload: dict[str, Any] | None = None
    error_message: str | None = None


class ConfirmationStateChangeEvent(MemoryEvent):
    """A change to the session confirmation state."""

    event_type: Literal[SessionEventType.CONFIRMATION_STATE_CHANGE] = (
        SessionEventType.CONFIRMATION_STATE_CHANGE
    )
    previous_status: ResolutionStatus | None = None
    current_status: ResolutionStatus | None = None
    previous_confirmation_status: ConfirmationStatus | None = None
    current_confirmation_status: ConfirmationStatus | None = None
    confirmation_tool_name: str | None = None
    reason: str | None = None


class SessionStateSnapshot(SessionContext):
    """A derived snapshot of the current session state."""

    created_at: datetime
    updated_at: datetime
    event_count: int = Field(default=0, ge=0)
    confirmation_status: ConfirmationStatus = ConfirmationStatus.NONE
    pending_confirmation_tool: str | None = None
    last_assistant_reply: str | None = None
    last_tool_name: str | None = None
    last_confirmation_reason: str | None = None

    @classmethod
    def from_context(cls, context: SessionContext) -> Self:
        """Create a state snapshot from the initial session context."""
        now = _utc_now()
        return cls(
            **context.model_dump(mode="python"),
            created_at=now,
            updated_at=now,
        )
