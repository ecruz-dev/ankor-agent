import pytest
from pydantic import ValidationError

from app.schemas.athlete import (
    AthleteLookupRequest,
    AthleteLookupResponse,
    AthleteMatch,
)
from app.schemas.evaluation import (
    EvaluationDraft,
    EvaluationDraftRequest,
    EvaluationDraftResponse,
)
from app.schemas.session import ResolutionStatus, SessionContext
from app.schemas.tool_inputs import ToolInputEnvelope, ToolName
from app.schemas.tool_outputs import ToolOutputEnvelope


def test_session_context_defaults_to_pending_confirmation() -> None:
    session = SessionContext(
        session_id="session-1",
        org_id="org-1",
        coach_id="coach-1",
    )

    assert session.resolution_status is ResolutionStatus.PENDING_CONFIRMATION


def test_athlete_lookup_request_strips_query_whitespace() -> None:
    lookup = AthleteLookupRequest(
        org_id="org-1",
        query="  Jane Doe  ",
    )

    assert lookup.query == "Jane Doe"
    assert lookup.max_results == 5


def test_athlete_lookup_response_requires_selected_athlete_when_resolved() -> None:
    with pytest.raises(ValidationError):
        AthleteLookupResponse(
            query="Jane Doe",
            status=ResolutionStatus.RESOLVED,
        )


def test_evaluation_draft_request_rejects_invalid_ratings() -> None:
    with pytest.raises(ValidationError):
        EvaluationDraftRequest(
            org_id="org-1",
            coach_id="coach-1",
            team_id="team-1",
            athlete_id="athlete-1",
            scorecard_template_id="template-1",
            items=[
                {
                    "skill_id": "skill-1",
                    "rating": 6,
                }
            ],
        )


def test_evaluation_draft_response_requires_draft_for_pending_confirmation() -> None:
    with pytest.raises(ValidationError):
        EvaluationDraftResponse(
            status=ResolutionStatus.PENDING_CONFIRMATION,
        )


def test_tool_input_envelope_rejects_mismatched_payload() -> None:
    session = SessionContext(
        session_id="session-1",
        org_id="org-1",
        coach_id="coach-1",
    )
    evaluation_payload = EvaluationDraftRequest(
        org_id="org-1",
        coach_id="coach-1",
        team_id="team-1",
        athlete_id="athlete-1",
        scorecard_template_id="template-1",
        items=[
            {
                "skill_id": "skill-1",
                "rating": 4,
            }
        ],
    )

    with pytest.raises(ValidationError):
        ToolInputEnvelope(
            request_id="request-1",
            tool_name=ToolName.ATHLETE_LOOKUP,
            session=session,
            payload=evaluation_payload,
        )


def test_tool_output_envelope_requires_matching_payload_status() -> None:
    payload = AthleteLookupResponse(
        query="Jane Doe",
        status=ResolutionStatus.AMBIGUOUS,
        matches=[
            AthleteMatch(
                athlete_id="athlete-1",
                full_name="Jane Doe",
                team_id="team-1",
            )
        ],
    )

    with pytest.raises(ValidationError):
        ToolOutputEnvelope(
            request_id="request-1",
            tool_name=ToolName.ATHLETE_LOOKUP,
            status=ResolutionStatus.RESOLVED,
            payload=payload,
        )


def test_tool_output_envelope_accepts_evaluation_draft_payload() -> None:
    payload = EvaluationDraftResponse(
        status=ResolutionStatus.PENDING_CONFIRMATION,
        draft=EvaluationDraft(
            org_id="org-1",
            coach_id="coach-1",
            team_id="team-1",
            athlete_id="athlete-1",
            scorecard_template_id="template-1",
            items=[
                {
                    "skill_id": "skill-1",
                    "rating": 4,
                }
            ],
        ),
    )

    envelope = ToolOutputEnvelope(
        request_id="request-1",
        tool_name=ToolName.EVALUATION_DRAFT,
        status=ResolutionStatus.PENDING_CONFIRMATION,
        payload=payload,
    )

    assert envelope.payload == payload
