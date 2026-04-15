"""Framework-agnostic guardrails for evaluation agent decisions."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from app.schemas.session import ConfirmationStatus, ResolutionStatus

FINALIZE_EVALUATION_TOOL = "finalize_evaluation"
ATHLETE_RESOLUTION_TOOLS = frozenset(
    {"create_evaluation_draft", "finalize_evaluation"}
)
TEMPLATE_RESOLUTION_TOOLS = frozenset(
    {"create_evaluation_draft", "finalize_evaluation"}
)


@dataclass(frozen=True, slots=True)
class ToolRequestValidation:
    """Validation result for a requested tool call."""

    allowed: bool
    reason: str | None = None


def requires_confirmation(tool_name: str) -> bool:
    """Return whether the requested tool needs explicit user confirmation."""
    return tool_name == FINALIZE_EVALUATION_TOOL


def can_finalize(
    *,
    explicit_confirmation: bool,
    confirmation_status: ConfirmationStatus = ConfirmationStatus.NONE,
    athlete_status: ResolutionStatus,
    template_status: ResolutionStatus,
) -> bool:
    """Return whether finalization is allowed for the current session context."""
    return (
        (explicit_confirmation or confirmation_status is ConfirmationStatus.ACCEPTED)
        and athlete_status is ResolutionStatus.RESOLVED
        and template_status is ResolutionStatus.RESOLVED
    )


def validate_tool_request(
    tool_name: str,
    *,
    available_tool_names: Collection[str],
    athlete_status: ResolutionStatus = ResolutionStatus.RESOLVED,
    template_status: ResolutionStatus = ResolutionStatus.RESOLVED,
    explicit_confirmation: bool = False,
    confirmation_status: ConfirmationStatus = ConfirmationStatus.NONE,
) -> ToolRequestValidation:
    """Validate whether a tool call is safe to execute."""
    if tool_name not in available_tool_names:
        return ToolRequestValidation(
            allowed=False,
            reason="Requested tool is not registered.",
        )

    if tool_name in ATHLETE_RESOLUTION_TOOLS and athlete_status is not ResolutionStatus.RESOLVED:
        return ToolRequestValidation(
            allowed=False,
            reason="Athlete identity is not resolved. Ask for clarification or use tools first.",
        )

    if tool_name in TEMPLATE_RESOLUTION_TOOLS and template_status is not ResolutionStatus.RESOLVED:
        return ToolRequestValidation(
            allowed=False,
            reason="Evaluation template is not resolved. Clarify the template before proceeding.",
        )

    if requires_confirmation(tool_name) and not can_finalize(
        explicit_confirmation=explicit_confirmation,
        confirmation_status=confirmation_status,
        athlete_status=athlete_status,
        template_status=template_status,
    ):
        return ToolRequestValidation(
            allowed=False,
            reason=(
                "Explicit confirmation is required before finalizing an evaluation."
                if confirmation_status is not ConfirmationStatus.PENDING
                else "Finalization is waiting for explicit confirmation from the coach."
            ),
        )

    return ToolRequestValidation(allowed=True)
