"""Launch the FastAPI web app from a source checkout.

Equivalent to ``python -m artificial_writer.web`` after installing the package
with the ``web`` extra. Kept at the repo root so the web front-end is visible at
a glance and runnable from a fresh clone with::

    python run_web.py

then open http://127.0.0.1:8000.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from artificial_writer.web.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
