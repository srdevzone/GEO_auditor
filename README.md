# GEO Auditor — AI Visibility Score for Any Website

A user types in a website. 3–5 minutes later they get:

1. **A score out of 100** for how visible they are inside AI answers (ChatGPT, Perplexity, Gemini, Google AI Overviews) — with the full arithmetic shown, no magic numbers.
2. **What's broken, with proof** — each finding carries the exact page and a verbatim quote from the site, what exists today, and what it should be.
3. **A prioritized fix list** — ordered by impact ÷ effort, in plain language for a business owner, with **copy-pasteable solutions** (JSON-LD snippets, rewrites, exact steps).

Built for the Phaze AI take-home task. Stack: **FastAPI + React (Vite)**. Every AI call goes through one of five swappable LLM providers: **OpenAI, Groq, OpenCode (Zen/Go), Ollama, LM Studio** (OpenRouter also included as a bonus). Nothing is mocked — anything that is a proxy or estimate is labelled in the UI and in the report.

---

## Run it (under 5 minutes)

```bash
# 1. One-time setup (python venv + pip + npm)
./script.sh setup

# 2. Optional: add keys
cp backend/.env.example backend/.env   # fill in whatever you have

# 3. Start both servers
./script.sh dev
# → open http://localhost:5173

# 4. Verify providers are detected
./script.sh env-check
```

**Key discovery that makes this painless:** your OpenCode (OpenCode Go/Zen) and OpenRouter API keys are **auto-discovered from `~/.local/share/opencode/auth.json`** — no env vars needed if you already use the opencode CLI. Any of these also works:

| Provider   | Env vars                        | Web search |
|------------|---------------------------------|------------|
| OpenCode   | `OPENCODE_API_KEY` (auto-detected from auth.json) | ✅ GPT/Grok models via `/responses`; others use proxy |
| OpenAI     | `OPENAI_API_KEY`, `OPENAI_MODEL` | ✅ Responses API `web_search` |
| Groq       | `GROQ_API_KEY`, `GROQ_MODEL`     | ❌ → labelled search proxy |
| OpenRouter | `OPENROUTER_API_KEY` (auto-detected) | ❌ → labelled search proxy |
| Ollama     | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | ❌ → labelled search proxy |
| LM Studio  | `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL` | ❌ → labelled search proxy |

Other script commands:

```bash
./script.sh test           # pytest suite (10 tests, no network, no LLM)
./script.sh lint           # ruff (backend) + eslint (frontend)
./script.sh audit <url>    # CLI audit → writes reports/<domain>.md + .json
./script.sh reports        # regenerate the three sample reports in reports/
./script.sh env-check      # which providers are configured
./script.sh reset          # stop servers, wipe venv/node_modules
```

---

**Web search provider notes (learned the hard way):**
- OpenCode's Zen/Go gateway rejects the Responses API `include` parameter and sometimes
  Cloudflare-blocks default HTTP client user-agents — the code sends browser-style headers
  and drops `include` for OpenCode, reading citations from output annotations instead.
- If a provider's web-search tool fails at runtime (wrong model, gateway quirk), the probe
  **falls back to the search proxy automatically** instead of losing the measurement, and the
  per-query mode in the report shows exactly what happened.

## What I check, and why (the research)

The field is ~2 years old and nobody has agreed on a standard, so every check is my explicit thesis. The two rules from the brief: **go deep, not wide**, and **be able to defend everything**.

### Dimension 1 — AI presence (35% weight): *Are you actually IN the AI answer?*

This is the product. Almost every existing tool audits the *ingredients* (schema, robots, content) and guesses visibility; I try to **measure visibility directly**.

- The LLM reads the crawled site and plans the 6–7 questions a customer would actually type into an AI assistant (commercial, comparison, pricing, how-to, informational + 1 branded). Questions are generated from the *site's real structure* (H1s, H2s, topics) so they reflect what the business does.
- Each question is then asked to a **web-search-enabled model** (OpenAI Responses `web_search`, or OpenCode GPT-family models through `/responses`). It answers like ChatGPT would, then we check: **did your domain appear in the answer text or in its citations?** The report shows the query, the answer excerpt, and the cited URLs.
- **Why it matters:** BrightEdge's 2024 research found ~35%+ of brand queries surface an AI answer, and AI engines cite only a handful of sources per answer. If you're not in the top 3–5 sources for your own questions, you're invisible to the fastest-growing channel.

**No web search on your provider?** (Groq, Ollama, LM Studio, OpenRouter, non-GPT OpenCode models.) We use a **labelled search-engine proxy** with a three-tier fallback:
1. DuckDuckGo's top results for the same questions, checked for your domain (+ LLM judgement of whether AI engines would cite you).
2. A **SearXNG instance** if you point `GEO_SEARXNG_URL` at one (self-hosted or tolerant public instance) — great for running your own infra.
3. **Model-knowledge probes** when no search engine is reachable (e.g. bot-blocked): the model says, honestly, whether it knows the brand well enough to cite it for that question.

Every probe records which mode produced it (`search_proxy`, `model_knowledge`, or `ai_web_search`) and the report shows it per query. Failed probes are marked **error** and excluded from the score — a rate-limited search is never counted as "you don't appear". Proxy mode is clearly labelled in the UI and report — it's a real measurement, not a fake AI answer.

### Dimension 2 — Answerability (30%): *Can AI engines lift answers out of your site?*

AI engines don't read for pleasure; they extract short answers from sources. Research (Agarwal et al.'s Princeton "Generative Engine Optimization" paper; Amsive Digital's GEO studies) shows **citations, statistics, quotes and Q&A formatting measurably increase the chance of being cited**.

The LLM analyzes the crawled pages and reports, per finding: what's missing (e.g. "no statistics anywhere on the pricing page"), quoting the exact sentence where the stat *should* be. We check: statistics and data points, FAQ/Q&A blocks, tables, clear heading structure, quotable 1–3 sentence claims, thin pages, sentence-level extractability.

### Dimension 3 — Entity & foundation (20%): *Does the AI know who you are and can it read you?*

An AI engine can only cite a site it (a) can crawl and (b) can identify as a real entity. Checks: robots.txt blocking, `meta robots`, JS-only rendering (content invisible in raw HTML), missing sitemap, JSON-LD structured data (Organization, Product, Service, FAQPage…), consistent brand naming, about/contact pages, canonical/duplicate issues.

### Dimension 4 — Authority & trust (15%): *Why should the AI trust you as a source?*

AI engines prefer established, dated, authored sources (E-E-A-T proxies). Checks: publication dates, authorship/byline, original statistics vs. aggregation, external citations to credible sources, and a **brand-recognition probe**: we ask the model (without search, labelled as model knowledge) what it knows about the brand — a business that an LLM already knows exists is far more likely to be suggested.

### What I cut, and why

- **Backlink graphs (Ahrefs/Moz style)** — needs paid APIs, is a slow proxy for AI citation behaviour, and the LLM-knowledge probe already covers brand prominence. High effort, low marginal signal.
- **Core Web Vitals / page speed** — genuine research shows AI citation behaviour barely tracks it; real-world AI engines cite slow sites all the time (Wikipedia, government sites). Cut for impact.
- **Social media signals, video, multi-language** — niche, out of scope for a first cut.
- **Auth, database, billing** — the brief says skip. Jobs live in an in-memory store; reports are exportable files.

### Scoring model (fully deterministic — no LLM decides your number)

- Presence: **measured** hit-rate = fraction of test queries where the domain surfaced.
- Answerability / entity / authority: each starts at 100 and loses **fixed points per finding** (critical 25, major 12, minor 5, info 1). Severity is the LLM's, points are not — the report shows every deduction.
- Overall = weighted average (35/30/20/15) over non-skipped dimensions. Every dimension shows its measured score, weight, weighted contribution and deductions, plus the one-paragraph method — the score breakdown table in the UI and report *is* the answer to "how was this calculated".
- Fixes are ordered by **priority = impact ÷ effort** (both 1–5, proposed by the LLM, shown in the report), bucketed into *Do this week / Do this month / Plan next quarter*.

### What's real vs. what's labelled

| Thing | Status |
|---|---|
| Crawl, robots.txt, sitemap, page content, schema, dates | **Real**, live fetch |
| Presence probes (web-search models) | **Real** AI-answer probing with citations |
| Presence via Groq/Ollama/etc. | **Real search data**, labelled *search proxy* (not an AI answer) |
| Brand-knowledge probe | **Real** model recall, labelled *model knowledge* |
| LLM findings/fixes | **Real analysis**; every finding requires a verbatim quote or explicit absence evidence |
| Nothing is pre-fabricated; no sample reports masquerade as live runs | The three reports in `reports/` are live runs from this tool |

---

## Architecture

```
frontend/  React + Vite (no UI framework, ~300 lines of CSS)
backend/   FastAPI
  app/
    main.py               routes: POST /api/audit, GET /api/audit/{id}, markdown export, provider status
    config.py             env-based settings, opencode auth.json discovery
    llm/base.py           one interface, six providers (OpenAI/Groq/OpenCode/OpenRouter/Ollama/LM Studio)
    llm/registry.py       provider detection + failure blacklist + auto-fallback
    llm/websearch.py      DuckDuckGo + SearXNG proxy (labelled fallback)
    audit/crawler.py      robots + sitemap + BFS crawl (httpx + trafilatura + BeautifulSoup)
    audit/analyzer.py     query planning, presence probing, content analysis (JSON-schema prompts)
    audit/scoring.py      deterministic scoring + impact/effort prioritization
    audit/report.py       report assembly + copy-pasteable Markdown export
    prompts/prompts.py    the product: evidence-forcing prompt templates
  tests/                  10 unit tests (no network/LLM): scoring math, URL/PSL, crawler fixture, JSON parsing
script.sh                 setup / dev / backend / frontend / test / lint / audit / reports / env-check / reset
```

**Failure handling that matters:**
- A provider that errors (no credits, bad key) is **blacklisted for the session** and the audit **auto-falls back to the next configured provider**, logged transparently in the progress feed.
- A site that 404s, times out, is JS-only, or blocks robots produces findings/notes rather than a crash.
- LLM non-JSON output is parsed leniently (fenced/embedded JSON) and findings without evidence are dropped rather than padded.

---

## Sample reports

`reports/` contains three live runs (regenerate with `./script.sh reports`):

- `barackobama.com` — a content-thin but well-known brand
- `en.wikipedia.org/wiki/Generative_engine_optimization` — a niche page that ranks for its own topic
- `semrush.com` — a heavyweight SaaS marketing brand (openai.com was dropped because it blocks
  non-browser clients from datacenter IPs - a good example of a real-world crawl blocker the tool survives)

## Documentation

Deeper write-ups live in `docs/`:

- **[How it works](./docs/how-it-works.md)** — the six-stage pipeline, stage by stage
- **[Scoring model](./docs/scoring.md)** — dimensions, weights, deduction table, worked example, prioritization
- **[LLM providers](./docs/providers.md)** — the six providers, web-search capability, presence fallback ladder
- **[Architecture](./docs/architecture.md)** — layout, API, data flow, extension points

Each is a real, dated run against a real site — the JSON is the raw report the API returns; the `.md` is what a customer would download.

## What I'd build next (given another week)

1. **SSE push** instead of polling; job persistence to disk so reports survive restarts.
2. **Perplexity-style multi-query probes** with more AI engines (Gemini grounding, Perplexity Sonar) for the presence dimension.
3. **Before/after re-audit**: run, fix, re-run and show the score delta — the "moment of realization" product loop.
4. **Historical tracking** (score over time) and a weekly watchlist.
5. Citation-worthy-ness scoring of *individual pages* (which page is most likely to be quoted, and why).
6. A browser-rendered crawl (Playwright) to accurately handle heavy JS sites — the current raw-HTML detection is honest but conservative.
7. Provider-agnostic cost/credits dashboard (OpenCode Zen and OpenRouter both expose usage endpoints).

## Notes & honesty

- The opencode API keys on this machine were out of credits during development, so sample runs were executed via the auto-fallback to OpenRouter (`deepseek/deepseek-v4-flash`, the same model family as the opencode default). The fallback is visible in each report's provider metadata.
- DuckDuckGo HTML scraping is a free, no-key proxy that can occasionally rate-limit or bot-block; when that happens the probe falls through to SearXNG (if configured) or to a labelled model-knowledge estimate, and genuine failures are marked "error" in the report rather than counted as misses.
- LLM analysis is temperature 0.1 and evidence-forced, but it is still a language model: findings are quotes from *your site*, the reasoning is machine-judged. That's the nature of the tool; nothing is presented as crawled data unless it was.
