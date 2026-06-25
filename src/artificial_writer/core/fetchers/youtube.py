"""Fetch a YouTube video transcript as article text.

``youtube_transcript_api`` is imported lazily so the ``youtube`` extra stays
optional. We deliberately make no extra network calls for a title — the URL (or
video id) is good enough.
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse

from ..errors import FetchError
from .base import FetchedArticle

logger = logging.getLogger(__name__)


def _video_id(url: str) -> str:
    """Extract the 11-ish-char video id from a YouTube URL."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "youtu.be" in host:
        candidate = parsed.path.lstrip("/").split("/", 1)[0]
    elif parsed.path.startswith(("/embed/", "/shorts/", "/v/")):
        candidate = parsed.path.split("/")[2]
    else:
        candidate = (parse_qs(parsed.query).get("v") or [""])[0]

    if not candidate:
        raise FetchError(f"Could not find a YouTube video id in {url!r}.")
    return candidate


class YouTubeFetcher:
    """Fetch and join a video's transcript segments into text."""

    def fetch(self, url: str) -> FetchedArticle:
        """Fetch the transcript for the video at ``url``.

        Raises:
            FetchError: if the id can't be parsed or the transcript is unavailable.
        """
        video_id = _video_id(url)
        logger.info("Fetching YouTube transcript for %s", video_id)

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError as exc:  # pragma: no cover - import guard
            raise FetchError(
                "The 'youtube-transcript-api' package is not installed. Install it with "
                "`pip install artificial-writer[youtube]`."
            ) from exc

        try:
            segments = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as exc:  # noqa: BLE001 - surface any API error uniformly
            raise FetchError(f"Failed to fetch transcript for {url}: {exc}") from exc

        text = " ".join(
            (segment.get("text") if isinstance(segment, dict) else getattr(segment, "text", ""))
            or ""
            for segment in segments
        ).strip()
        if not text:
            raise FetchError(f"No transcript text found for {url}.")

        return FetchedArticle(url=url, title=url, text=text)
