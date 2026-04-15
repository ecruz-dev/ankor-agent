"""Tool for creating a draft evaluation."""

from __future__ import annotations

from app.clients.ankor_backend import AnkorBackendClient
from app.schemas.evaluation import EvaluationDraftRequest, EvaluationDraftResponse


class CreateEvaluationDraftTool:
    """Use when the assistant has enough scoring data to draft an evaluation."""

    name = "create_evaluation_draft"
    description = "Create a draft evaluation for an athlete using the backend API."
    input_model = EvaluationDraftRequest
    output_model = EvaluationDraftResponse

    def __init__(self, client: AnkorBackendClient) -> None:
        self._client = client

    async def run(
        self,
        tool_input: EvaluationDraftRequest,
    ) -> EvaluationDraftResponse:
        """Create an evaluation draft using the ANKOR backend client."""
        return await self._client.create_evaluation_draft(tool_input)
