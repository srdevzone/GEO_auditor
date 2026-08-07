# How the GEO Auditor works

This document walks through what happens between the moment a user submits a URL and
the moment a report appears. The whole pipeline lives in `backend/app/audit/` and is
orchestrated by `orchestrator.py`.

## High-level flow

```
User enters https://yourbusiness.com
        │
        ▼
┌─────────────────────┐   ┌──────────────────────┐   ┌─────────────────────┐
│  1. CRAWL           │   │  2. PLAN QUESTIONS   │   │  3. PROBE AI ANSWERS│
│  robots.txt,        │   │  LLM reads the site  │   │  For each question: │
│  sitemap, up to N   │──▶│  and writes the 6-7  │──▶│  does your domain   │
│  pages (raw text,   │   │  questions customers │   │  appear in the AI   │
│  headings, schema,  │   │  ask AI about it     │   │  answer / results?  │
│  stats, dates)      │   │                      │   │                     │
└─────────────────────┘   └──────────────────────┘   └─────────────────────┘
        │                                                      │
        ▼                                                      ▼
┌─────────────────────┐   ┌──────────────────────┐   ┌─────────────────────┐
│  4. ANALYZE CONTENT │   │  5. SCORE            │   │  6. REPORT          │
│  LLM judges the site│──▶│  deterministic 0-100 │──▶│  findings + fixes + │
│  for answerability, │   │  with full math shown│   │  markdown export    │
│  entity, authority  │   │                      │   │                     │
└─────────────────────┘   └──────────────────────┘   └─────────────────────┘
```

Each stage updates the job's `progress` and `stage_log`, which the frontend polls
every ~1.5s and renders as a live tracker.

## Stage 1 — Crawl (`crawler.py`)

Transport is `httpx` with browser-like headers. Parsing uses `BeautifulSoup` (structure)
and `trafilatura` (readable text) — nothing is hand-rolled.

1. **robots.txt** is fetched first. We record whether the site blocks crawlers and
   collect any sitemap URLs listed there.
2. **sitemap.xml** is fetched (sitemap-index files are resolved recursively, one level
   deep). Valid URLs become crawl candidates.
3. **Homepage** is fetched and parsed into a `Page`:
   - title, meta description, meta robots, canonical, language
   - H1/H2/H3 headings
   - readable text (word count, truncated to `GEO_MAX_PAGE_CHARS` for the LLM)
   - JSON-LD structured data blocks (`@graph` expanded)
   - FAQ pairs (from `FAQPage` schema or microdata)
   - table count, statistics found (regex for %, $, counts), publication date, authorship
   - `csr_suspected`: if the raw HTML is large but renders almost no text, the page is
     probably client-side-rendered (JS) — flagged, because AI crawlers may not see it.
4. **Internal pages** are discovered breadth-first from the homepage links and sitemap,
   deduplicated, capped at `max_pages`. Non-HTML files, external domains, and obvious
   asset paths are skipped. Pages that 404 or time out are recorded in `crawl_errors`
   and don't fail the audit.

Domain comparison uses the **Public Suffix List** (`publicsuffix2`), so
`shop.example.co.uk` and `www.example.co.uk` are correctly treated as one site.

## Stage 2 — Plan the questions (`analyzer.py::plan_queries`)

The LLM receives a digest of the site (homepage title/meta/H1s, per-page H2s, topics,
stats) and is prompted to write **the 6–7 questions a real customer would type into an AI
assistant** where this business *should* appear — one per intent (commercial, comparison,
pricing, how-to, informational) plus one branded question. The queries come from the
site's actual structure, so they reflect what the business does, not generic topics.

Output is strict JSON (`{"queries": [{"query", "intent"}]}`). If the model fails, a
retry with a "return ONLY JSON" nudge runs once.

## Stage 3 — Probe AI presence (`analyzer.py::probe_presence`)

For each question, one of three measurement modes runs (recorded per query in the report):

1. **`ai_web_search`** — the active provider supports web search. The model is asked to
   search and answer the question *the way ChatGPT would*, with citations, then to state
   whether the audited domain appears in its answer. We also independently check the
   returned citations (`url_citation` annotations) for the domain. This is the strongest
   evidence: it's a live AI answer.
2. **`search_proxy`** — the provider has no web search. DuckDuckGo's top results for the
   question are fetched (real search data), we check whether the domain appears, and a
   second LLM call judges "would an AI assistant cite this brand given these results?".
   Clearly labelled in the report as a proxy.
3. **`model_knowledge`** — only when no search engine is reachable (bot-blocked). The
   model honestly reports, from training knowledge only, whether it would cite the brand.
   Labelled as an estimate.

**Failures never lie.** A rate-limited or blocked search is marked `error` and excluded
from scoring — it is never counted as "you don't appear".

## Stage 4 — Analyze content (`analyzer.py::analyze_content`)

The LLM gets a digest of up to 12 pages (title, headings, stats, FAQ counts, schema
types, and a text excerpt per page) plus crawl metadata (robots, sitemap) and judges
three dimensions:

- **answerability** — can AI engines lift crisp answers out: statistics, Q&A/FAQ blocks,
  tables, clear headings, quotable 1–3 sentence claims, thin pages.
- **entity** — does the site establish what it is: JSON-LD, consistent naming, about/
  contact pages, crawlability, meta descriptions.
- **authority** — trust signals: publication dates, authorship, original statistics,
  external citations to credible sources.

Every finding must carry a **verbatim quote** from the crawled content (for absence
findings, a quote from where the thing *should* be), plus `found`, `should_be`, an
`impact` (1–5) and `effort` (1–5) rating, and a copy-pasteable `fix`. Findings without
evidence are dropped by the scorer.

A parallel `brand_knowledge` call asks the model (no search) what it knows about the
brand — labelled as model knowledge.

## Stage 5 — Score (`scoring.py`)

Fully deterministic — the LLM proposes findings, but the number is arithmetic. Details
in [scoring.md](./scoring.md).

## Stage 6 — Report (`report.py`)

Assembles the JSON report (score breakdown, presence table, findings, prioritized fixes,
strengths, crawl data) and renders a copy-pasteable **Markdown export**. The frontend
renders the JSON; the `.md` is what a user downloads.

## Resilience

- **Provider failure** → the provider is blacklisted for the session and the audit
  auto-falls-back to the next configured provider, logged transparently.
- **Web-search failure mid-audit** → falls through to the search proxy for that query.
- **LLM non-JSON output** → one retry with a JSON-only nudge; if analysis still fails,
  the audit completes with an empty-but-honest findings list and a note, never a crash.
- **Messy sites** → 403/404/timeouts/JS-only pages become notes or skipped pages, not errors.
