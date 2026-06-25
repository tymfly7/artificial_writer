"""Persist fetched articles and their summaries to disk."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str, fallback: str = "article") -> str:
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return (slug or fallback)[:60]


class Storage:
    """Read and write text files within a base output directory."""

    def __init__(self, base_dir: str | Path = "output") -> None:
        self.base_dir = Path(base_dir)

    def save(self, filename: str, content: str) -> Path:
        """Write ``content`` to ``filename`` inside the base directory."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / filename
        path.write_text(content, encoding="utf-8")
        logger.info("Saved %s (%d chars)", path, len(content))
        return path

    def read(self, filename: str) -> str:
        """Read and return the contents of ``filename`` in the base directory."""
        path = self.base_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"No such file: {path}")
        return path.read_text(encoding="utf-8")

    def save_summary(self, title: str, original: str, summary: str) -> Path:
        """Save the original text and summary to a single timestamped file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{_slugify(title)}.txt"
        body = (
            f"# {title}\n\n"
            f"## Summary\n\n{summary}\n\n"
            f"## Original\n\n{original}\n"
        )
        return self.save(filename, body)
