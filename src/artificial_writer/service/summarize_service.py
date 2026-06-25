"""The single entry point the web layer calls to summarize *for a user*.

It applies the user's summarizer/model/output-format choices on top of the
ambient :class:`Settings`, runs the synchronous core :class:`Pipeline` in a
worker thread, persists the result scoped to the user, and returns the stored
row.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings, SummarizerType, get_settings
from ..core.output_format import OutputFormat
from ..core.pipeline import Pipeline, PipelineResult
from . import quotas, repository
from .models import Summary, User

_YOUTUBE_HOSTS = ("youtube.com", "youtu.be")


def _source_type_for_url(url: str) -> str:
    """Classify a URL the same way the fetcher registry dispatches it."""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if any(yt in host for yt in _YOUTUBE_HOSTS):
        return "youtube"
    if parsed.path.lower().endswith(".pdf"):
        return "pdf"
    return "html"


def _build_settings(summarizer: SummarizerType | None, model: str | None) -> Settings:
    """Overlay the caller's summarizer/model choices on the ambient settings."""
    update: dict[str, object] = {}
    if summarizer is not None:
        update["summarizer"] = summarizer
    if model:
        # Route the model name to the field the chosen backend reads.
        if summarizer == SummarizerType.OPENAI:
            update["openai_model"] = model
        elif summarizer == SummarizerType.ANTHROPIC:
            update["anthropic_model"] = model
        else:
            update["ollama_model"] = model
    base = get_settings()
    return base.model_copy(update=update) if update else base


async def summarize_for_user(
    user: User,
    *,
    session: AsyncSession,
    url: str | None = None,
    text: str | None = None,
    output_format: OutputFormat | None = None,
    summarizer: SummarizerType | None = None,
    model: str | None = None,
) -> Summary:
    """Summarize ``url`` (or raw ``text``) for ``user`` and store the result.

    Exactly one of ``url`` / ``text`` must be given.
    """
    if (url is None) == (text is None):
        raise ValueError("Provide exactly one of 'url' or 'text'.")

    fmt = output_format or OutputFormat.PROSE
    settings = _build_settings(summarizer, model)

    # Quota gate: refuse a disallowed backend (403) or an over-cap user (429)
    # before any tokens are spent. This is the only path to a paid backend.
    quotas.assert_backend_allowed(user.tier, settings.summarizer, settings=settings)
    await quotas.assert_within_quota(session, user, settings=settings)

    pipeline = Pipeline(settings)

    if url is not None:
        result: PipelineResult = await asyncio.to_thread(
            pipeline.run, url, output_format=fmt
        )
        source_type = _source_type_for_url(url)
    else:
        assert text is not None
        result = await asyncio.to_thread(
            pipeline.summarize_text, text, output_format=fmt
        )
        source_type = "text"

    await quotas.record_usage(session, user, result.summary)

    return await repository.save_summary(
        session,
        user=user,
        article=result.article,
        result=result.summary,
        output_format=fmt.value,
        source_type=source_type,
    )
