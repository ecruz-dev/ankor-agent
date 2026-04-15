"""Execution layer between agent tool requests and registered tools."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any, Protocol, cast

from pydantic import BaseModel, ValidationError

from app.agent.guardrails import validate_tool_request
from app.schemas.session import ConfirmationStatus, ResolutionStatus
from app.tools.registry import RegisteredTool, ToolRegistry


class ExecutableTool(Protocol):
    """Common executable surface for registered tools."""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    def run(self, tool_input: Any) -> Any:
        """Execute the tool with validated input."""


@dataclass(frozen=True, slots=True)
class ToolExecutionRequest:
    """Normalized tool request emitted by the agent."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Result returned from tool execution."""

    tool_name: str
    success: bool
    request_id: str | None = None
    payload: dict[str, Any] | None = None
    error_message: str | None = None


class ToolExecutor:
    """Validate and execute tool requests against the tool registry."""

    def __init__(
        self,
        *,
        tool_registry: ToolRegistry | None = None,
        tool_map: Mapping[str, RegisteredTool] | None = None,
    ) -> None:
        resolved_map = tool_map or (tool_registry.by_name() if tool_registry else {})
        self._tool_map = {
            name: cast(ExecutableTool, tool)
            for name, tool in resolved_map.items()
        }

    async def execute(
        self,
        request: ToolExecutionRequest,
        *,
        explicit_confirmation: bool = False,
        confirmation_status: ConfirmationStatus = ConfirmationStatus.NONE,
        athlete_status: ResolutionStatus = ResolutionStatus.RESOLVED,
        template_status: ResolutionStatus = ResolutionStatus.RESOLVED,
    ) -> ToolExecutionResult:
        """Validate and execute a tool request."""
        validation = validate_tool_request(
            request.tool_name,
            available_tool_names=self._tool_map.keys(),
            athlete_status=athlete_status,
            template_status=template_status,
            explicit_confirmation=explicit_confirmation,
            confirmation_status=confirmation_status,
        )
        if not validation.allowed:
            return ToolExecutionResult(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=False,
                error_message=validation.reason,
            )

        tool = self._tool_map[request.tool_name]

        try:
            tool_input = tool.input_model.model_validate(request.arguments)
        except ValidationError as exc:
            return ToolExecutionResult(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=False,
                error_message=str(exc),
            )

        try:
            output = tool.run(tool_input)
            if isawaitable(output):
                output = await output
        except Exception as exc:
            return ToolExecutionResult(
                tool_name=request.tool_name,
                request_id=request.request_id,
                success=False,
                error_message=str(exc),
            )

        return ToolExecutionResult(
            tool_name=request.tool_name,
            request_id=request.request_id,
            success=True,
            payload=self._serialize_output(output),
        )

    @staticmethod
    def _serialize_output(output: Any) -> dict[str, Any] | None:
        """Serialize a tool output for memory events and follow-up agent calls."""
        if output is None:
            return None
        if isinstance(output, BaseModel):
            return output.model_dump(mode="json", exclude_none=True)
        if isinstance(output, dict):
            return dict(output)
        return {"value": output}
