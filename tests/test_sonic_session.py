import asyncio

from app.clients.bedrock_client import (
    BedrockClient,
    BedrockSessionConfig,
    StubBedrockBidirectionalStream,
)
from app.voice.events import (
    AssistantAudioReplyEvent,
    AssistantTextReplyEvent,
    ToolRequestTriggerEvent,
    TranscriptPartialEvent,
)
from app.voice.sonic_session import SonicSession


def test_sonic_session_forwards_audio_and_emits_typed_events() -> None:
    async def run_test() -> None:
        stream = StubBedrockBidirectionalStream()
        client = BedrockClient(stream_factory=lambda _: stream)
        session = SonicSession(
            config=BedrockSessionConfig(session_id="session-1"),
            bedrock_client=client,
        )

        await session.start()
        queued_event = await session.send_audio_chunk(
            b"\x00\x01",
            chunk_index=0,
            is_end_of_turn=True,
        )
        await asyncio.sleep(0)

        assert len(stream.sent_audio_events) == 1
        assert stream.sent_audio_events[0] == queued_event

        await stream.push_provider_event(
            {
                "type": "transcript.partial",
                "text": "Jane",
            }
        )
        await stream.push_provider_event(
            {
                "type": "assistant.text",
                "text": "I found Jane Doe on varsity.",
            }
        )
        await stream.finish()

        first_event = await session.next_event()
        second_event = await session.next_event()
        end_of_stream = await session.next_event()

        assert isinstance(first_event, TranscriptPartialEvent)
        assert first_event.text == "Jane"
        assert isinstance(second_event, AssistantTextReplyEvent)
        assert second_event.text == "I found Jane Doe on varsity."
        assert end_of_stream is None

        await session.aclose()
        assert stream.is_closed is True

    asyncio.run(run_test())


def test_sonic_session_parses_tool_and_audio_events() -> None:
    async def run_test() -> None:
        stream = StubBedrockBidirectionalStream()
        client = BedrockClient(stream_factory=lambda _: stream)
        session = SonicSession(
            config=BedrockSessionConfig(session_id="session-2"),
            bedrock_client=client,
        )

        await session.start()
        await stream.push_provider_event(
            {
                "type": "tool.request",
                "tool_name": "find_athlete",
                "arguments": {"query": "Jane Doe"},
                "request_id": "tool-1",
            }
        )
        await stream.push_provider_event(
            {
                "type": "assistant.audio",
                "audio_bytes": b"\x10\x11",
                "sequence_number": 2,
                "mime_type": "audio/pcm",
                "is_final_chunk": True,
            }
        )
        await stream.finish()

        tool_event = await session.next_event()
        audio_event = await session.next_event()
        end_of_stream = await session.next_event()

        assert isinstance(tool_event, ToolRequestTriggerEvent)
        assert tool_event.tool_name == "find_athlete"
        assert tool_event.arguments == {"query": "Jane Doe"}
        assert tool_event.request_id == "tool-1"
        assert isinstance(audio_event, AssistantAudioReplyEvent)
        assert audio_event.sequence_number == 2
        assert audio_event.is_final_chunk is True
        assert end_of_stream is None

        await session.aclose()

    asyncio.run(run_test())
