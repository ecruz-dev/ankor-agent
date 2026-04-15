"""Registry for all currently available ANKOR backend tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from app.clients.ankor_backend import AnkorBackendClient
from app.tools.create_evaluation_draft import CreateEvaluationDraftTool
from app.tools.finalize_evaluation import FinalizeEvaluationTool
from app.tools.find_athlete import FindAthleteTool
from app.tools.list_evaluation_templates import ListEvaluationTemplatesTool


class RegisteredTool(Protocol):
    """Common surface exposed by each thin tool wrapper."""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]


@dataclass(frozen=True, slots=True)
class ToolRegistry:
    """Container exposing the currently supported backend tools."""

    find_athlete: FindAthleteTool
    list_evaluation_templates: ListEvaluationTemplatesTool
    create_evaluation_draft: CreateEvaluationDraftTool
    finalize_evaluation: FinalizeEvaluationTool

    def all(self) -> tuple[RegisteredTool, ...]:
        """Return all registered tools in a stable order."""
        return (
            self.find_athlete,
            self.list_evaluation_templates,
            self.create_evaluation_draft,
            self.finalize_evaluation,
        )

    def by_name(self) -> dict[str, RegisteredTool]:
        """Return registered tools keyed by tool name."""
        return {tool.name: tool for tool in self.all()}


def create_tool_registry(client: AnkorBackendClient) -> ToolRegistry:
    """Instantiate all currently supported tools for the backend client."""
    return ToolRegistry(
        find_athlete=FindAthleteTool(client),
        list_evaluation_templates=ListEvaluationTemplatesTool(client),
        create_evaluation_draft=CreateEvaluationDraftTool(client),
        finalize_evaluation=FinalizeEvaluationTool(client),
    )


def get_all_tools(client: AnkorBackendClient) -> tuple[RegisteredTool, ...]:
    """Return all tool instances as a simple tuple."""
    return create_tool_registry(client).all()


def get_tool_map(client: AnkorBackendClient) -> dict[str, RegisteredTool]:
    """Return all tool instances keyed by their public names."""
    return create_tool_registry(client).by_name()
