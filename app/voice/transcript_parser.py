"""Parser for provider transcript payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.voice.events import TranscriptFinalEvent, TranscriptPartialEvent


class TranscriptParser:
    """Parse provider transcript payloads into typed partial/final events."""

    _TRANSCRIPT_TYPES = frozenset(
        {
            "transcript",
            "transcript_partial",
            "transcript_final",
        }
    )
    _FINAL_TYPES = frozenset({"transcript_final"})

    def parse_event(
        self,
        payload: Mapping[str, Any],
        *,
        session_id: str,
    ) -> TranscriptPartialEvent | TranscriptFinalEvent | None:
        """Return a transcript event when the payload represents speech text."""
        root = _unwrap_payload(payload)
        event_type = _normalize_event_type(root)
        transcript_text = _extract_text(root)
        is_final = _extract_is_final(root)

        if transcript_text is None:
            return None

        if event_type is None and is_final is None:
            return None

        if event_type is not None and event_type not in self._TRANSCRIPT_TYPES:
            return None

        confidence = _extract_confidence(root)
        provider_event_id = _extract_string(
            root,
            "provider_event_id",
            "event_id",
            "id",
        )

        if event_type in self._FINAL_TYPES or is_final is True:
            return TranscriptFinalEvent(
                session_id=session_id,
                text=transcript_text,
                confidence=confidence,
                provider_event_id=provider_event_id,
            )

        return TranscriptPartialEvent(
            session_id=session_id,
            text=transcript_text,
            confidence=confidence,
            provider_event_id=provider_event_id,
        )


def _unwrap_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    root = payload
    for key in ("event", "payload"):
        nested = root.get(key)
        if isinstance(nested, Mapping):
            root = nested
    return root


def _normalize_event_type(payload: Mapping[str, Any]) -> str | None:
    raw_type = _extract_string(payload, "type", "event_type", "kind")
    if raw_type is None:
        return None
    return raw_type.lower().replace(".", "_").replace("-", "_")


def _extract_text(payload: Mapping[str, Any]) -> str | None:
    for key in ("text", "transcript"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Mapping):
            nested_text = _extract_text(value)
            if nested_text is not None:
                return nested_text

    alternatives = payload.get("alternatives")
    if isinstance(alternatives, list):
        for alternative in alternatives:
            if isinstance(alternative, Mapping):
                text = _extract_text(alternative)
                if text is not None:
                    return text

    return None


def _extract_is_final(payload: Mapping[str, Any]) -> bool | None:
    for key in ("is_final", "final"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return None


def _extract_confidence(payload: Mapping[str, Any]) -> float | None:
    value = payload.get("confidence")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _extract_string(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
