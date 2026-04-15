from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from app.api.deps import AppServices
from app.config.settings import Settings
from app.main import create_app
from app.schemas.session import ConfirmationStatus, ResolutionStatus
from app.services.conversation_service import (
    ConversationAuthContext,
    ConversationTurnResult,
)


@dataclass
class StubConversationService:
    result: ConversationTurnResult
    calls: list[tuple[str, ConversationAuthContext]] = field(default_factory=list)

    async def handle_turn(
        self,
        *,
        user_text: str,
        auth_context: ConversationAuthContext,
    ) -> ConversationTurnResult:
        self.calls.append((user_text, auth_context))
        return self.result


def _build_turn_result(
    *,
    assistant_response: str,
    resolution_status: ResolutionStatus,
    confirmation_status: ConfirmationStatus,
) -> ConversationTurnResult:
    from app.memory.models import SessionStateSnapshot

    session_state = SessionStateSnapshot.model_validate(
        {
            "session_id": "session-1",
            "org_id": "org-1",
            "coach_id": "coach-1",
            "resolution_status": resolution_status,
            "confirmation_status": confirmation_status,
            "pending_confirmation_tool": (
                "finalize_evaluation"
                if confirmation_status is ConfirmationStatus.PENDING
                else None
            ),
            "created_at": "2026-04-15T00:00:00Z",
            "updated_at": "2026-04-15T00:00:00Z",
        }
    )
    return ConversationTurnResult(
        assistant_response=assistant_response,
        session_state=session_state,
    )


def test_post_session_message_returns_assistant_response_and_status() -> None:
    conversation_service = StubConversationService(
        result=_build_turn_result(
            assistant_response="I found Jane Doe on varsity.",
            resolution_status=ResolutionStatus.RESOLVED,
            confirmation_status=ConfirmationStatus.NONE,
        )
    )
    app = create_app(
        services=AppServices(
            settings=Settings(),
            conversation_service=conversation_service,
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/sessions/session-1/message",
            json={
                "text": "Find Jane Doe",
                "coach_id": "coach-1",
                "org_id": "org-1",
                "team_id": "team-1",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-1",
        "assistant_response": "I found Jane Doe on varsity.",
        "current_session_status": "resolved",
        "confirmation_status": "none",
        "confirmation_pending": False,
    }
    assert conversation_service.calls[0][0] == "Find Jane Doe"
    assert conversation_service.calls[0][1].session_id == "session-1"
    assert conversation_service.calls[0][1].team_id == "team-1"


def test_post_session_message_returns_pending_confirmation_flag() -> None:
    conversation_service = StubConversationService(
        result=_build_turn_result(
            assistant_response="Please confirm that you want me to finalize the evaluation.",
            resolution_status=ResolutionStatus.PENDING_CONFIRMATION,
            confirmation_status=ConfirmationStatus.PENDING,
        )
    )
    app = create_app(
        services=AppServices(
            settings=Settings(),
            conversation_service=conversation_service,
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/sessions/session-1/message",
            json={
                "text": "Finalize it",
                "coach_id": "coach-1",
                "org_id": "org-1",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-1",
        "assistant_response": "Please confirm that you want me to finalize the evaluation.",
        "current_session_status": "pending_confirmation",
        "confirmation_status": "pending",
        "confirmation_pending": True,
    }
