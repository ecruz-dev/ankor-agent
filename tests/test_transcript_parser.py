from app.voice.events import TranscriptFinalEvent, TranscriptPartialEvent
from app.voice.transcript_parser import TranscriptParser


def test_transcript_parser_returns_partial_event_for_partial_payload() -> None:
    parser = TranscriptParser()

    event = parser.parse_event(
        {
            "type": "transcript.partial",
            "text": "Jane",
            "confidence": 0.42,
        },
        session_id="session-1",
    )

    assert isinstance(event, TranscriptPartialEvent)
    assert event.text == "Jane"
    assert event.confidence == 0.42


def test_transcript_parser_returns_final_event_for_nested_payload() -> None:
    parser = TranscriptParser()

    event = parser.parse_event(
        {
            "event": {
                "type": "transcript",
                "transcript": {"text": "Jane Doe"},
                "is_final": True,
                "id": "provider-1",
            }
        },
        session_id="session-1",
    )

    assert isinstance(event, TranscriptFinalEvent)
    assert event.text == "Jane Doe"
    assert event.provider_event_id == "provider-1"


def test_transcript_parser_ignores_non_transcript_payload() -> None:
    parser = TranscriptParser()

    event = parser.parse_event(
        {
            "type": "assistant.text",
            "text": "I found Jane Doe.",
        },
        session_id="session-1",
    )

    assert event is None
