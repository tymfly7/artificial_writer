"""Launch the web UI with ``python -m artificial_writer.web``."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("artificial_writer.web.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
