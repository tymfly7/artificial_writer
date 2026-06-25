"""Allow ``python -m artificial_writer`` to launch the CLI."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
