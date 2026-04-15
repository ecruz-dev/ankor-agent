from app.agent.guardrails import (
    FINALIZE_EVALUATION_TOOL,
    can_finalize,
    requires_confirmation,
    validate_tool_request,
)
from app.schemas.session import ConfirmationStatus, ResolutionStatus

AVAILABLE_TOOLS = {
    "find_athlete",
    "list_evaluation_templates",
    "create_evaluation_draft",
    "finalize_evaluation",
}


def test_requires_confirmation_only_for_finalize() -> None:
    assert requires_confirmation(FINALIZE_EVALUATION_TOOL) is True
    assert requires_confirmation("find_athlete") is False


def test_can_finalize_requires_confirmation_and_resolved_state() -> None:
    assert can_finalize(
        explicit_confirmation=True,
        confirmation_status=ConfirmationStatus.NONE,
        athlete_status=ResolutionStatus.RESOLVED,
        template_status=ResolutionStatus.RESOLVED,
    ) is True
    assert can_finalize(
        explicit_confirmation=False,
        confirmation_status=ConfirmationStatus.NONE,
        athlete_status=ResolutionStatus.RESOLVED,
        template_status=ResolutionStatus.RESOLVED,
    ) is False
    assert can_finalize(
        explicit_confirmation=False,
        confirmation_status=ConfirmationStatus.ACCEPTED,
        athlete_status=ResolutionStatus.RESOLVED,
        template_status=ResolutionStatus.RESOLVED,
    ) is True
    assert can_finalize(
        explicit_confirmation=True,
        confirmation_status=ConfirmationStatus.NONE,
        athlete_status=ResolutionStatus.AMBIGUOUS,
        template_status=ResolutionStatus.RESOLVED,
    ) is False
    assert can_finalize(
        explicit_confirmation=True,
        confirmation_status=ConfirmationStatus.NONE,
        athlete_status=ResolutionStatus.RESOLVED,
        template_status=ResolutionStatus.PENDING_CONFIRMATION,
    ) is False


def test_validate_tool_request_rejects_unknown_tool() -> None:
    result = validate_tool_request(
        "missing_tool",
        available_tool_names=AVAILABLE_TOOLS,
    )

    assert result.allowed is False
    assert result.reason == "Requested tool is not registered."


def test_validate_tool_request_rejects_ambiguous_athlete_for_draft() -> None:
    result = validate_tool_request(
        "create_evaluation_draft",
        available_tool_names=AVAILABLE_TOOLS,
        athlete_status=ResolutionStatus.AMBIGUOUS,
    )

    assert result.allowed is False
    assert result.reason == (
        "Athlete identity is not resolved. Ask for clarification or use tools first."
    )


def test_validate_tool_request_rejects_unclear_template_for_draft() -> None:
    result = validate_tool_request(
        "create_evaluation_draft",
        available_tool_names=AVAILABLE_TOOLS,
        template_status=ResolutionStatus.NOT_FOUND,
    )

    assert result.allowed is False
    assert result.reason == (
        "Evaluation template is not resolved. Clarify the template before proceeding."
    )


def test_validate_tool_request_rejects_finalize_without_confirmation() -> None:
    result = validate_tool_request(
        "finalize_evaluation",
        available_tool_names=AVAILABLE_TOOLS,
        explicit_confirmation=False,
        confirmation_status=ConfirmationStatus.NONE,
    )

    assert result.allowed is False
    assert result.reason == (
        "Explicit confirmation is required before finalizing an evaluation."
    )


def test_validate_tool_request_rejects_finalize_while_confirmation_pending() -> None:
    result = validate_tool_request(
        "finalize_evaluation",
        available_tool_names=AVAILABLE_TOOLS,
        explicit_confirmation=False,
        confirmation_status=ConfirmationStatus.PENDING,
    )

    assert result.allowed is False
    assert result.reason == (
        "Finalization is waiting for explicit confirmation from the coach."
    )


def test_validate_tool_request_allows_finalize_when_safe() -> None:
    result = validate_tool_request(
        "finalize_evaluation",
        available_tool_names=AVAILABLE_TOOLS,
        athlete_status=ResolutionStatus.RESOLVED,
        template_status=ResolutionStatus.RESOLVED,
        explicit_confirmation=True,
        confirmation_status=ConfirmationStatus.NONE,
    )

    assert result.allowed is True
    assert result.reason is None
