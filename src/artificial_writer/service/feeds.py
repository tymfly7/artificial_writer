"""RSS/Atom parsing and new-entry diffing helpers.

Kept separate from the job task so the polling logic stays thin and testable:
:func:`parse_feed` turns a feed URL into a list of :class:`FeedEntry`, and
:func:`new_entries` filters out the ones already recorded in a feed's
``seen_entry_ids``. ``feedparser`` is imported lazily so it stays an optional
dependency of the ``server`` extra.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FeedEntry:
    """One entry from a parsed feed, reduced to what polling needs."""

    id: str  # stable identifier: the entry's id/guid, falling back to its link
    title: str
    link: str


def _entry_id(entry: object) -> str:
    """Pick a stable identifier for a feedparser entry (id/guid, else link)."""
    get = getattr(entry, "get", None)
    if get is None:
        return ""
    return str(get("id") or get("link") or "")


def parse_feed(rss_url: str) -> list[FeedEntry]:
    """Fetch and parse ``rss_url`` into :class:`FeedEntry` rows."""
    import feedparser

    parsed = feedparser.parse(rss_url)
    entries: list[FeedEntry] = []
    for entry in parsed.entries:
        link = str(entry.get("link") or "")
        identifier = _entry_id(entry)
        if not identifier:
            continue
        entries.append(
            FeedEntry(id=identifier, title=str(entry.get("title") or "Untitled"), link=link)
        )
    return entries


def new_entries(
    entries: Sequence[FeedEntry], seen_entry_ids: Iterable[str]
) -> list[FeedEntry]:
    """Return entries whose id is not already in ``seen_entry_ids``."""
    seen = set(seen_entry_ids)
    return [entry for entry in entries if entry.id not in seen]
