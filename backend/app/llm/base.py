"""LLM provider layer.

One interface, five backends:
  - OpenAI      (chat completions + Responses API with web_search tool)
  - Groq        (chat completions; no web search -> search proxy)
  - OpenCode    (opencode.ai/zen/v1; OpenAI-compatible; GPT/Grok models get
                 /responses web search, others use the search proxy)
  - Ollama      (local, OpenAI-compatible; no web search -> search proxy)
  - LM Studio   (local, OpenAI-compatible; no web search -> search proxy)

Web-search capability: only providers that can *search the live web* (OpenAI
Responses web_search, OpenCode GPT-family models) report
`supports_web_search=True`. Everything else falls back to a transparent
DuckDuckGo proxy that is clearly labelled as such in the report.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx


class LLMError(Exception):
    """Raised when a provider call fails after retries."""


# Some gateways (Cloudflare-fronted) block default HTTP client user-agents.
# A browser-like UA makes provider calls reliable.
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://opencode.ai",
}


@dataclass
class Citation:
    url: str
    title: str = ""


@dataclass
class SearchAnswer:
    text: str
    citations: list[Citation]
    searched_queries: list[str]


class BaseProvider:
    id: str = "base"
    display_name: str = "Base"
    supports_web_search: bool = False
    search_note: str = ""

    def is_configured(self) -> bool:
        raise NotImplementedError

    async def complete(self, messages: list[dict], *, json_mode: bool = False, temperature: float = 0.2) -> str:
        """Send a chat-completions style call; returns the assistant text."""
        raise NotImplementedError

    async def complete_with_search(self, messages: list[dict], *, search_context: str = "medium") -> SearchAnswer:
        """Like complete(), but the model may search the live web. Results carry citations."""
        raise NotImplementedError


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1]):
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict, headers: dict | None = None) -> dict:
    merged = {**_BROWSER_HEADERS, **(headers or {})}
    resp = await client.post(url, json=payload, headers=merged)
    if resp.status_code >= 400:
        detail = resp.text[:400]
        raise LLMError(f"{url} -> HTTP {resp.status_code}: {detail}")
    return resp.json()


class OpenAIProvider(BaseProvider):
    id = "openai"
    display_name = "OpenAI"
    supports_web_search = True
    search_note = "Live web search via OpenAI Responses API"

    def __init__(self, api_key: str, model: str, timeout: float = 120):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def complete(self, messages, *, json_mode=False, temperature=0.2) -> str:
        payload: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = await _post_json(
                client,
                "https://api.openai.com/v1/chat/completions",
                payload,
                {"Authorization": f"Bearer {self.api_key}"},
            )
        return data["choices"][0]["message"]["content"] or ""

    async def complete_with_search(self, messages, *, search_context="medium", include_sources=True) -> SearchAnswer:
        # Responses API with the hosted web_search tool.
        input_items = [{"role": m["role"], "content": m["content"]} for m in messages]
        payload = {
            "model": self.model,
            "tools": [{"type": "web_search", "search_context_size": search_context}],
            "input": input_items,
        }
        if include_sources:
            payload["include"] = ["web_search_call.action.sources"]
        async with httpx.AsyncClient(timeout=self.timeout * 3) as client:
            data = await _post_json(
                client,
                "https://api.openai.com/v1/responses",
                payload,
                {"Authorization": f"Bearer {self.api_key}"},
            )
        return _parse_responses_output(data)


def _parse_responses_output(data: dict) -> SearchAnswer:
    text_parts: list[str] = []
    citations: dict[str, Citation] = {}
    queries: list[str] = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for block in item.get("content", []):
                if block.get("type") == "output_text":
                    text_parts.append(block.get("text", ""))
                    for ann in block.get("annotations", []):
                        if ann.get("type") == "url_citation" and ann.get("url"):
                            citations[ann["url"]] = Citation(ann["url"], ann.get("title", ""))
        elif item.get("type") == "web_search_call":
            action = item.get("action") or {}
            for q in action.get("queries", []):
                if q not in queries:
                    queries.append(q)
            for src in action.get("sources", []):
                url = src.get("url")
                if url:
                    citations[url] = Citation(url, src.get("title", ""))
    return SearchAnswer(text="\n\n".join(p for p in text_parts if p).strip(), citations=list(citations.values()), searched_queries=queries)


class OpenAIChatSearchError(Exception):
    """Placeholder: OpenAI chat completions have no search; never used directly."""


class GroqProvider(BaseProvider):
    id = "groq"
    display_name = "Groq"
    supports_web_search = False
    search_note = "No native web search on Groq; using labelled search proxy"

    def __init__(self, api_key: str, model: str, timeout: float = 120):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def complete(self, messages, *, json_mode=False, temperature=0.2) -> str:
        payload: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = await _post_json(
                client,
                "https://api.groq.com/openai/v1/chat/completions",
                payload,
                {"Authorization": f"Bearer {self.api_key}"},
            )
        return data["choices"][0]["message"]["content"] or ""


class OpenRouterProvider(BaseProvider):
    id = "openrouter"
    display_name = "OpenRouter"
    supports_web_search = False
    search_note = "No native web search on OpenRouter; using labelled search proxy"

    def __init__(self, api_key: str, model: str, timeout: float = 120):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def complete(self, messages, *, json_mode=False, temperature=0.2) -> str:
        payload: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = await _post_json(
                client,
                "https://openrouter.ai/api/v1/chat/completions",
                payload,
                {"Authorization": f"Bearer {self.api_key}", "HTTP-Referer": "https://geo-auditor.local", "X-Title": "GEO Auditor"},
            )
        return data["choices"][0]["message"]["content"] or ""


class OpenCodeProvider(BaseProvider):
    id = "opencode"
    display_name = "OpenCode"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 120, web_search: bool = True):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._web_search = web_search

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def supports_web_search(self) -> bool:  # type: ignore[override]
        # Only GPT/Grok-family models are served through the /responses endpoint.
        return self._web_search and bool(re.match(r"^(gpt|grok)", self.model))

    @property
    def search_note(self) -> str:
        if self.supports_web_search:
            return "Web search via OpenCode Responses endpoint"
        return "Selected OpenCode model has no web search; using labelled search proxy"

    async def complete(self, messages, *, json_mode=False, temperature=0.2) -> str:
        payload: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = await _post_json(
                client,
                f"{self.base_url}/chat/completions",
                payload,
                {"Authorization": f"Bearer {self.api_key}"},
            )
        return data["choices"][0]["message"]["content"] or ""

    async def complete_with_search(self, messages, *, search_context="medium") -> SearchAnswer:
        input_items = [{"role": m["role"], "content": m["content"]} for m in messages]
        payload = {
            "model": self.model,
            "tools": [{"type": "web_search", "search_context_size": search_context}],
            "input": input_items,
        }
        # NB: the opencode gateway rejects the `include` param, so sources are
        # read from the output annotations instead.
        async with httpx.AsyncClient(timeout=self.timeout * 3) as client:
            data = await _post_json(
                client,
                f"{self.base_url}/responses",
                payload,
                {"Authorization": f"Bearer {self.api_key}"},
            )
        return _parse_responses_output(data)


class LocalOpenAICompatibleProvider(BaseProvider):
    """Ollama & LM Studio: same wire format, different base URLs, no auth."""

    id = "local"
    display_name = "Local"
    supports_web_search = False
    search_note = "Local model has no web search; using labelled search proxy"

    def __init__(self, provider_id: str, display_name: str, base_url: str, model: str, timeout: float = 300, use_format_json: bool = False):
        self.id = provider_id
        self.display_name = display_name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.use_format_json = use_format_json  # Ollama uses "format":"json"

    def is_configured(self) -> bool:
        return True  # configured when reachable; reachability probed separately

    async def complete(self, messages, *, json_mode=False, temperature=0.2) -> str:
        payload: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if json_mode:
            if self.use_format_json:
                payload["format"] = "json"
            else:
                payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = await _post_json(client, f"{self.base_url}/chat/completions", payload)
        return data["choices"][0]["message"]["content"] or ""

    async def probe(self) -> bool:
        """True when the local server answers /models."""
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False


def make_providers(cfg) -> list[BaseProvider]:
    """Build all providers from settings. Local providers are included only when
    their server is reachable."""
    out: list[BaseProvider] = []
    if cfg.openai_api_key:
        out.append(OpenAIProvider(cfg.openai_api_key, cfg.openai_model, cfg.llm_timeout))
    if cfg.groq_api_key:
        out.append(GroqProvider(cfg.groq_api_key, cfg.groq_model, cfg.llm_timeout))
    if cfg.opencode_api_key:
        out.append(
            OpenCodeProvider(
                cfg.opencode_api_key, cfg.opencode_base_url, cfg.opencode_model, cfg.llm_timeout,
                web_search=cfg.web_search_enabled,
            )
        )
    if cfg.openrouter_api_key:
        out.append(OpenRouterProvider(cfg.openrouter_api_key, cfg.openrouter_model, cfg.llm_timeout))
    return out


def make_local_providers(cfg) -> list[BaseProvider]:
    """Probed local providers (async) - checked lazily by the registry."""
    return [
        LocalOpenAICompatibleProvider("ollama", "Ollama", cfg.ollama_base_url, cfg.ollama_model, use_format_json=True),
        LocalOpenAICompatibleProvider("lmstudio", "LM Studio", cfg.lmstudio_base_url, cfg.lmstudio_model),
    ]
