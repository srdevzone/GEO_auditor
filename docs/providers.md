# LLM providers & the web-search story

The backend talks to six providers through one interface (`backend/app/llm/base.py`).
The user picks one in the UI (or "Auto"), and the audit runs every LLM call through that
provider. **No LLM calls are mocked** — any proxy or estimate is labelled.

## The interface

```python
class BaseProvider:
    id, display_name
    supports_web_search: bool
    async complete(messages, *, json_mode=False, temperature=0.2) -> str
    async complete_with_search(messages, *, search_context="medium") -> SearchAnswer
    # SearchAnswer = { text, citations: [Citation(url, title)], searched_queries }
```

- `complete` — plain chat completions (OpenAI-compatible wire format for all six).
- `complete_with_search` — the model may search the live web and returns citations.
  Only providers that genuinely support this report `supports_web_search=True`.

## The six providers

| id | Transport | Web search | How |
|---|---|---|---|
| `openai` | `api.openai.com` | ✅ | Responses API with the hosted `web_search` tool; citations read from `url_citation` annotations and `sources` |
| `opencode` | `opencode.ai/zen/v1` or `zen/go/v1` (from `.env`) | ✅ for GPT/Grok model ids | OpenAI-compatible `/chat/completions`, plus `/responses` with `web_search` when the model id starts with `gpt`/`grok` |
| `groq` | `api.groq.com/openai/v1` | ❌ | chat completions only |
| `openrouter` | `openrouter.ai/api/v1` | ❌ | chat completions only |
| `ollama` | `http://localhost:11434/v1` | ❌ | local, OpenAI-compatible; uses `"format": "json"` for JSON mode |
| `lmstudio` | `http://127.0.0.1:1234/v1` | ❌ | local, OpenAI-compatible |

### Credentials

- `OPENAI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` from `backend/.env`.
- **OpenCode keys are auto-discovered** from `~/.local/share/opencode/auth.json`
  (OpenCode Go / Zen), so if you already use the opencode CLI there is zero setup.
  Override with `OPENCODE_API_KEY`.
- Local providers count as configured only when their `/models` endpoint answers.

### Provider selection

`Registry` (in `app/llm/registry.py`) builds all configured providers and:

- `Auto` → picks in preference order: `opencode → openai → groq → openrouter → ollama → lmstudio`.
- Explicit pick → always attempted (the session blacklist only affects auto-selection,
  so you can retry a provider after topping up credits).
- A provider that raises during an audit is blacklisted for the session and the audit
  auto-falls-back to the next one (visible in the progress log).

## The web-search story, honestly

Search engines and model gateways are inconsistent from server IPs, so presence probing
is a three-tier ladder per query. The mode used is recorded **per query** in the report:

```
1. ai_web_search     provider searches live web → answer + citations (strongest)
        │  fails (wrong model, gateway quirk, rate limit)
        ▼
2. search_proxy      DuckDuckGo top results → domain match + LLM judge
        │  no results (bot-blocked)
        ▼
3. model_knowledge   model says, from training only, whether it would cite the brand
```

Failures are `error` (excluded from scoring), never counted as "you don't appear".

### Gotchas discovered and handled

- **OpenCode Go gateway rejects the `include` param** on `/responses`
  (`invalid_prompt`). The code omits it for OpenCode and reads citations from output
  annotations instead (OpenAI still gets `include` for full source lists).
- **Cloudflare blocks default HTTP client user-agents** — every provider request sends
  browser-style headers.
- **DDG rate-limits / bot-blocks** fast parallel queries — probes run sequentially with
  a 1s stagger, retry once on empty results, and an optional `GEO_SEARXNG_URL` instance
  can be used as a second engine before falling back to model-knowledge.

### Choosing a provider for best results

- **Most accurate presence:** any web-search-capable combo — `openai` (default model
  `gpt-5.6`), or `opencode` with a GPT/Grok model (e.g. `OPENCODE_MODEL=gpt-5.6-luna`).
- **Cheapest / local:** `opencode` with `deepseek-v4-flash`, `groq`, `ollama`, or
  `lmstudio` — these use the labelled search proxy for presence.
- Toggle with `GEO_WEB_SEARCH=0` to force proxy mode even for web-search providers.
