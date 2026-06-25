"""Launch the command-line interface from a source checkout.

Equivalent to the installed ``artwriter`` command (and to
``python -m artificial_writer``). Kept at the repo root so the CLI front-end is
visible at a glance and runnable from a fresh clone with::

    python run_cli.py https://example.com/article
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from artificial_writer.cli.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
