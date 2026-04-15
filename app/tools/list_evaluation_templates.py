"""Tool for retrieving evaluation templates available to a session."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.clients.ankor_backend import (
    AnkorBackendClient,
    EvaluationTemplateListResponse,
)


class ListEvaluationTemplatesInput(BaseModel):
    """Input for retrieving evaluation templates from the backend."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    org_id: str = Field(min_length=1)
    team_id: str | None = None


class ListEvaluationTemplatesTool:
    """Use when the assistant needs available templates before drafting."""

    name = "list_evaluation_templates"
    description = (
        "List evaluation templates for the current organization and optional team."
    )
    input_model = ListEvaluationTemplatesInput
    output_model = EvaluationTemplateListResponse

    def __init__(self, client: AnkorBackendClient) -> None:
        self._client = client

    async def run(
        self,
        tool_input: ListEvaluationTemplatesInput,
    ) -> EvaluationTemplateListResponse:
        """Return evaluation templates from the ANKOR backend client."""
        return await self._client.list_evaluation_templates(
            org_id=tool_input.org_id,
            team_id=tool_input.team_id,
        )
