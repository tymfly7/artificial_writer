"""Command-line interface for Artificial Writer.

Examples
--------
    artwriter https://example.com/article
    artwriter https://example.com/article --summarizer ollama --save
    artwriter https://example.com/article --sentences 3 --json
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .config import SummarizerType, configure_logging, get_settings
from .errors import ArtificialWriterError
from .pipeline import Pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="artwriter",
        description="Fetch an article from a URL and summarize it.",
    )
    parser.add_argument("url", help="The http(s) URL of the article to summarize.")
    parser.add_argument(
        "-s",
        "--summarizer",
        choices=[s.value for s in SummarizerType],
        help="Summarizer backend to use (default: from config / extractive).",
    )
    parser.add_argument(
        "-n",
        "--sentences",
        type=int,
        help="Number of sentences for the extractive summarizer.",
    )
    parser.add_argument(
        "--save", action="store_true", help="Save the summary to the output/ directory."
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit the result as JSON instead of text."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    args = _build_parser().parse_args(argv)

    # Build settings, letting CLI flags override env/.env values.
    overrides: dict[str, object] = {}
    if args.summarizer:
        overrides["summarizer"] = args.summarizer
    if args.sentences:
        overrides["extractive_sentences"] = args.sentences
    settings = get_settings().model_copy(update=overrides)

    configure_logging(settings.log_level)

    try:
        result = Pipeline(settings).run(args.url, save=args.save)
    except ArtificialWriterError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "url": result.article.url,
                    "title": result.article.title,
                    "backend": result.summary.backend,
                    "model": result.summary.model,
                    "elapsed_seconds": round(result.summary.elapsed_seconds, 3),
                    "summary": result.summary.summary,
                    "saved_path": str(result.saved_path) if result.saved_path else None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"\n{result.article.title}\n{'=' * len(result.article.title)}\n")
        print(result.summary.summary)
        print(
            f"\n[{result.summary.backend}"
            f"{' / ' + result.summary.model if result.summary.model else ''}"
            f" in {result.summary.elapsed_seconds:.2f}s]"
        )
        if result.saved_path:
            print(f"Saved to {result.saved_path}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
