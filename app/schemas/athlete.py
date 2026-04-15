"""Athlete lookup models."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.session import ResolutionStatus


class AthleteLookupRequest(BaseModel):
    """Normalized athlete lookup input for the voice flow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    org_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    team_id: str | None = None
    max_results: int = Field(default=5, ge=1, le=10)


class AthleteMatch(BaseModel):
    """A candidate athlete returned from a lookup."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    athlete_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    team_id: str | None = None
    team_name: str | None = None
    position: str | None = None
    graduation_year: int | None = Field(default=None, ge=2000, le=2100)


class AthleteLookupResponse(BaseModel):
    """Lookup result returned to the calling layer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1)
    status: ResolutionStatus
    selected_athlete: AthleteMatch | None = None
    matches: list[AthleteMatch] = Field(default_factory=list)
    clarification_prompt: str | None = None

    @model_validator(mode="after")
    def validate_status_requirements(self) -> Self:
        """Keep lookup responses internally consistent."""
        if (
            self.status is ResolutionStatus.RESOLVED
            and self.selected_athlete is None
        ):
            raise ValueError(
                "selected_athlete is required when status is resolved"
            )
        if (
            self.status
            in {
                ResolutionStatus.AMBIGUOUS,
                ResolutionStatus.PENDING_CONFIRMATION,
            }
            and not self.matches
            and self.selected_athlete is None
        ):
            raise ValueError(
                "matches or selected_athlete is required for unresolved lookups"
            )
        if (
            self.status is ResolutionStatus.NOT_FOUND
            and self.selected_athlete is not None
        ):
            raise ValueError(
                "selected_athlete must be omitted when status is not_found"
            )
        return self
