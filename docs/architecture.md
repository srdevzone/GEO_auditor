# Architecture & extension points

## Repository layout

```
.
├── script.sh                  # dev/test/reset/audit commands (see below)
├── README.md                  # run guide + product decisions
├── reports/                   # three live sample audits (.json raw, .md export)
├── docs/                      # this documentation
│
├── backend/
│   ├── .env.example           # all optional provider keys + tunables
│   ├── pyproject.toml         # ruff config
│   ├── run.py                 # uvicorn dev entrypoint (reload)
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py            # FastAPI routes + CORS
│   │   ├── config.py          # Settings (env-driven) + opencode auth.json discovery
│   │   ├── llm/
│   │   │   ├── base.py        # BaseProvider interface + six providers + responses parsing
│   │   │   ├── registry.py    # provider detection, blacklist, auto-fallback
│   │   │   └── websearch.py   # DuckDuckGo + SearXNG proxies
│   │   ├── audit/
│   │   │   ├── orchestrator.py# JobStore + AuditRunner (the pipeline driver)
│   │   │   ├── crawler.py     # robots/sitemap/page crawl + extraction
│   │   │   ├── analyzer.py    # query planning, presence probing, content analysis
│   │   │   ├── scoring.py     # deterministic score + fix prioritization
│   │   │   └── report.py      # JSON report + Markdown export
│   │   └── prompts/
│   │       └── prompts.py     # all LLM prompt templates
│   └── tests/                 # 10 unit tests (no network/LLM)
│
└── frontend/
    ├── vite.config.js         # dev proxy /api → :8000
    └── src/
        ├── api.js             # fetch helpers
        ├── App.jsx            # view state machine (form → progress → report)
        ├── styles.css
        └── components/
            ├── AuditForm.jsx      # URL + provider picker
            ├── ProgressPanel.jsx  # polls GET /api/audit/{id}
            └── ReportView.jsx     # score gauge, breakdown, presence, findings, fixes
```

## API surface (`app/main.py`)

| Method & path | Purpose |
|---|---|
| `GET /api/health` | liveness |
| `GET /api/providers` | configured providers + web-search capability (drives the picker chips) |
| `POST /api/audit` | body: `{url, provider?, max_pages?, num_queries?, web_search?}` → `{job_id}`. Launches a background task |
| `GET /api/audit/{job_id}` | `{status, progress, stage, stage_log, result?, error?}` — polled by the frontend |
| `GET /api/audit/{job_id}/markdown` | the copy-pasteable Markdown report |

Jobs live in an in-memory `JobStore` (no database — the brief says skip it; reports are
exportable files). An audit runs as an `asyncio` task so the API stays responsive.

## Data flow through the pipeline

`POST /api/audit` → `AuditRunner.run()`:

1. resolve provider (`Registry.get`) — log it
2. `_pipeline()`:
   - `Crawler.crawl()` → `CrawlResult` (homepage + pages + robots + sitemap)
   - `run_analysis()` → planned queries, presence results, content analysis,
     brand knowledge (progress callbacks every step)
   - `score_report()` → deterministic scores + prioritized findings
   - `build_report()` + `to_markdown()` → `result` + `markdown` on the job
3. on `LLMError` → mark provider failed, retry once with next provider
4. job status → `done` / `failed` (with a surfaced error)

## How to extend it

### Add a new provider
1. Subclass `BaseProvider` in `app/llm/base.py` (implement `complete`, and
   `complete_with_search` only if it really searches the web).
2. Add credential fields to `Settings` in `app/config.py`.
3. Register it in `make_providers()` and add its id to `PREFERENCE_ORDER` in
   `registry.py`.
4. Add a block to `backend/.env.example`.

### Add a new check/dimension
1. Add a dimension to `DIMENSIONS`/`WEIGHTS` in `app/audit/scoring.py` and a
   `SEVERITY_POINTS` entry if needed.
2. Extend the analysis prompt in `app/prompts/prompts.py` and/or add deterministic
   signals in `crawler.py`'s `Page`.
3. Surface it in `report.py` (JSON + markdown) and `frontend/src/components/ReportView.jsx`.

### Add a new presence probe engine
Follow `duckduckgo_search` in `app/llm/websearch.py`: return `list[SearchResult]`, then
wire it into the fallback chain in `analyzer.py::probe_presence`.

## Config knobs (`backend/.env`)

| Env var | Default | Meaning |
|---|---|---|
| `OPENAI_MODEL` / `GROQ_MODEL` / `OPENCODE_MODEL` / `OPENROUTER_MODEL` / `OLLAMA_MODEL` / `LMSTUDIO_MODEL` | per provider | model id |
| `OPENCODE_BASE_URL` | `https://opencode.ai/zen/v1` | override to `zen/go/v1` etc. |
| `GEO_MAX_PAGES` | `15` | pages crawled per audit |
| `GEO_NUM_QUERIES` | `7` | presence-test questions |
| `GEO_WEB_SEARCH` | `1` | `0` forces the search proxy |
| `GEO_SEARXNG_URL` | empty | optional SearXNG instance for the proxy tier |
| `GEO_TIMEOUT` / `GEO_LLM_TIMEOUT` | `20` / `120` | request timeouts (seconds) |
| `GEO_DATA_DIR` | `data` | scratch dir (currently unused; reserved) |

## Script commands (`script.sh`)

| Command | What it does |
|---|---|
| `./script.sh setup` | create venv, pip install, npm install |
| `./script.sh dev` | start backend + frontend |
| `./script.sh backend` / `./script.sh frontend` | start one |
| `./script.sh stop` | stop both |
| `./script.sh test` | pytest (10 tests, offline) |
| `./script.sh lint` | ruff + eslint |
| `./script.sh audit <url> [provider]` | run an audit from the CLI → `reports/<domain>.md/.json` |
| `./script.sh reports` | regenerate the three sample reports |
| `./script.sh env-check` | show which providers are detected |
| `./script.sh reset` | stop servers, wipe venv/node_modules |
