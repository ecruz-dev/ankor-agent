"""Tool output envelope models."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.athlete import AthleteLookupResponse
from app.schemas.evaluation import EvaluationDraftResponse
from app.schemas.session import ResolutionStatus
from app.schemas.tool_inputs import ToolName

ToolOutputPayload = AthleteLookupResponse | EvaluationDraftResponse


class ToolOutputEnvelope(BaseModel):
    """Standard envelope for tool execution results."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str = Field(min_length=1)
    tool_name: ToolName
    status: ResolutionStatus
    payload: ToolOutputPayload | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_payload_matches_tool(self) -> Self:
        """Keep envelope metadata aligned with the payload."""
        if self.status is ResolutionStatus.RESOLVED and self.error_message:
            raise ValueError(
                "error_message must be omitted when status is resolved"
            )
        if self.payload is None:
            return self

        expected_payloads = {
            ToolName.ATHLETE_LOOKUP: AthleteLookupResponse,
            ToolName.EVALUATION_DRAFT: EvaluationDraftResponse,
        }
        expected_type = expected_payloads[self.tool_name]
        if not isinstance(self.payload, expected_type):
            raise ValueError(
                f"payload must be {expected_type.__name__} for {self.tool_name.value}"
            )
        if self.payload.status is not self.status:
            raise ValueError("payload status must match envelope status")
        return self
