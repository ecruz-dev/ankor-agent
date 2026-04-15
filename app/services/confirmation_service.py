"""Explicit confirmation handling for sensitive conversation actions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agent.guardrails import FINALIZE_EVALUATION_TOOL
from app.memory.models import ConfirmationStateChangeEvent, SessionStateSnapshot
from app.schemas.session import ConfirmationStatus

_NON_WORD_PATTERN = re.compile(r"[^\w\s]")
_AFFIRMATIVE_RESPONSES = frozenset({"yes", "confirm", "go ahead"})
_NEGATIVE_RESPONSES = frozenset({"no", "cancel"})


@dataclass(frozen=True, slots=True)
class ConfirmationResolution:
    """Result of evaluating a user confirmation response."""

    status: ConfirmationStatus
    event: ConfirmationStateChangeEvent
    explicit_confirmation: bool
    assistant_response: str | None = None


class ConfirmationService:
    """Interpret and persist explicit confirmation decisions."""

    def parse_confirmation_response(self, user_text: str) -> ConfirmationStatus | None:
        """Interpret simple affirmative or negative user replies."""
        normalized = self._normalize(user_text)
        if normalized in _AFFIRMATIVE_RESPONSES:
            return ConfirmationStatus.ACCEPTED
        if normalized in _NEGATIVE_RESPONSES:
            return ConfirmationStatus.DENIED
        return None

    def requires_pending_confirmation(self, session_state: SessionStateSnapshot) -> bool:
        """Return whether the session is currently waiting for confirmation."""
        return (
            session_state.confirmation_status is ConfirmationStatus.PENDING
            and session_state.pending_confirmation_tool is not None
        )

    def request_confirmation(
        self,
        session_state: SessionStateSnapshot,
        *,
        tool_name: str,
    ) -> ConfirmationStateChangeEvent:
        """Create an event that records a pending confirmation requirement."""
        return ConfirmationStateChangeEvent(
            session_id=session_state.session_id,
            previous_confirmation_status=session_state.confirmation_status,
            current_confirmation_status=ConfirmationStatus.PENDING,
            confirmation_tool_name=tool_name,
            reason="Explicit confirmation is required before finalizing the evaluation.",
        )

    def resolve_confirmation(
        self,
        session_state: SessionStateSnapshot,
        *,
        user_text: str,
    ) -> ConfirmationResolution | None:
        """Resolve a user reply against the current pending confirmation state."""
        if not self.requires_pending_confirmation(session_state):
            return None

        decision = self.parse_confirmation_response(user_text)
        if decision is None:
            return None

        tool_name = session_state.pending_confirmation_tool
        if tool_name is None:
            return None

        if decision is ConfirmationStatus.ACCEPTED:
            return ConfirmationResolution(
                status=decision,
                event=ConfirmationStateChangeEvent(
                    session_id=session_state.session_id,
                    previous_confirmation_status=session_state.confirmation_status,
                    current_confirmation_status=ConfirmationStatus.ACCEPTED,
                    confirmation_tool_name=tool_name,
                    reason="Coach explicitly confirmed the requested action.",
                ),
                explicit_confirmation=True,
            )

        return ConfirmationResolution(
            status=decision,
            event=ConfirmationStateChangeEvent(
                session_id=session_state.session_id,
                previous_confirmation_status=session_state.confirmation_status,
                current_confirmation_status=ConfirmationStatus.DENIED,
                confirmation_tool_name=tool_name,
                reason="Coach declined the requested action.",
            ),
            explicit_confirmation=False,
            assistant_response="Okay, I won't finalize the evaluation.",
        )

    def build_confirmation_prompt(self, tool_name: str) -> str:
        """Return a concise confirmation prompt for a protected tool."""
        if tool_name == FINALIZE_EVALUATION_TOOL:
            return "Please confirm that you want me to finalize the evaluation."
        return "Please confirm that you want me to continue."

    @staticmethod
    def _normalize(user_text: str) -> str:
        normalized = _NON_WORD_PATTERN.sub("", user_text.strip().lower())
        return " ".join(normalized.split())
