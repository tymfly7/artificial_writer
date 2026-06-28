"""FastAPI application exposing a JSON API and a small HTML front-end.

Run with::

    uvicorn artificial_writer.web.app:app --reload

or via the helper::

    python -m artificial_writer.web
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..core.config import Settings, SummarizerType, get_settings
from ..core.errors import (
    ArtificialWriterError,
    AuthError,
    ConfigurationError,
    FetchError,
    QuotaExceeded,
    SummarizationError,
)
from ..core.output_format import OutputFormat
from ..core.pipeline import Pipeline, PipelineResult
from ..core.summarizers import list_ollama_models
from ..service import quotas
from ..service.schemas import FetchRequest, FetchResponse, SummarizeResponse
from .routers import auth as auth_router
from .routers import batch as batch_router
from .routers import digests as digests_router
from .routers import feeds as feeds_router
from .routers import summarize as summarize_router

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Artificial Writer", version="1.0.0")
app.include_router(auth_router.router)
app.include_router(summarize_router.router)
app.include_router(batch_router.router)
app.include_router(feeds_router.router)
app.include_router(digests_router.router)


def _wants_html(request: Request) -> bool:
    """True for browser navigations; False for API/JSON clients.

    API routes (``/api``, ``/auth``, ``/ollama``, ``/health``) and any client that
    doesn't ask for HTML keep the plain JSON 404 body, so only real page visits
    get the illustrated error page.
    """
    path = request.url.path
    if path.startswith(("/api", "/auth", "/ollama", "/health")):
        return False
    return "text/html" in request.headers.get("accept", "")


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> Response:
    """Render a friendly HTML page for 404s in the browser; JSON otherwise."""
    if exc.status_code == 404 and _wants_html(request):
        return _TEMPLATES.TemplateResponse(
            request, "404.html", {}, status_code=404
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(AuthError)
async def _auth_error_handler(_: Request, exc: AuthError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(QuotaExceeded)
async def _quota_error_handler(_: Request, exc: QuotaExceeded) -> JSONResponse:
    # Disallowed backend -> 403; a daily cap that was hit -> 429.
    code = 403 if exc.status == QuotaExceeded.BACKEND_NOT_ALLOWED else 429
    return JSONResponse(status_code=code, content={"detail": str(exc)})


@app.exception_handler(FetchError)
async def _fetch_error_handler(_: Request, exc: FetchError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ConfigurationError)
async def _config_error_handler(_: Request, exc: ConfigurationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(SummarizationError)
async def _summarization_error_handler(
    _: Request, exc: SummarizationError
) -> JSONResponse:
    # The summary backend failed -- treat as an upstream/bad-gateway condition.
    return JSONResponse(status_code=502, content={"detail": str(exc)})


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


def _summarize_text(
    text: str,
    title: str,
    summarizer: str | None,
    model: str | None,
    output_format: OutputFormat = OutputFormat.PROSE,
) -> SummarizeResponse:
    """Step two: summarize text already fetched in a previous request."""
    result = Pipeline(_build_settings(summarizer, model)).summarize_text(
        text, title=title, output_format=output_format
    )
    return _to_response(result)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/api/fetch", response_model=FetchResponse)
def api_fetch(req: FetchRequest) -> FetchResponse:
    """JSON API: fetch and clean the article at ``url`` without summarizing."""
    return _fetch(str(req.url))


@app.get("/ollama/models")
def ollama_models() -> dict[str, object]:
    """List Ollama models pulled on the configured host, for the UI's picker.

    Polls the local Ollama server so the model dropdown stays in sync with
    whatever is actually installed. Returns an empty list (never an error) when
    Ollama is not running, letting the page fall back to manual model entry.
    No auth: this reports host-local infrastructure, not per-tenant data.
    """
    settings = get_settings()
    models = list_ollama_models(
        settings.ollama_host, timeout=min(settings.request_timeout, 5.0)
    )
    return {"models": models, "default": settings.ollama_model}


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
        # Never let the browser cache the app shell: a stale copy would keep
        # running an old model-picker script against fresh server state.
        headers={"Cache-Control": "no-store"},
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Render the empty web form."""
    return _render(request)


@app.get("/app", response_class=HTMLResponse)
def console(request: Request) -> HTMLResponse:
    """Render the authenticated browser console.

    A single page that drives the existing JSON API (register/login, summarize,
    archive, digests) from the browser. Auth rides on the signed session cookie
    set by ``/auth/register`` and ``/auth/login``, so the page just calls those
    endpoints with same-origin credentials -- no logic is duplicated here.
    """
    return _TEMPLATES.TemplateResponse(
        request,
        "console.html",
        {
            "backends": [s.value for s in SummarizerType],
            "output_formats": [f.value for f in OutputFormat],
            "ollama_model": get_settings().ollama_model,
        },
        headers={"Cache-Control": "no-store"},  # always serve the current shell
    )


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
            #
            # This unauthenticated local form may only use the free backends; the
            # paid backends are reachable solely through the authenticated
            # /api/summarize endpoint, which enforces tier and quota policy.
            settings = get_settings()
            quotas.assert_backend_allowed(
                settings.default_tier, summarizer or settings.summarizer.value
            )
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
