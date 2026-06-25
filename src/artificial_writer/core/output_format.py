"""Output shaping for summaries.

An :class:`OutputFormat` selects the *shape* of a summary (prose, bullets, a
tweet thread, ...) independently of which backend produces it. The default is
:attr:`OutputFormat.PROSE`, which preserves the original behavior.
"""

from __future__ import annotations

from enum import Enum


class OutputFormat(str, Enum):
    """The requested shape of a summary."""

    PROSE = "prose"
    TLDR = "tldr"
    BULLETS = "bullets"
    ELI5 = "eli5"
    QUOTES = "quotes"
    TWEET = "tweet"
    LINKEDIN = "linkedin"
