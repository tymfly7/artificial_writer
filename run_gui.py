"""Launch the Tkinter desktop GUI from a source checkout.

Equivalent to ``python -m artificial_writer.gui`` after installing the package.
Kept at the repo root so the desktop front-end is visible at a glance and
runnable from a fresh clone with::

    python run_gui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from artificial_writer.gui.app import main  # noqa: E402

if __name__ == "__main__":
    main()
