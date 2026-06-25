"""Convenience launcher for the desktop GUI.

Equivalent to running ``python -m artificial_writer.gui`` after installing the
package. Kept at the repo root so ``python main.py`` works from a fresh clone
once dependencies are installed (``pip install -e .``).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from artificial_writer.gui import main  # noqa: E402

if __name__ == "__main__":
    main()
