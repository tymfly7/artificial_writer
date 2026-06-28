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
    max_input_chars: int = Field(default=80_000, ge=100)
    log_level: str = "INFO"

    # Extractive summarizer.
    extractive_sentences: int = Field(default=5, ge=1)

    # Per-backend input caps (estimated tokens; see summarizers.estimate_tokens).
    # These sit *under* the global ``max_input_chars`` ceiling: text is first
    # trimmed to that ceiling, then to the selected backend's token budget, in
    # both cases cut back to the last full stop. They bound cost and keep the
    # prompt within each backend's context window. The token count is a
    # conservative char-based estimate, not an exact per-model tokenization.
    ollama_max_input_tokens: int = Field(default=8_000, ge=50)
    openai_max_input_tokens: int = Field(default=12_000, ge=50)
    anthropic_max_input_tokens: int = Field(default=24_000, ge=50)

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

    # Multi-tenant service layer (used by artificial_writer.service / the web API).
    database_url: str = "postgresql+asyncpg://aw:aw@localhost:5432/aw"
    redis_url: str = "redis://localhost:6379/0"  # RQ broker + result store
    session_secret: str = "change-me"  # signs the "aw_session" cookie
    default_tier: str = "free"

    # Tier policy: which backends each tier may use and its daily caps. Free tiers
    # are restricted to the offline/free backends and spend nothing; paid tiers
    # unlock the cloud backends up to a daily request count and cost ceiling.
    # Dict/list fields accept JSON in their ``AW_``-prefixed env vars.
    free_backends: list[str] = Field(default_factory=lambda: ["extractive", "ollama"])
    paid_backends: list[str] = Field(default_factory=lambda: ["openai", "anthropic"])
    tier_daily_request_cap: dict[str, int] = Field(
        default_factory=lambda: {"free": 20, "pro": 500}
    )
    tier_daily_cost_cap_usd: dict[str, float] = Field(
        default_factory=lambda: {"free": 0.0, "pro": 5.0}
    )


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
