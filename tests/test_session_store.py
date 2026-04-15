import asyncio

import pytest

from app.memory.agentcore_memory import AgentCoreMemorySessionStore
from app.memory.models import (
    AssistantReplyEvent,
    ConfirmationStateChangeEvent,
    ToolRequestEvent,
    ToolResultEvent,
    UserUtteranceEvent,
)
from app.memory.session_store import (
    InMemorySessionStore,
    SessionEventMismatchError,
    SessionNotFoundError,
)
from app.schemas.session import ResolutionStatus, SessionContext


def test_in_memory_session_store_creates_session_with_initial_state() -> None:
    async def run_test() -> None:
        store = InMemorySessionStore()

        state = await store.create_session(
            SessionContext(
                session_id="session-1",
                org_id="org-1",
                coach_id="coach-1",
                team_id="team-1",
            )
        )

        assert state.session_id == "session-1"
        assert state.team_id == "team-1"
        assert state.event_count == 0
        assert state.resolution_status is ResolutionStatus.PENDING_CONFIRMATION

    asyncio.run(run_test())


def test_in_memory_session_store_updates_state_from_appended_events() -> None:
    async def run_test() -> None:
        store = InMemorySessionStore()
        context = SessionContext(
            session_id="session-1",
            org_id="org-1",
            coach_id="coach-1",
        )
        await store.create_session(context)

        await store.append_event(
            "session-1",
            UserUtteranceEvent(session_id="session-1", text="Evaluate Jane Doe"),
        )
        await store.append_event(
            "session-1",
            AssistantReplyEvent(
                session_id="session-1",
                text="I found Jane Doe on varsity.",
            ),
        )
        await store.append_event(
            "session-1",
            ToolRequestEvent(
                session_id="session-1",
                tool_name="find_athlete",
                request_id="tool-1",
            ),
        )
        await store.append_event(
            "session-1",
            ConfirmationStateChangeEvent(
                session_id="session-1",
                previous_status=ResolutionStatus.PENDING_CONFIRMATION,
                current_status=ResolutionStatus.RESOLVED,
                reason="Athlete identity confirmed",
            ),
        )
        state = await store.get_session_state("session-1")

        assert state.event_count == 4
        assert state.last_user_utterance == "Evaluate Jane Doe"
        assert state.last_assistant_reply == "I found Jane Doe on varsity."
        assert state.last_tool_name == "find_athlete"
        assert state.resolution_status is ResolutionStatus.RESOLVED
        assert state.last_confirmation_reason == "Athlete identity confirmed"

    asyncio.run(run_test())


def test_in_memory_session_store_lists_events_in_append_order() -> None:
    async def run_test() -> None:
        store = InMemorySessionStore()
        await store.create_session(
            SessionContext(
                session_id="session-1",
                org_id="org-1",
                coach_id="coach-1",
            )
        )
        await store.append_event(
            "session-1",
            UserUtteranceEvent(session_id="session-1", text="Start evaluation"),
        )
        await store.append_event(
            "session-1",
            ToolResultEvent(
                session_id="session-1",
                tool_name="create_evaluation_draft",
                request_id="tool-2",
                payload={"draft_id": "draft-1"},
            ),
        )

        events = await store.list_events("session-1")

        assert len(events) == 2
        assert events[0].event_type.value == "user_utterance"
        assert events[1].event_type.value == "tool_result"

    asyncio.run(run_test())


def test_in_memory_session_store_raises_for_missing_session() -> None:
    async def run_test() -> None:
        store = InMemorySessionStore()

        with pytest.raises(SessionNotFoundError):
            await store.get_session_state("missing-session")

    asyncio.run(run_test())


def test_in_memory_session_store_rejects_mismatched_event_session_id() -> None:
    async def run_test() -> None:
        store = InMemorySessionStore()
        await store.create_session(
            SessionContext(
                session_id="session-1",
                org_id="org-1",
                coach_id="coach-1",
            )
        )

        with pytest.raises(SessionEventMismatchError):
            await store.append_event(
                "session-1",
                UserUtteranceEvent(
                    session_id="other-session",
                    text="This should fail",
                ),
            )

    asyncio.run(run_test())


def test_agentcore_memory_session_store_uses_local_fallback() -> None:
    async def run_test() -> None:
        store = AgentCoreMemorySessionStore()
        await store.create_session(
            SessionContext(
                session_id="session-1",
                org_id="org-1",
                coach_id="coach-1",
            )
        )

        state = await store.append_event(
            "session-1",
            UserUtteranceEvent(
                session_id="session-1",
                text="Find Jane Doe",
            ),
        )

        assert state.last_user_utterance == "Find Jane Doe"
        assert state.event_count == 1

    asyncio.run(run_test())
