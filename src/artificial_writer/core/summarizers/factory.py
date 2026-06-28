"""Construct a summarizer backend from application settings."""

from __future__ import annotations

from ..config import Settings, SummarizerType, get_settings
from ..errors import ConfigurationError
from .base import Summarizer
from .extractive import ExtractiveSummarizer


def build_summarizer(settings: Settings | None = None) -> Summarizer:
    """Return the :class:`Summarizer` selected in ``settings``.

    Provider SDKs are imported lazily inside each backend, so selecting the
    default extractive summarizer never requires optional dependencies.
    """
    settings = settings or get_settings()

    # ``settings.summarizer`` may arrive as a plain string (e.g. from a UI
    # dropdown via ``model_copy``, which does not re-validate). Coerce it to the
    # enum here, case-insensitively, so all front-ends select backends reliably.
    try:
        kind = SummarizerType(settings.summarizer.lower())
    except ValueError as exc:
        choices = ", ".join(s.value for s in SummarizerType)
        raise ConfigurationError(
            f"Unknown summarizer: {settings.summarizer!r}. Choose one of: {choices}."
        ) from exc

    if kind is SummarizerType.EXTRACTIVE:
        return ExtractiveSummarizer(num_sentences=settings.extractive_sentences)

    if kind is SummarizerType.OLLAMA:
        from .ollama import OllamaSummarizer

        return OllamaSummarizer(
            model=settings.ollama_model,
            host=settings.ollama_host,
            timeout=settings.request_timeout * 4,
            max_input_tokens=settings.ollama_max_input_tokens,
        )

    if kind is SummarizerType.OPENAI:
        from .openai_provider import OpenAISummarizer

        return OpenAISummarizer(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_input_tokens=settings.openai_max_input_tokens,
        )

    if kind is SummarizerType.ANTHROPIC:
        from .anthropic_provider import AnthropicSummarizer

        return AnthropicSummarizer(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            max_input_tokens=settings.anthropic_max_input_tokens,
        )

    raise ConfigurationError(f"Unknown summarizer: {kind!r}")  # pragma: no cover
