"""Typed event models for bidirectional voice sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, TypeAlias
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    """Return the current UTC timestamp for a voice event."""
    return datetime.now(UTC)


def _new_event_id() -> str:
    """Generate a stable identifier for voice events."""
    return str(uuid4())


class VoiceEventType(str, Enum):
    """Supported event types emitted during a voice session."""

    AUDIO_INPUT_CHUNK = "audio_input_chunk"
    TRANSCRIPT_PARTIAL = "transcript_partial"
    TRANSCRIPT_FINAL = "transcript_final"
    ASSISTANT_TEXT_REPLY = "assistant_text_reply"
    ASSISTANT_AUDIO_REPLY = "assistant_audio_reply"
    TOOL_REQUEST_TRIGGER = "tool_request_trigger"


class AudioEncoding(str, Enum):
    """Minimal set of audio encodings used by the voice layer."""

    PCM_S16LE = "pcm_s16le"
    OPUS = "opus"


class VoiceEvent(BaseModel):
    """Base model shared by all voice session events."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str = Field(default_factory=_new_event_id, min_length=1)
    session_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utc_now)
    event_type: VoiceEventType


class AudioInputChunkEvent(VoiceEvent):
    """Audio chunk submitted by the caller into the voice session."""

    event_type: Literal[VoiceEventType.AUDIO_INPUT_CHUNK] = (
        VoiceEventType.AUDIO_INPUT_CHUNK
    )
    chunk_index: int = Field(ge=0)
    audio_bytes: bytes = Field(min_length=1)
    sample_rate_hz: int = Field(default=16000, gt=0)
    channel_count: int = Field(default=1, gt=0)
    encoding: AudioEncoding = AudioEncoding.PCM_S16LE
    is_end_of_turn: bool = False


class TranscriptEvent(VoiceEvent):
    """Base model for partial and final transcript events."""

    text: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provider_event_id: str | None = None


class TranscriptPartialEvent(TranscriptEvent):
    """Interim transcript emitted while the user is speaking."""

    event_type: Literal[VoiceEventType.TRANSCRIPT_PARTIAL] = (
        VoiceEventType.TRANSCRIPT_PARTIAL
    )


class TranscriptFinalEvent(TranscriptEvent):
    """Final transcript emitted after the provider finalizes speech input."""

    event_type: Literal[VoiceEventType.TRANSCRIPT_FINAL] = (
        VoiceEventType.TRANSCRIPT_FINAL
    )


class AssistantTextReplyEvent(VoiceEvent):
    """Assistant text emitted by the provider for downstream orchestration."""

    event_type: Literal[VoiceEventType.ASSISTANT_TEXT_REPLY] = (
        VoiceEventType.ASSISTANT_TEXT_REPLY
    )
    text: str = Field(min_length=1)


class AssistantAudioReplyEvent(VoiceEvent):
    """Assistant audio emitted by the provider."""

    event_type: Literal[VoiceEventType.ASSISTANT_AUDIO_REPLY] = (
        VoiceEventType.ASSISTANT_AUDIO_REPLY
    )
    audio_bytes: bytes = Field(min_length=1)
    sequence_number: int = Field(default=0, ge=0)
    mime_type: str = Field(default="audio/pcm", min_length=1)
    is_final_chunk: bool = False


class ToolRequestTriggerEvent(VoiceEvent):
    """Tool trigger emitted by the provider or a higher-level voice adapter."""

    event_type: Literal[VoiceEventType.TOOL_REQUEST_TRIGGER] = (
        VoiceEventType.TOOL_REQUEST_TRIGGER
    )
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


VoiceSessionEvent: TypeAlias = (
    TranscriptPartialEvent
    | TranscriptFinalEvent
    | AssistantTextReplyEvent
    | AssistantAudioReplyEvent
    | ToolRequestTriggerEvent
)
