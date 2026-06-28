"""Summarizer interface and shared result type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..output_format import OutputFormat

#: Conservative characters-per-token ratio used by :func:`estimate_tokens` and
#: :func:`trim_to_tokens`. English prose averages ~4 chars/token; code and
#: non-English run denser, so we use a smaller divisor to err on the high side.
CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    """Conservative, provider-agnostic estimate of the token count of ``text``.

    There is no single tokenizer shared across the backends (Ollama, OpenAI and
    Anthropic each tokenize differently), so this is a deliberate *safety bound*,
    not an accurate count: we divide by :data:`CHARS_PER_TOKEN` (erring high) and
    floor at the word count. For an exact figure, use a backend's own tokenizer
    (e.g. Anthropic's ``messages.count_tokens``).
    """
    return max(int(len(text) / CHARS_PER_TOKEN), len(text.split()))


def trim_to_sentence(text: str, max_chars: int | None) -> str:
    """Trim ``text`` to at most ``max_chars``, cutting back to the last full stop.

    When ``max_chars`` is ``None`` or the text already fits, it is returned
    (stripped) unchanged. Otherwise we slice to ``max_chars`` and back up to the
    final sentence terminator (``.``/``!``/``?``) so the text is never cut
    mid-word; if none is found we fall back to a hard slice.
    """
    text = text.strip()
    if max_chars is None or len(text) <= max_chars:
        return text

    window = text[:max_chars]
    cut = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
    if cut == -1:
        return window
    return window[: cut + 1]


def trim_to_tokens(text: str, max_tokens: int | None) -> str:
    """Trim ``text`` to roughly ``max_tokens``, cutting back to the last full stop.

    The token budget is converted to a character budget via
    :data:`CHARS_PER_TOKEN` (the inverse of :func:`estimate_tokens`, so a trimmed
    string's estimated token count never exceeds ``max_tokens``) and the actual
    cut is delegated to :func:`trim_to_sentence`. ``None`` means no cap.
    """
    if max_tokens is None:
        return text.strip()
    return trim_to_sentence(text, int(max_tokens * CHARS_PER_TOKEN))


@dataclass(frozen=True)
class SummaryResult:
    """A summary plus metadata about how it was produced."""

    summary: str
    backend: str
    model: str | None = None
    elapsed_seconds: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class Summarizer(ABC):
    """Abstract base class for all summarizer backends.

    Implementations turn a block of text into a shorter summary. Keeping this
    interface tiny is what makes the backends interchangeable across the CLI,
    GUI, and web front-ends.
    """

    #: Stable identifier used in logs, metadata, and the factory.
    name: str = "base"

    #: Per-backend hard cap on input *tokens* (estimated — see
    #: :func:`estimate_tokens`). ``None`` means no cap beyond the pipeline's
    #: global ``AW_MAX_INPUT_CHARS`` ceiling; a value bounds cost and keeps the
    #: prompt within the backend's context window. Subclasses set a default and
    #: the factory may override it from settings.
    max_input_tokens: int | None = None

    def _prepare(self, text: str) -> str:
        """Apply this backend's token cap, trimming to the last full stop."""
        return trim_to_tokens(text, self.max_input_tokens)

    @abstractmethod
    def summarize(
        self, text: str, *, output_format: OutputFormat = OutputFormat.PROSE
    ) -> SummaryResult:
        """Return a :class:`SummaryResult` for ``text``."""
        raise NotImplementedError
