"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the voice service."""

    model_config = SettingsConfigDict(
        env_prefix="ANKOR_VOICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ankor-voice-agent"
    environment: Literal["local", "development", "staging", "production"] = "local"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
