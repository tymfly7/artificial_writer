"""FastAPI application exposing a JSON API and a small HTML front-end.

Run with::

    uvicorn artificial_writer.web.app:app --reload

or via the helper::

    python -m artificial_writer.web
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl

from ..config import Settings, SummarizerType, get_settings
from ..errors import ArtificialWriterError
from ..pipeline import Pipeline, PipelineResult

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Artificial Writer", version="1.0.0")


class SummarizeRequest(BaseModel):
    url: HttpUrl
    summarizer: SummarizerType | None = None
    model: str | None = None  # local model name (Ollama); ignored by other backends


class SummarizeResponse(BaseModel):
    title: str
    url: str
    backend: str
    model: str | None
    elapsed_seconds: float
    summary: str


class FetchRequest(BaseModel):
    url: HttpUrl


class FetchResponse(BaseModel):
    title: str
    url: str
    word_count: int
    text: str


def _build_settings(summarizer: str | None, model: str | None) -> Settings:
    """Apply UI/API overrides without re-validating (mirrors the GUI)."""
    update: dict[str, object] = {}
    if summarizer:
        update["summarizer"] = summarizer
    if model:
        # Applies to the Ollama backend; ignored by others.
        update["ollama_model"] = model
    return get_settings().model_copy(update=update) if update else get_settings()


def _fetch(url: str) -> FetchResponse:
    article = Pipeline(get_settings()).fetch(url)
    return FetchResponse(
        title=article.title,
        url=article.url,
        word_count=article.word_count,
        text=article.text,
    )


def _to_response(result: PipelineResult) -> SummarizeResponse:
    return SummarizeResponse(
        title=result.article.title,
        url=result.article.url,
        backend=result.summary.backend,
        model=result.summary.model,
        elapsed_seconds=round(result.summary.elapsed_seconds, 3),
        summary=result.summary.summary,
    )


def _summarize(url: str, summarizer: str | None, model: str | None = None) -> SummarizeResponse:
    """One-shot: fetch ``url`` and summarize it (used by the JSON API)."""
    result = Pipeline(_build_settings(summarizer, model)).run(url)
    return _to_response(result)


def _summarize_text(
    text: str, title: str, summarizer: str | None, model: str | None
) -> SummarizeResponse:
    """Step two: summarize text already fetched in a previous request."""
    result = Pipeline(_build_settings(summarizer, model)).summarize_text(text, title=title)
    return _to_response(result)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/api/fetch", response_model=FetchResponse)
def api_fetch(req: FetchRequest) -> FetchResponse:
    """JSON API: fetch and clean the article at ``url`` without summarizing."""
    return _fetch(str(req.url))


@app.post("/api/summarize", response_model=SummarizeResponse)
def api_summarize(req: SummarizeRequest) -> SummarizeResponse:
    """JSON API: fetch and summarize the article at ``url``."""
    return _summarize(
        str(req.url),
        req.summarizer.value if req.summarizer else None,
        req.model,
    )


def _render(
    request: Request,
    *,
    article: FetchResponse | None = None,
    result: SummarizeResponse | None = None,
    error: str | None = None,
    url: str = "",
) -> HTMLResponse:
    return _TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "backends": [s.value for s in SummarizerType],
            "ollama_model": get_settings().ollama_model,
            "article": article,
            "result": result,
            "error": error,
            "url": url,
        },
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Render the empty web form."""
    return _render(request)


@app.post("/", response_class=HTMLResponse)
def submit(
    request: Request,
    action: str = Form("fetch"),
    url: str = Form(""),
    summarizer: str = Form(""),
    model: str = Form(""),
    article_text: str = Form(""),
    article_title: str = Form(""),
) -> HTMLResponse:
    """Handle the two-step HTML form: ``fetch`` first, then ``summarize``."""
    article: FetchResponse | None = None
    result: SummarizeResponse | None = None
    error: str | None = None

    try:
        if action == "summarize" and article_text.strip():
            # Step two: summarize the text fetched in the previous request and
            # keep the original on screen alongside the summary.
            article = FetchResponse(
                title=article_title,
                url=url,
                word_count=len(article_text.split()),
                text=article_text,
            )
            result = _summarize_text(
                article_text, article_title, summarizer or None, model or None
            )
        else:
            # Step one: fetch and display the original article text.
            article = _fetch(url)
    except ArtificialWriterError as exc:
        error = str(exc)

    return _render(request, article=article, result=result, error=error, url=url)
