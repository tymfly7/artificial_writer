"""Tests for the FastAPI web app (skipped if web extras are not installed)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from artificial_writer.core.fetcher import FetchedArticle  # noqa: E402
from artificial_writer.core.pipeline import PipelineResult  # noqa: E402
from artificial_writer.core.summarizers.base import SummaryResult  # noqa: E402
from artificial_writer.web import app as web_app  # noqa: E402


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    def fake_run(self: object, url: str, save: bool = False) -> PipelineResult:
        return PipelineResult(
            article=FetchedArticle(url=url, title="Web Title", text="body"),
            summary=SummaryResult(summary="web summary", backend="extractive"),
        )

    def fake_fetch(self: object, url: str) -> FetchedArticle:
        return FetchedArticle(url=url, title="Web Title", text="hello world body")

    def fake_summarize_text(
        self: object, text: str, *, title: str = "Untitled", save: bool = False
    ) -> PipelineResult:
        return PipelineResult(
            article=FetchedArticle(url="", title=title, text=text),
            summary=SummaryResult(summary=f"summary of {text}", backend="extractive"),
        )

    monkeypatch.setattr(web_app.Pipeline, "run", fake_run)
    monkeypatch.setattr(web_app.Pipeline, "fetch", fake_fetch)
    monkeypatch.setattr(web_app.Pipeline, "summarize_text", fake_summarize_text)
    return TestClient(web_app.app)


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_index_renders(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Artificial Writer" in resp.text


def test_api_summarize(client: TestClient) -> None:
    resp = client.post("/api/summarize", json={"url": "https://example.com/a"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "web summary"
    assert body["title"] == "Web Title"


def test_api_summarize_accepts_model(client: TestClient) -> None:
    resp = client.post(
        "/api/summarize",
        json={"url": "https://example.com/a", "summarizer": "ollama", "model": "gemma4:e4b"},
    )
    assert resp.status_code == 200


def test_api_fetch(client: TestClient) -> None:
    resp = client.post("/api/fetch", json={"url": "https://example.com/a"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Web Title"
    assert body["text"] == "hello world body"
    assert body["word_count"] == 3


def test_form_fetch_then_summarize(client: TestClient) -> None:
    # Step one: fetch shows the original text.
    fetched = client.post("/", data={"action": "fetch", "url": "https://example.com/a"})
    assert fetched.status_code == 200
    assert "hello world body" in fetched.text

    # Step two: summarize the already-fetched text without re-fetching.
    summarized = client.post(
        "/",
        data={
            "action": "summarize",
            "url": "https://example.com/a",
            "article_title": "Web Title",
            "article_text": "hello world body",
            "summarizer": "extractive",
        },
    )
    assert summarized.status_code == 200
    assert "summary of hello world body" in summarized.text
