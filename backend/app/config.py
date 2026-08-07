"""App configuration: provider credentials & audit tunables.

Every provider is optional. A provider is "configured" when we can find a key
(or local server) for it. The registry picks the best available provider,
preferring the one the user explicitly selected.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

AUTH_FILE = Path(os.environ.get("OPENCODE_AUTH_FILE", "~/.local/share/opencode/auth.json")).expanduser()


def _opencode_key_from_auth() -> str | None:
    """Auto-discover the user's opencode key (OpenCode Go / Zen) from the CLI auth store."""
    try:
        if not AUTH_FILE.exists():
            return None
        data = json.loads(AUTH_FILE.read_text())
        for name in ("opencode-go", "opencode", "opencode-zen"):
            entry = data.get(name) or {}
            key = entry.get("key") or entry.get("apiKey")
            if key:
                return key
    except Exception:
        return None
    return None


def _openrouter_key_from_auth() -> str | None:
    """Auto-discover the user's OpenRouter key from the opencode CLI auth store."""
    try:
        if not AUTH_FILE.exists():
            return None
        data = json.loads(AUTH_FILE.read_text())
        entry = data.get("openrouter") or {}
        key = entry.get("key") or entry.get("apiKey")
        return key or None
    except Exception:
        return None


def _browser_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) GeoAuditor/1.0 (+ai visibility auditor)",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


@dataclass
class Settings:
    # ---- provider credentials -------------------------------------------------
    openai_api_key: str | None = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: os.environ.get("OPENAI_MODEL", "gpt-5.6"))

    groq_api_key: str | None = field(default_factory=lambda: os.environ.get("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"))

    opencode_api_key: str | None = field(default_factory=lambda: os.environ.get("OPENCODE_API_KEY") or _opencode_key_from_auth())
    opencode_base_url: str = field(default_factory=lambda: os.environ.get("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1"))
    opencode_model: str = field(default_factory=lambda: os.environ.get("OPENCODE_MODEL", "deepseek-v4-flash"))

    openrouter_api_key: str | None = field(default_factory=lambda: os.environ.get("OPENROUTER_API_KEY") or _openrouter_key_from_auth())
    openrouter_model: str = field(default_factory=lambda: os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash"))

    ollama_base_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    ollama_model: str = field(default_factory=lambda: os.environ.get("OLLAMA_MODEL", "llama3.1"))

    lmstudio_base_url: str = field(default_factory=lambda: os.environ.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"))
    lmstudio_model: str = field(default_factory=lambda: os.environ.get("LMSTUDIO_MODEL", ""))

    # ---- audit tunables -------------------------------------------------------
    max_pages: int = int(os.environ.get("GEO_MAX_PAGES", "15"))
    max_page_chars: int = int(os.environ.get("GEO_MAX_PAGE_CHARS", "8000"))
    num_queries: int = int(os.environ.get("GEO_NUM_QUERIES", "7"))
    request_timeout: float = float(os.environ.get("GEO_TIMEOUT", "20"))
    llm_timeout: float = float(os.environ.get("GEO_LLM_TIMEOUT", "120"))
    web_search_enabled: bool = os.environ.get("GEO_WEB_SEARCH", "1") != "0"
    searxng_url: str = os.environ.get("GEO_SEARXNG_URL", "")  # optional tolerant SearXNG instance, e.g. http://localhost:8888

    # cache dir for crawled artefacts (no DB needed; we keep jobs in memory)
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("GEO_DATA_DIR", "data")))

    @property
    def browser_headers(self) -> dict[str, str]:
        return _browser_headers()


settings = Settings()
