"""Conversation orchestration for text-first agent turns."""

from __future__ import annotations

from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any, Protocol

from fastapi import status
from pydantic import BaseModel, ConfigDict, Field

from app.agent.guardrails import FINALIZE_EVALUATION_TOOL, requires_confirmation
from app.memory.models import (
    AssistantReplyEvent,
    ConfirmationStateChangeEvent,
    SessionStateSnapshot,
    ToolRequestEvent,
    ToolResultEvent,
    UserUtteranceEvent,
)
from app.memory.session_store import SessionNotFoundError, SessionStore
from app.schemas.session import ConfirmationStatus, SessionContext
from app.services.confirmation_service import ConfirmationService
from app.services.tool_executor import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutor,
)
from app.utils.errors import AppError


class ConversationAuthContext(BaseModel):
    """Auth and session context supplied for a conversation turn."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=1)
    org_id: str = Field(min_length=1)
    coach_id: str = Field(min_length=1)
    team_id: str | None = None
    active_athlete_id: str | None = None
    active_scorecard_template_id: str | None = None


@dataclass(frozen=True, slots=True)
class AgentTurnResponse:
    """Normalized agent response for one turn stage."""

    assistant_response: str | None = None
    tool_requests: tuple[ToolExecutionRequest, ...] = ()


@dataclass(frozen=True, slots=True)
class ConversationTurnResult:
    """Result returned from a conversation turn."""

    assistant_response: str
    session_state: SessionStateSnapshot
    tool_results: tuple[ToolExecutionResult, ...] = ()


class AgentRunner(Protocol):
    """Callable interface used to run the agent for a turn."""

    def __call__(
        self,
        agent: object,
        *,
        user_text: str,
        session_state: SessionStateSnapshot,
        auth_context: ConversationAuthContext,
        tool_results: tuple[ToolExecutionResult, ...] = (),
    ) -> Awaitable[AgentTurnResponse] | AgentTurnResponse:
        """Execute the agent and return the normalized result."""


class ConversationServiceError(AppError):
    """Raised when the conversation service cannot complete a turn."""


class ConversationService:
    """Coordinate agent calls, confirmation handling, tools, and memory."""

    def __init__(
        self,
        *,
        agent: object,
        session_store: SessionStore,
        tool_executor: ToolExecutor,
        confirmation_service: ConfirmationService | None = None,
        agent_runner: AgentRunner | None = None,
    ) -> None:
        self._agent = agent
        self._session_store = session_store
        self._tool_executor = tool_executor
        self._confirmation_service = confirmation_service or ConfirmationService()
        self._agent_runner = agent_runner or default_agent_runner

    async def handle_turn(
        self,
        *,
        user_text: str,
        auth_context: ConversationAuthContext,
    ) -> ConversationTurnResult:
        """Run one text conversation turn and persist memory events."""
        session_state = await self._load_session_state(auth_context)
        session_state = await self._session_store.append_event(
            auth_context.session_id,
            UserUtteranceEvent(
                session_id=auth_context.session_id,
                text=user_text,
            ),
        )

        explicit_confirmation = False
        resolution = self._confirmation_service.resolve_confirmation(
            session_state,
            user_text=user_text,
        )
        if resolution is not None:
            session_state = await self._session_store.append_event(
                auth_context.session_id,
                resolution.event,
            )
            explicit_confirmation = resolution.explicit_confirmation
            if resolution.assistant_response is not None:
                session_state = await self._session_store.append_event(
                    auth_context.session_id,
                    AssistantReplyEvent(
                        session_id=auth_context.session_id,
                        text=resolution.assistant_response,
                    ),
                )
                return ConversationTurnResult(
                    assistant_response=resolution.assistant_response,
                    session_state=session_state,
                )

        initial_response = await self._run_agent(
            user_text=user_text,
            session_state=session_state,
            auth_context=auth_context,
        )

        tool_results: list[ToolExecutionResult] = []
        final_response = initial_response

        if initial_response.tool_requests:
            maybe_prompt = await self._maybe_prompt_for_confirmation(
                tool_requests=initial_response.tool_requests,
                session_state=session_state,
                auth_context=auth_context,
                explicit_confirmation=explicit_confirmation,
            )
            if maybe_prompt is not None:
                return maybe_prompt

            tool_results = await self._execute_tool_requests(
                tool_requests=initial_response.tool_requests,
                auth_context=auth_context,
                session_state=session_state,
                explicit_confirmation=explicit_confirmation,
            )
            final_state = await self._session_store.get_session_state(
                auth_context.session_id
            )
            final_response = await self._run_agent(
                user_text=user_text,
                session_state=final_state,
                auth_context=auth_context,
                tool_results=tuple(tool_results),
            )

        assistant_response = (
            final_response.assistant_response or initial_response.assistant_response
        )
        if not assistant_response:
            raise ConversationServiceError(
                "Agent did not return an assistant response.",
                error_code="conversation_response_missing",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        session_state = await self._session_store.append_event(
            auth_context.session_id,
            AssistantReplyEvent(
                session_id=auth_context.session_id,
                text=assistant_response,
            ),
        )
        return ConversationTurnResult(
            assistant_response=assistant_response,
            session_state=session_state,
            tool_results=tuple(tool_results),
        )

    async def _load_session_state(
        self,
        auth_context: ConversationAuthContext,
    ) -> SessionStateSnapshot:
        try:
            return await self._session_store.get_session_state(auth_context.session_id)
        except SessionNotFoundError:
            return await self._session_store.create_session(
                SessionContext(
                    session_id=auth_context.session_id,
                    org_id=auth_context.org_id,
                    coach_id=auth_context.coach_id,
                    team_id=auth_context.team_id,
                    active_athlete_id=auth_context.active_athlete_id,
                    active_scorecard_template_id=auth_context.active_scorecard_template_id,
                )
            )

    async def _run_agent(
        self,
        *,
        user_text: str,
        session_state: SessionStateSnapshot,
        auth_context: ConversationAuthContext,
        tool_results: tuple[ToolExecutionResult, ...] = (),
    ) -> AgentTurnResponse:
        result = self._agent_runner(
            self._agent,
            user_text=user_text,
            session_state=session_state,
            auth_context=auth_context,
            tool_results=tool_results,
        )
        if isawaitable(result):
            result = await result
        return _normalize_agent_turn_response(result)

    async def _maybe_prompt_for_confirmation(
        self,
        *,
        tool_requests: tuple[ToolExecutionRequest, ...],
        session_state: SessionStateSnapshot,
        auth_context: ConversationAuthContext,
        explicit_confirmation: bool,
    ) -> ConversationTurnResult | None:
        for request in tool_requests:
            if not requires_confirmation(request.tool_name):
                continue
            if explicit_confirmation or session_state.confirmation_status is ConfirmationStatus.ACCEPTED:
                continue

            session_state = await self._session_store.append_event(
                auth_context.session_id,
                self._confirmation_service.request_confirmation(
                    session_state,
                    tool_name=request.tool_name,
                ),
            )
            assistant_response = self._confirmation_service.build_confirmation_prompt(
                request.tool_name
            )
            session_state = await self._session_store.append_event(
                auth_context.session_id,
                AssistantReplyEvent(
                    session_id=auth_context.session_id,
                    text=assistant_response,
                ),
            )
            return ConversationTurnResult(
                assistant_response=assistant_response,
                session_state=session_state,
            )
        return None

    async def _execute_tool_requests(
        self,
        *,
        tool_requests: tuple[ToolExecutionRequest, ...],
        auth_context: ConversationAuthContext,
        session_state: SessionStateSnapshot,
        explicit_confirmation: bool,
    ) -> list[ToolExecutionResult]:
        results: list[ToolExecutionResult] = []
        current_state = session_state

        for request in tool_requests:
            await self._session_store.append_event(
                auth_context.session_id,
                ToolRequestEvent(
                    session_id=auth_context.session_id,
                    tool_name=request.tool_name,
                    request_id=request.request_id,
                    arguments=request.arguments,
                ),
            )
            result = await self._tool_executor.execute(
                request,
                explicit_confirmation=explicit_confirmation,
                confirmation_status=current_state.confirmation_status,
                athlete_status=current_state.resolution_status,
                template_status=current_state.resolution_status,
            )
            results.append(result)
            await self._session_store.append_event(
                auth_context.session_id,
                ToolResultEvent(
                    session_id=auth_context.session_id,
                    tool_name=result.tool_name,
                    request_id=result.request_id,
                    success=result.success,
                    payload=result.payload,
                    error_message=result.error_message,
                ),
            )
            if request.tool_name == FINALIZE_EVALUATION_TOOL:
                current_state = await self._session_store.append_event(
                    auth_context.session_id,
                    ConfirmationStateChangeEvent(
                        session_id=auth_context.session_id,
                        previous_confirmation_status=current_state.confirmation_status,
                        current_confirmation_status=ConfirmationStatus.NONE,
                        confirmation_tool_name=request.tool_name,
                        reason="Confirmation state cleared after finalization attempt.",
                    ),
                )
            else:
                current_state = await self._session_store.get_session_state(
                    auth_context.session_id
                )

        return results


async def default_agent_runner(
    agent: object,
    *,
    user_text: str,
    session_state: SessionStateSnapshot,
    auth_context: ConversationAuthContext,
    tool_results: tuple[ToolExecutionResult, ...] = (),
) -> AgentTurnResponse:
    """Run an injected agent object using a small compatibility shim."""
    agent_callable = getattr(agent, "run", None)
    if agent_callable is None and callable(agent):
        agent_callable = agent
    if agent_callable is None:
        raise ConversationServiceError(
            "Configured agent is not callable.",
            error_code="conversation_agent_invalid",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    result = agent_callable(
        user_text=user_text,
        session_state=session_state,
        auth_context=auth_context,
        tool_results=tool_results,
    )
    if isawaitable(result):
        result = await result
    return _normalize_agent_turn_response(result)


def _normalize_agent_turn_response(result: Any) -> AgentTurnResponse:
    if isinstance(result, AgentTurnResponse):
        return result
    if isinstance(result, Mapping):
        assistant_response = result.get("assistant_response")
        if assistant_response is None:
            assistant_response = result.get("response")
        tool_requests = result.get("tool_requests", ())
        return AgentTurnResponse(
            assistant_response=assistant_response,
            tool_requests=tuple(
                _normalize_tool_request(tool_request)
                for tool_request in tool_requests
            ),
        )
    raise ConversationServiceError(
        "Agent returned an unsupported response shape.",
        error_code="conversation_agent_response_invalid",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _normalize_tool_request(tool_request: Any) -> ToolExecutionRequest:
    if isinstance(tool_request, ToolExecutionRequest):
        return tool_request
    if isinstance(tool_request, Mapping):
        return ToolExecutionRequest(
            tool_name=str(tool_request["tool_name"]),
            arguments=dict(tool_request.get("arguments", {})),
            request_id=tool_request.get("request_id"),
        )
    raise ConversationServiceError(
        "Agent returned an invalid tool request.",
        error_code="conversation_tool_request_invalid",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
