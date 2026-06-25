"""Application configuration loaded from environment variables / a .env file.

All settings are prefixed with ``AW_`` and have sensible defaults so the app
runs with zero configuration using the free, offline extractive summarizer.
"""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SummarizerType(str, Enum):
    """Supported summarizer backends."""

    EXTRACTIVE = "extractive"
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are read (in priority order) from constructor arguments, environment
    variables, then a local ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_prefix="AW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    summarizer: SummarizerType = SummarizerType.EXTRACTIVE
    max_input_chars: int = Field(default=12_000, ge=100)
    log_level: str = "INFO"

    # Extractive summarizer.
    extractive_sentences: int = Field(default=5, ge=1)

    # Ollama (free local LLM).
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # OpenAI (optional).
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Anthropic (optional).
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # Network.
    request_timeout: float = Field(default=30.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()


def configure_logging(level: str | None = None) -> None:
    """Configure root logging once, using the given or configured level."""
    resolved = (level or get_settings().log_level).upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
