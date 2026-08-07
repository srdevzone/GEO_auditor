"""Provider registry: which providers are configured, and which one to use."""
from __future__ import annotations

from dataclasses import dataclass

from .base import BaseProvider, LocalOpenAICompatibleProvider, make_local_providers, make_providers

PREFERENCE_ORDER = ["opencode", "openai", "groq", "openrouter", "ollama", "lmstudio"]


@dataclass
class ProviderStatus:
    id: str
    name: str
    configured: bool
    supports_web_search: bool
    model: str
    note: str = ""


class Registry:
    def __init__(self, cfg, llm_timeout: float | None = None):
        self.cfg = cfg
        self.remote: dict[str, BaseProvider] = {p.id: p for p in make_providers(cfg)}
        self.local: dict[str, LocalOpenAICompatibleProvider] = {p.id: p for p in make_local_providers(cfg)}
        self._probe_cache: dict[str, bool] = {}
        self.failed: set[str] = set()  # providers that errored during this process; skipped in auto-selection

    def mark_failed(self, provider_id: str) -> None:
        self.failed.add(provider_id)

    async def _probe_local(self, provider: LocalOpenAICompatibleProvider) -> bool:
        if provider.id not in self._probe_cache:
            self._probe_cache[provider.id] = await provider.probe()
        return self._probe_cache[provider.id]

    async def statuses(self) -> list[ProviderStatus]:
        out = []
        for pid in PREFERENCE_ORDER:
            if pid in self.remote:
                p = self.remote[pid]
                out.append(ProviderStatus(p.id, p.display_name, True, p.supports_web_search, getattr(p, "model", ""), p.search_note))
            elif pid in self.local:
                p = self.local[pid]
                alive = await self._probe_local(p)
                note = p.search_note if alive else p.search_note + " (server not reachable)"
                out.append(ProviderStatus(p.id, p.display_name, alive, False, p.model, note))
        return out

    async def get(self, provider_id: str | None, exclude: set[str] | None = None) -> BaseProvider:
        """Resolve a provider by id; raise LookupError when missing/offline.

        The `failed` blacklist only affects AUTO-selection. An explicit
        provider_id is always attempted - the user may have fixed the key or
        topped up credits since the last failure.
        """
        exclude = exclude or set()
        if provider_id:
            if provider_id in exclude:
                raise LookupError(f"Provider '{provider_id}' was excluded (previous attempt failed)")
            if provider_id in self.remote:
                return self.remote[provider_id]
            if provider_id in self.local:
                p = self.local[provider_id]
                if await self._probe_local(p):
                    return p
                raise LookupError(f"Local provider '{provider_id}' is not reachable at {p.base_url}")
            raise LookupError(f"Unknown provider '{provider_id}'. Configure one in backend/.env (see .env.example).")
        for pid in PREFERENCE_ORDER:
            if pid in exclude or pid in self.failed:
                continue
            if pid in self.remote:
                return self.remote[pid]
            if pid in self.local:
                p = self.local[pid]
                if await self._probe_local(p):
                    return p
        raise LookupError(
            "No LLM provider configured. Set OPENCODE_API_KEY, OPENAI_API_KEY or GROQ_API_KEY in backend/.env, "
            "or start Ollama / LM Studio."
        )
