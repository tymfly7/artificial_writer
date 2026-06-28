"""Tests for the FastAPI web app (skipped if web extras are not installed)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from artificial_writer.core.fetcher import FetchedArticle  # noqa: E402
from artificial_writer.core.output_format import OutputFormat  # noqa: E402
from artificial_writer.core.pipeline import PipelineResult  # noqa: E402
from artificial_writer.core.summarizers.base import SummaryResult  # noqa: E402
from artificial_writer.web import app as web_app  # noqa: E402


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    def fake_run(
        self: object,
        url: str,
        *,
        save: bool = False,
        output_format: OutputFormat = OutputFormat.PROSE,
    ) -> PipelineResult:
        return PipelineResult(
            article=FetchedArticle(url=url, title="Web Title", text="body"),
            summary=SummaryResult(summary="web summary", backend="extractive"),
        )

    def fake_fetch(self: object, url: str) -> FetchedArticle:
        return FetchedArticle(url=url, title="Web Title", text="hello world body")

    def fake_summarize_text(
        self: object,
        text: str,
        *,
        title: str = "Untitled",
        save: bool = False,
        output_format: OutputFormat = OutputFormat.PROSE,
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


def test_console_renders(client: TestClient) -> None:
    # The browser console is a static page that drives the JSON API client-side;
    # it renders without auth (the page itself does the login/register calls).
    resp = client.get("/app")
    assert resp.status_code == 200
    for marker in ("/auth/login", "/api/summarize", "/api/archive", "/auth/keys"):
        assert marker in resp.text


def test_api_summarize_requires_auth(client: TestClient) -> None:
    # /api/summarize is now the authenticated, quota-gated endpoint; without a
    # session or API key it rejects the caller (covered end-to-end in
    # test_web_quota.py).
    resp = client.post("/api/summarize", json={"url": "https://example.com/a"})
    assert resp.status_code == 401


def test_ollama_models(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # The picker endpoint polls the local Ollama host; stub that discovery so the
    # test never touches the network.
    monkeypatch.setattr(web_app, "list_ollama_models", lambda *a, **k: ["llama3.2", "phi4"])
    resp = client.get("/ollama/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["models"] == ["llama3.2", "phi4"]
    assert "default" in body


def test_ollama_models_empty_when_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ollama not running -> empty list, still a 200 so the UI degrades gracefully.
    monkeypatch.setattr(web_app, "list_ollama_models", lambda *a, **k: [])
    resp = client.get("/ollama/models")
    assert resp.status_code == 200
    assert resp.json()["models"] == []


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
