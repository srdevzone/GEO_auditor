# Documentation

- **[how-it-works.md](./how-it-works.md)** — the audit pipeline stage by stage: crawl,
  question planning, AI presence probing, content analysis, scoring, reporting.
- **[scoring.md](./scoring.md)** — how the 0–100 score is calculated: dimensions,
  weights, deduction table, a worked example, and fix prioritization (impact ÷ effort).
- **[providers.md](./providers.md)** — the six LLM providers (OpenAI, Groq, OpenCode,
  OpenRouter, Ollama, LM Studio), web-search capability, the three-tier presence
  fallback, and the gateway gotchas handled.
- **[architecture.md](./architecture.md)** — repository layout, API endpoints, data
  flow, and how to extend the tool (new provider / check / probe engine).
