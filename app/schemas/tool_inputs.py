"""Tool input envelope models."""

from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.athlete import AthleteLookupRequest
from app.schemas.evaluation import EvaluationDraftRequest
from app.schemas.session import SessionContext


class ToolName(str, Enum):
    """Known internal tool names for the voice service."""

    ATHLETE_LOOKUP = "athlete_lookup"
    EVALUATION_DRAFT = "evaluation_draft"


ToolInputPayload = AthleteLookupRequest | EvaluationDraftRequest


class ToolInputEnvelope(BaseModel):
    """Standard envelope for invoking an internal tool."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str = Field(min_length=1)
    tool_name: ToolName
    session: SessionContext
    payload: ToolInputPayload

    @model_validator(mode="after")
    def validate_payload_matches_tool(self) -> Self:
        """Ensure the payload type matches the selected tool."""
        expected_payloads = {
            ToolName.ATHLETE_LOOKUP: AthleteLookupRequest,
            ToolName.EVALUATION_DRAFT: EvaluationDraftRequest,
        }
        expected_type = expected_payloads[self.tool_name]
        if not isinstance(self.payload, expected_type):
            raise ValueError(
                f"payload must be {expected_type.__name__} for {self.tool_name.value}"
            )
        return self
