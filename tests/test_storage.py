"""Tests for the file storage helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from artificial_writer.core.storage import Storage


def test_save_and_read_roundtrip(tmp_path: Path) -> None:
    storage = Storage(base_dir=tmp_path)
    path = storage.save("note.txt", "hello world")

    assert path.exists()
    assert storage.read("note.txt") == "hello world"


def test_read_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Storage(base_dir=tmp_path).read("nope.txt")


def test_save_summary_creates_slugged_file(tmp_path: Path) -> None:
    storage = Storage(base_dir=tmp_path)
    path = storage.save_summary("Hello, World!", "the original", "the summary")

    assert path.suffix == ".txt"
    assert "hello-world" in path.name
    content = path.read_text(encoding="utf-8")
    assert "the summary" in content
    assert "the original" in content
