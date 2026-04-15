"""Prompt asset loaders for the ANKOR evaluation agent."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt_asset(filename: str) -> str:
    """Load a prompt asset from the shared prompts directory."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


@lru_cache
def build_create_evaluation_system_prompt() -> str:
    """Assemble the evaluation system prompt with shared examples."""
    sections = [
        load_prompt_asset("create_evaluation_system.txt"),
        "Clarification Examples:\n" + load_prompt_asset("clarification_examples.txt"),
        "Confirmation Examples:\n" + load_prompt_asset("confirmation_examples.txt"),
    ]
    return "\n\n".join(section for section in sections if section)


CREATE_EVALUATION_SYSTEM_PROMPT = build_create_evaluation_system_prompt()
