"""Session models for the ANKOR voice service."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ResolutionStatus(str, Enum):
    """Shared resolution states used across the voice flow."""

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    PENDING_CONFIRMATION = "pending_confirmation"


class SessionContext(BaseModel):
    """Conversation state carried between tool calls."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=1)
    org_id: str = Field(min_length=1)
    coach_id: str = Field(min_length=1)
    team_id: str | None = None
    active_athlete_id: str | None = None
    active_scorecard_template_id: str | None = None
    last_user_utterance: str | None = None
    resolution_status: ResolutionStatus = ResolutionStatus.PENDING_CONFIRMATION
