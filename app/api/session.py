"""HTTP endpoints for local text-based conversation testing."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_conversation_service
from app.schemas.session import ConfirmationStatus, ResolutionStatus
from app.services.conversation_service import (
    ConversationAuthContext,
    ConversationService,
)

router = APIRouter(tags=["sessions"])


class SessionMessageRequest(BaseModel):
    """Request body for a local text conversation turn."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1)
    coach_id: str = Field(min_length=1)
    org_id: str = Field(min_length=1)
    team_id: str | None = None
    active_athlete_id: str | None = None
    active_scorecard_template_id: str | None = None


class SessionMessageResponse(BaseModel):
    """Developer-friendly response for local conversation testing."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    assistant_response: str
    current_session_status: ResolutionStatus
    confirmation_status: ConfirmationStatus
    confirmation_pending: bool


@router.post("/sessions/{session_id}/message", response_model=SessionMessageResponse)
async def post_session_message(
    session_id: str,
    request: SessionMessageRequest,
    conversation_service: Annotated[
        ConversationService, Depends(get_conversation_service)
    ],
) -> SessionMessageResponse:
    """Send a text message into the conversation flow for local testing."""
    result = await conversation_service.handle_turn(
        user_text=request.text,
        auth_context=ConversationAuthContext(
            session_id=session_id,
            org_id=request.org_id,
            coach_id=request.coach_id,
            team_id=request.team_id,
            active_athlete_id=request.active_athlete_id,
            active_scorecard_template_id=request.active_scorecard_template_id,
        ),
    )
    session_state = result.session_state
    return SessionMessageResponse(
        session_id=session_id,
        assistant_response=result.assistant_response,
        current_session_status=session_state.resolution_status,
        confirmation_status=session_state.confirmation_status,
        confirmation_pending=(
            session_state.confirmation_status is ConfirmationStatus.PENDING
        ),
    )
