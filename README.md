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

JSON API:

```bash
# fetch only
curl -X POST http://127.0.0.1:8000/api/fetch \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/article"}'

# fetch + summarize (model applies to the Ollama backend)
curl -X POST http://127.0.0.1:8000/api/summarize \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/article", "summarizer": "ollama", "model": "gemma4:e4b"}'
```

## Configuration

All settings are optional and read from environment variables or a `.env` file
(`AW_` prefix). Copy [`.env.example`](.env.example) to `.env` to customize.

| Variable | Default | Description |
| --- | --- | --- |
| `AW_SUMMARIZER` | `extractive` | `extractive` \| `ollama` \| `openai` \| `anthropic` |
| `AW_EXTRACTIVE_SENTENCES` | `5` | Sentences kept by the extractive summarizer |
| `AW_MAX_INPUT_CHARS` | `12000` | Max characters fed to the summarizer |
| `AW_OLLAMA_MODEL` | `llama3.2` | Local model name for Ollama |
| `AW_OPENAI_API_KEY` | – | Enables the OpenAI backend |
| `AW_ANTHROPIC_API_KEY` | – | Enables the Anthropic backend |

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
