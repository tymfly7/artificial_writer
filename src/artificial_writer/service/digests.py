"""Aggregate a set of finished summaries into one stored :class:`Digest`.

A digest is the viewable output of a batch run or a feed poll: a single markdown
document with one section per summary, plus the list of summary ids it was built
from. Both the async batch/feed jobs and (potentially) the web layer build
digests through :func:`build_digest`, so the rendering lives in one place.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from .models import Digest, Summary


def render_body(title: str, summaries: Sequence[Summary]) -> str:
    """Render the markdown body: a heading plus one section per summary."""
    lines = [f"# {title}", ""]
    if not summaries:
        lines.append("_No new articles._")
        return "\n".join(lines)
    for summary in summaries:
        lines.append(f"## {summary.title}")
        lines.append(f"[{summary.source_url}]({summary.source_url})")
        lines.append("")
        lines.append(summary.summary)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


async def build_digest(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    summary_rows: Sequence[Summary],
) -> Digest:
    """Build, persist, and return a :class:`Digest` aggregating ``summary_rows``.

    ``kind`` is ``"batch"`` or ``"feed"``. The digest stores the rendered markdown
    body and the ids of the summaries it covers (as strings, matching the JSON
    column). The caller owns the surrounding transaction (commit).
    """
    digest = Digest(
        user_id=user_id,
        kind=kind,
        title=title,
        body=render_body(title, summary_rows),
        summary_ids=[str(s.id) for s in summary_rows],
    )
    session.add(digest)
    await session.flush()
    return digest
