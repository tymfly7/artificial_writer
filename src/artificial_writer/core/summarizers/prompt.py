"""Shared prompt construction for LLM-based summarizers."""

from __future__ import annotations

_TEMPLATE = (
    "Summarize the following article in clear, concise prose. "
    "Keep it faithful to the source and written in the same language as the text. "
    "Return only the summary, with no preamble.\n\n"
    "ARTICLE:\n{text}"
)


def build_prompt(text: str) -> str:
    """Build a summarization prompt for the given article text."""
    return _TEMPLATE.format(text=text)
