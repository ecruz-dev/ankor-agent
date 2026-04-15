"""Evaluation draft models."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.session import ResolutionStatus


class EvaluationItemDraft(BaseModel):
    """A single skill rating captured in an evaluation draft."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    skill_id: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    comments: str | None = None


class EvaluationDraft(BaseModel):
    """The current draft of an athlete evaluation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    org_id: str = Field(min_length=1)
    coach_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)
    athlete_id: str = Field(min_length=1)
    scorecard_template_id: str = Field(min_length=1)
    notes: str | None = None
    items: list[EvaluationItemDraft] = Field(min_length=1)


class EvaluationDraftRequest(EvaluationDraft):
    """Incoming request to draft or revise an evaluation."""


class EvaluationDraftResponse(BaseModel):
    """Draft output returned from the evaluation flow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: ResolutionStatus
    draft: EvaluationDraft | None = None
    confirmation_prompt: str | None = None

    @model_validator(mode="after")
    def validate_status_requirements(self) -> Self:
        """Require a draft when the flow has a usable result."""
        if (
            self.status
            in {
                ResolutionStatus.RESOLVED,
                ResolutionStatus.PENDING_CONFIRMATION,
            }
            and self.draft is None
        ):
            raise ValueError(
                "draft is required when status is resolved or pending_confirmation"
            )
        return self
