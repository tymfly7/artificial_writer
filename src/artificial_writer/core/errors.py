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


class AuthError(ArtificialWriterError):
    """Raised when a request cannot be authenticated (bad/missing credentials)."""


class QuotaExceeded(ArtificialWriterError):
    """Raised when a request violates a user's tier policy or daily caps.

    The ``status`` attribute distinguishes the two cases so front-ends can map
    them to the right HTTP code:

    * :attr:`BACKEND_NOT_ALLOWED` -- the tier may not use the chosen (paid)
      backend at all (HTTP 403 semantics).
    * :attr:`CAP_EXCEEDED` -- a daily request or cost cap has been reached
      (HTTP 429 semantics).
    """

    BACKEND_NOT_ALLOWED = "backend_not_allowed"
    CAP_EXCEEDED = "cap_exceeded"

    def __init__(self, message: str, *, status: str = CAP_EXCEEDED) -> None:
        super().__init__(message)
        self.status = status
