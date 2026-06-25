"""Summarizer interface and shared result type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryResult:
    """A summary plus metadata about how it was produced."""

    summary: str
    backend: str
    model: str | None = None
    elapsed_seconds: float = 0.0


class Summarizer(ABC):
    """Abstract base class for all summarizer backends.

    Implementations turn a block of text into a shorter summary. Keeping this
    interface tiny is what makes the backends interchangeable across the CLI,
    GUI, and web front-ends.
    """

    #: Stable identifier used in logs, metadata, and the factory.
    name: str = "base"

    @abstractmethod
    def summarize(self, text: str) -> SummaryResult:
        """Return a :class:`SummaryResult` for ``text``."""
        raise NotImplementedError
