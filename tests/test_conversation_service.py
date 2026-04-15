import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.clients.ankor_backend import AnkorBackendClient, FinalizeEvaluationResponse
from app.memory.models import ConfirmationStateChangeEvent
from app.memory.session_store import InMemorySessionStore
from app.schemas.session import ConfirmationStatus, ResolutionStatus, SessionContext
from app.services.confirmation_service import ConfirmationService
from app.services.conversation_service import (
    AgentTurnResponse,
    ConversationAuthContext,
    ConversationService,
)
from app.services.tool_executor import ToolExecutionRequest, ToolExecutor
from app.tools.registry import create_tool_registry


def test_conversation_service_requires_confirmation_before_finalize() -> None:
    async def run_test() -> None:
        session_store = InMemorySessionStore()
        client = MagicMock(spec=AnkorBackendClient)
        client.finalize_evaluation = AsyncMock()

        async def agent_runner(
            _: object,
            *,
            user_text: str,
            session_state: object,
            auth_context: ConversationAuthContext,
            tool_results: tuple[object, ...] = (),
        ) -> AgentTurnResponse:
            return AgentTurnResponse(
                tool_requests=(
                    ToolExecutionRequest(
                        tool_name="finalize_evaluation",
                        arguments={"evaluation_id": "evaluation-1"},
                        request_id="tool-1",
                    ),
                ),
            )

        service = ConversationService(
            agent=object(),
            session_store=session_store,
            tool_executor=ToolExecutor(tool_registry=create_tool_registry(client)),
            agent_runner=agent_runner,
        )

        result = await service.handle_turn(
            user_text="Finalize it",
            auth_context=ConversationAuthContext(
                session_id="session-1",
                org_id="org-1",
                coach_id="coach-1",
            ),
        )

        client.finalize_evaluation.assert_not_awaited()
        assert result.assistant_response == (
            "Please confirm that you want me to finalize the evaluation."
        )
        assert result.session_state.confirmation_status is ConfirmationStatus.PENDING
        assert result.session_state.pending_confirmation_tool == "finalize_evaluation"

    asyncio.run(run_test())


def test_conversation_service_accepts_confirmation_and_finalizes() -> None:
    async def run_test() -> None:
        session_store = InMemorySessionStore()
        await session_store.create_session(
            SessionContext(
                session_id="session-1",
                org_id="org-1",
                coach_id="coach-1",
            )
        )
        await session_store.append_event(
            "session-1",
            ConfirmationStateChangeEvent(
                session_id="session-1",
                previous_confirmation_status=ConfirmationStatus.NONE,
                current_confirmation_status=ConfirmationStatus.PENDING,
                confirmation_tool_name="finalize_evaluation",
                reason="Awaiting coach confirmation.",
            ),
        )

        client = MagicMock(spec=AnkorBackendClient)
        client.finalize_evaluation = AsyncMock(
            return_value=FinalizeEvaluationResponse(
                evaluation_id="evaluation-1",
                status="submitted",
                message="Evaluation finalized",
            )
        )

        async def agent_runner(
            _: object,
            *,
            user_text: str,
            session_state: object,
            auth_context: ConversationAuthContext,
            tool_results: tuple[object, ...] = (),
        ) -> AgentTurnResponse:
            if not tool_results:
                return AgentTurnResponse(
                    tool_requests=(
                        ToolExecutionRequest(
                            tool_name="finalize_evaluation",
                            arguments={"evaluation_id": "evaluation-1"},
                            request_id="tool-1",
                        ),
                    ),
                )
            return AgentTurnResponse(
                assistant_response="The evaluation has been finalized.",
            )

        service = ConversationService(
            agent=object(),
            session_store=session_store,
            tool_executor=ToolExecutor(tool_registry=create_tool_registry(client)),
            confirmation_service=ConfirmationService(),
            agent_runner=agent_runner,
        )

        result = await service.handle_turn(
            user_text="yes",
            auth_context=ConversationAuthContext(
                session_id="session-1",
                org_id="org-1",
                coach_id="coach-1",
            ),
        )

        client.finalize_evaluation.assert_awaited_once_with(
            evaluation_id="evaluation-1"
        )
        assert result.assistant_response == "The evaluation has been finalized."
        assert result.session_state.confirmation_status is ConfirmationStatus.NONE
        assert result.tool_results[0].success is True

    asyncio.run(run_test())


def test_conversation_service_denies_confirmation() -> None:
    async def run_test() -> None:
        session_store = InMemorySessionStore()
        await session_store.create_session(
            SessionContext(
                session_id="session-1",
                org_id="org-1",
                coach_id="coach-1",
            )
        )
        await session_store.append_event(
            "session-1",
            ConfirmationStateChangeEvent(
                session_id="session-1",
                previous_confirmation_status=ConfirmationStatus.NONE,
                current_confirmation_status=ConfirmationStatus.PENDING,
                confirmation_tool_name="finalize_evaluation",
                reason="Awaiting coach confirmation.",
            ),
        )

        agent_runner = AsyncMock()
        service = ConversationService(
            agent=object(),
            session_store=session_store,
            tool_executor=ToolExecutor(tool_map={}),
            confirmation_service=ConfirmationService(),
            agent_runner=agent_runner,
        )

        result = await service.handle_turn(
            user_text="no",
            auth_context=ConversationAuthContext(
                session_id="session-1",
                org_id="org-1",
                coach_id="coach-1",
            ),
        )

        agent_runner.assert_not_awaited()
        assert result.assistant_response == "Okay, I won't finalize the evaluation."
        assert result.session_state.confirmation_status is ConfirmationStatus.DENIED
        assert result.session_state.pending_confirmation_tool is None

    asyncio.run(run_test())


def test_tool_executor_blocks_finalize_without_confirmation() -> None:
    async def run_test() -> None:
        client = MagicMock(spec=AnkorBackendClient)
        client.finalize_evaluation = AsyncMock()
        executor = ToolExecutor(tool_registry=create_tool_registry(client))

        result = await executor.execute(
            ToolExecutionRequest(
                tool_name="finalize_evaluation",
                arguments={"evaluation_id": "evaluation-1"},
            ),
            explicit_confirmation=False,
            confirmation_status=ConfirmationStatus.NONE,
            athlete_status=ResolutionStatus.RESOLVED,
            template_status=ResolutionStatus.RESOLVED,
        )

        client.finalize_evaluation.assert_not_awaited()
        assert result.success is False
        assert result.error_message == (
            "Explicit confirmation is required before finalizing an evaluation."
        )

    asyncio.run(run_test())
