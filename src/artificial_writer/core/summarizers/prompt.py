"""Shared prompt construction for LLM-based summarizers."""

from __future__ import annotations

from ..output_format import OutputFormat

# The PROSE template is the original, unchanged behavior.
_TEMPLATE = (
    "Summarize the following article in clear, concise prose. "
    "Keep it faithful to the source and written in the same language as the text. "
    "Return only the summary, with no preamble.\n\n"
    "ARTICLE:\n{text}"
)

# Per-format instruction lines. Each replaces the first sentence of the PROSE
# template; the "same language / no preamble" guidance is appended to all of them.
_FORMAT_INSTRUCTIONS: dict[OutputFormat, str] = {
    OutputFormat.TLDR: "Summarize the following article as a single TL;DR sentence.",
    OutputFormat.BULLETS: (
        "Summarize the following article as 5-8 concise bullet points, "
        'each on its own line starting with "- ".'
    ),
    OutputFormat.ELI5: (
        "Summarize the following article so that a 12-year-old can understand it. "
        "Use plain words and short sentences."
    ),
    OutputFormat.QUOTES: (
        "Extract the 3-5 most important verbatim quotes from the following article, "
        'each on its own line starting with "- ".'
    ),
    OutputFormat.TWEET: (
        "Summarize the following article as a tweet thread. Keep each tweet under "
        "280 characters and number them (1/, 2/, ...)."
    ),
    OutputFormat.LINKEDIN: (
        "Summarize the following article as a professional LinkedIn post: an "
        "engaging hook, a few short paragraphs, and a closing takeaway."
    ),
}

_SHARED_GUIDANCE = (
    " Keep it faithful to the source and written in the same language as the text. "
    "Return only the summary, with no preamble.\n\n"
    "ARTICLE:\n{text}"
)


def build_prompt(text: str, fmt: OutputFormat = OutputFormat.PROSE) -> str:
    """Build a summarization prompt for ``text`` in the requested format."""
    if fmt is OutputFormat.PROSE:
        return _TEMPLATE.format(text=text)
    instruction = _FORMAT_INSTRUCTIONS[fmt]
    return (instruction + _SHARED_GUIDANCE).format(text=text)
