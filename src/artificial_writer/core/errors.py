"""Domain-specific exception hierarchy for clear, catchable error handling."""

from __future__ import annotations


class ArtificialWriterError(Exception):
    """Base class for all errors raised by this package."""


class FetchError(ArtificialWriterError):
    """Raised when text cannot be retrieved or extracted from a URL."""


class SummarizationError(ArtificialWriterError):
    """Raised when a summarizer backend fails to produce a summary."""


class ConfigurationError(ArtificialWriterError):
    """Raised when a selected backend is misconfigured (e.g. missing API key)."""
