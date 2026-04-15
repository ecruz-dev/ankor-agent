"""Tool for finalizing an existing evaluation draft."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.clients.ankor_backend import (
    AnkorBackendClient,
    FinalizeEvaluationResponse,
)


class FinalizeEvaluationInput(BaseModel):
    """Input required to finalize a previously created evaluation draft."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evaluation_id: str = Field(min_length=1)


class FinalizeEvaluationTool:
    """Use when the user confirms that a draft evaluation should be submitted."""

    name = "finalize_evaluation"
    description = "Finalize a previously created evaluation draft."
    input_model = FinalizeEvaluationInput
    output_model = FinalizeEvaluationResponse

    def __init__(self, client: AnkorBackendClient) -> None:
        self._client = client

    async def run(
        self,
        tool_input: FinalizeEvaluationInput,
    ) -> FinalizeEvaluationResponse:
        """Finalize an evaluation using the ANKOR backend client."""
        return await self._client.finalize_evaluation(
            evaluation_id=tool_input.evaluation_id
        )
