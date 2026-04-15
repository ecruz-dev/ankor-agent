from app.memory.models import SessionStateSnapshot
from app.schemas.session import ConfirmationStatus
from app.services.confirmation_service import ConfirmationService


def test_confirmation_service_accepts_affirmative_response() -> None:
    service = ConfirmationService()
    session_state = SessionStateSnapshot.model_validate(
        {
            "session_id": "session-1",
            "org_id": "org-1",
            "coach_id": "coach-1",
            "resolution_status": "resolved",
            "confirmation_status": "pending",
            "pending_confirmation_tool": "finalize_evaluation",
            "created_at": "2026-04-15T00:00:00Z",
            "updated_at": "2026-04-15T00:00:00Z",
        }
    )

    resolution = service.resolve_confirmation(session_state, user_text="go ahead")

    assert resolution is not None
    assert resolution.status is ConfirmationStatus.ACCEPTED
    assert resolution.explicit_confirmation is True
    assert resolution.assistant_response is None
    assert resolution.event.current_confirmation_status is ConfirmationStatus.ACCEPTED


def test_confirmation_service_denies_negative_response() -> None:
    service = ConfirmationService()
    session_state = SessionStateSnapshot.model_validate(
        {
            "session_id": "session-1",
            "org_id": "org-1",
            "coach_id": "coach-1",
            "resolution_status": "resolved",
            "confirmation_status": "pending",
            "pending_confirmation_tool": "finalize_evaluation",
            "created_at": "2026-04-15T00:00:00Z",
            "updated_at": "2026-04-15T00:00:00Z",
        }
    )

    resolution = service.resolve_confirmation(session_state, user_text="cancel")

    assert resolution is not None
    assert resolution.status is ConfirmationStatus.DENIED
    assert resolution.explicit_confirmation is False
    assert resolution.assistant_response == "Okay, I won't finalize the evaluation."
    assert resolution.event.current_confirmation_status is ConfirmationStatus.DENIED
