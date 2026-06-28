# Artificial Writer

![Artificial Writer](artiwriter.png)

Fetch an article from a URL, extract the readable text, and summarize it — from a
**command line**, a **desktop GUI**, or a **web app**. Summarization is **pluggable**
and the default backend is **free and works fully offline** (no API key required).

> Originally a school project, rebuilt from the ground up as a clean, tested,
> multi-interface Python application.

---

## Highlights

- **Pluggable summarizers** behind one small interface — swap backends with a flag.
- **Free by default**: a built-in extractive summarizer runs offline with zero config.
- **Free local LLM** support via [Ollama](https://ollama.com) (no API key).
- **Optional cloud LLMs**: OpenAI and Anthropic (bring your own key).
- **Three front-ends** sharing one pipeline: CLI, Tkinter GUI, FastAPI web app.
- **Tested** with `pytest` (network mocked), **typed** (`mypy`), **linted** (`ruff`), **CI** on 3.10–3.13.
- **Clean architecture**: `src/` layout, typed config, domain errors, dependency injection.

## Architecture

```
URL ──▶ TextFetcher ──▶ clean text ──▶ Summarizer ──▶ summary ──▶ Storage
                                          ▲
                 extractive · ollama · openai · anthropic  (chosen by a factory)
```

The three front-ends are kept as separate, co-equal packages — `cli/`, `gui/`,
and `web/` — each a thin wrapper around the shared engine in
[`core/`](src/artificial_writer/core). A front-end depends on `core` and never
on another front-end, so behavior stays consistent and the interfaces stay small.

```
run_cli.py · run_gui.py · run_web.py   # top-level launchers for each front-end
src/artificial_writer/
├── core/                # the shared engine every front-end is built on
│   ├── config.py        #   typed settings from env / .env (pydantic-settings)
│   ├── fetcher.py       #   URL → cleaned article text
│   ├── pipeline.py      #   fetch → summarize → store orchestration
│   ├── storage.py       #   save/read results
│   ├── errors.py        #   domain error hierarchy
│   └── summarizers/     #   pluggable backends + factory
│       ├── base.py      #     Summarizer ABC + SummaryResult
│       ├── extractive.py#     free, offline (default)
│       ├── ollama.py    #     free, local LLM
│       ├── openai_provider.py
│       └── anthropic_provider.py
├── cli/                 # command-line front-end
├── gui/                 # Tkinter desktop front-end
└── web/                 # FastAPI app + HTML page
```

## Installation

```bash
git clone https://github.com/TymFly/artificial_writer.git
cd artificial_writer
```

Create and activate a virtual environment:

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

```powershell
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Then install:

```bash
pip install -e .                # core (CLI + GUI, free extractive summarizer)
pip install -e ".[web]"         # + web app
pip install -e ".[all,dev]"     # everything + dev tools (tests, lint, types)
```

## Usage

### CLI

```bash
artwriter https://en.wikipedia.org/wiki/Solar_power
artwriter https://example.com/article --sentences 3
artwriter https://example.com/article --summarizer ollama --save
artwriter https://example.com/article --json
```

(or `python -m artificial_writer <url>`, or `python run_cli.py <url>` from a
source checkout)

### Desktop GUI

```bash
artwriter-gui                        # installed console script
python -m artificial_writer.gui      # or: python run_gui.py
```

Enter a URL and click **Fetch** to pull and view the original article text, then
pick a backend and click **Summarize**.

### Web app

```bash
artwriter-web                        # installed console script (needs [web] extra)
python -m artificial_writer.web      # or: python run_web.py
```

(then open http://127.0.0.1:8000)

Enter a URL and click **Fetch** to view the original text, then choose a backend
(and a local **Model** name for Ollama) and click **Summarize**.

JSON API (single-user, no auth):

```bash
# fetch only — clean the article text without summarizing
curl -X POST http://127.0.0.1:8000/api/fetch \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/article"}'
```

> The HTML form and `/api/fetch` are unauthenticated and limited to the **free**
> backends. The authenticated, multi-tenant `/api/summarize` (with per-user
> archives, paid backends, quotas, batch jobs, and feeds) is described below.

## Multi-tenant web service

The same FastAPI app exposes an authenticated, multi-tenant API backed by
PostgreSQL (per-user archives + full-text search) and Redis (async batch jobs and
RSS feed polling). The bundled compose stack runs the whole thing:

```bash
cp .env.example .env                 # set AW_SESSION_SECRET (and any API keys)
docker compose -f infra/docker-compose.yml up --build
```

That starts five services — **postgres**, **redis**, **api** (on
http://127.0.0.1:8000), **worker** (RQ batch/feed jobs), and **scheduler**
(periodic feed polling). The `api` container runs `alembic upgrade head` on start
via [`infra/entrypoint.sh`](infra/entrypoint.sh), so the schema is always current.
Check it with `curl http://127.0.0.1:8000/health`.

**Register a user, then authenticate with either a cookie or an API key:**

```bash
# register (sets the aw_session cookie) and keep cookies in a jar
curl -c jar.txt -X POST http://127.0.0.1:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email": "me@example.com", "password": "password123"}'

# issue a long-lived API key (the full secret is shown exactly once)
curl -b jar.txt -X POST http://127.0.0.1:8000/auth/keys      # -> {"key": "aw_..."}

# summarize for that user (Bearer key OR the cookie jar authenticates)
curl -X POST http://127.0.0.1:8000/api/summarize \
     -H "Authorization: Bearer aw_..." -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/article", "output_format": "bullets"}'
```

Authenticated endpoints (all scoped to the calling user):

| Method & path | Purpose |
| --- | --- |
| `POST /auth/register` · `POST /auth/login` · `POST /auth/logout` | Session (cookie) auth |
| `POST /auth/keys` · `GET /auth/keys` · `DELETE /auth/keys/{id}` | Issue / list / revoke API keys |
| `POST /api/summarize` | Fetch + summarize one URL, stored to the user's archive |
| `GET /api/archive?q=` | Full-text search the user's stored summaries |
| `POST /api/batch` · `GET /api/batch/{job_id}` | Summarize many URLs into one digest (async) |
| `POST /api/feeds` · `GET /api/feeds` · `DELETE /api/feeds/{id}` | Manage polled RSS feeds |
| `GET /api/digests` · `GET /api/digests/{id}` | View batch/feed digests (JSON or HTML) |

Tier policy gates the paid backends: a **free** tier may only use the offline/free
backends (a paid backend → `403`) and is bounded by a daily request cap
(over-cap → `429`); a **pro** tier unlocks OpenAI/Anthropic up to a daily request
and USD cost ceiling. See the `AW_*` tier vars in [`.env.example`](.env.example).

The offline CLI and desktop GUI are **unchanged** by all of this — they need none
of the `server` dependencies and never touch Postgres or Redis.

## Configuration

All settings are optional and read from environment variables or a `.env` file
(`AW_` prefix). Copy [`.env.example`](.env.example) to `.env` to customize.

| Variable | Default | Description |
| --- | --- | --- |
| `AW_SUMMARIZER` | `extractive` | `extractive` \| `ollama` \| `openai` \| `anthropic` |
| `AW_EXTRACTIVE_SENTENCES` | `5` | Sentences kept by the extractive summarizer |
| `AW_MAX_INPUT_CHARS` | `80000` | Global upper bound (characters) fed to the summarizer; cut back to the last full stop |
| `AW_OLLAMA_MAX_INPUT_TOKENS` | `8000` | Per-backend input cap for Ollama (estimated tokens, under the global cap) |
| `AW_OPENAI_MAX_INPUT_TOKENS` | `12000` | Per-backend input cap for OpenAI (estimated tokens, under the global cap) |
| `AW_ANTHROPIC_MAX_INPUT_TOKENS` | `24000` | Per-backend input cap for Anthropic (estimated tokens, under the global cap) |
| `AW_OLLAMA_MODEL` | `llama3.2` | Local model name for Ollama |
| `AW_OPENAI_API_KEY` | – | Enables the OpenAI backend |
| `AW_ANTHROPIC_API_KEY` | – | Enables the Anthropic backend |

The multi-tenant web service adds a few more (see [`.env.example`](.env.example)):

| Variable | Default | Description |
| --- | --- | --- |
| `AW_DATABASE_URL` | `postgresql+asyncpg://aw:aw@localhost:5432/aw` | Async Postgres URL (Alembic converts it to a sync driver) |
| `AW_REDIS_URL` | `redis://localhost:6379/0` | RQ broker + result store for batch jobs / feeds |
| `AW_SESSION_SECRET` | `change-me` | Signs the `aw_session` login cookie — change it in any deploy |
| `AW_DEFAULT_TIER` | `free` | Tier assigned to new users |
| `AW_FREE_BACKENDS` / `AW_PAID_BACKENDS` | `["extractive","ollama"]` / `["openai","anthropic"]` | Which backends each class of tier may use |
| `AW_TIER_DAILY_REQUEST_CAP` | `{"free": 20, "pro": 500}` | Per-tier daily request caps (429 over-cap) |
| `AW_TIER_DAILY_COST_CAP_USD` | `{"free": 0.0, "pro": 5.0}` | Per-tier daily USD cost caps (a `0` cap blocks paid backends, 403) |

### Using a free local LLM (Ollama)

```bash
# install Ollama from https://ollama.com, then:
ollama pull llama3.2
AW_SUMMARIZER=ollama artwriter https://example.com/article
```

## Development

```bash
pip install -e ".[all,dev]"
pytest            # run the test suite (network is mocked)
ruff check .      # lint
mypy              # type-check
```

## License

[MIT](LICENSE)
