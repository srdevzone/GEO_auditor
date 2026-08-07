"""LLM-powered analysis: query planning, content findings, brand knowledge.

Every LLM call uses a strict JSON schema via prompt, then is parsed and
validated. Failures are returned as labelled errors, never silent fakes.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..llm.base import BaseProvider, LLMError, SearchAnswer, _parse_json
from ..prompts.prompts import (
    BRAND_KNOWLEDGE,
    CONTENT_ANALYSIS,
    PRESENCE_PROXY_JUDGE,
    PRESENCE_WEB_SEARCH,
    QUERY_PLANNER,
)
from .crawler import CrawlResult


@dataclass
class PlannedQuery:
    query: str
    intent: str = ""


@dataclass
class PresenceQueryResult:
    query: str
    intent: str = ""
    mode: str = ""            # "ai_web_search" | "search_proxy"
    appeared: bool | None = None
    answer_excerpt: str = ""
    mention_quote: str = ""
    cited_urls: list[str] = field(default_factory=list)
    top_results: list[dict] = field(default_factory=list)
    note: str = ""
    error: str = ""


@dataclass
class AnalysisResult:
    findings: list[dict] = field(default_factory=list)
    strengths: list[dict] = field(default_factory=list)
    summary: str = ""
    brand_knowledge: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _site_digest(crawl: CrawlResult, max_pages: int = 10) -> str:
    lines = [f"Brand/domain: {crawl.brand_from_title or crawl.brand} ({crawl.root_url})"]
    hp = crawl.homepage
    if hp:
        lines += [
            f"Homepage title: {hp.title}",
            f"Homepage meta: {hp.meta_description}",
            f"Homepage H1s: {'; '.join(hp.h1[:5])}",
        ]
    for page in crawl.all_pages[:max_pages]:
        lines.append(
            f"\n## {page.url}\n"
            f"Title: {page.title}\n"
            f"H1: {'; '.join(page.h1[:4])}\n"
            f"H2: {'; '.join(page.h2[:8])}\n"
            f"Stats found: {', '.join(page.stats_found[:8]) or 'none'}\n"
            f"FAQ pairs: {len(page.faq_pairs)}\n"
            f"Word count: {page.word_count}\n"
            f"Text: {page.text[:1800]}"
        )
    return "\n".join(lines)


def _content_digest(crawl: CrawlResult, max_pages: int = 12, page_chars: int = 1600) -> str:
    parts = []
    for page in crawl.all_pages[:max_pages]:
        parts.append(
            f"## {page.url}\n"
            f"Title: {page.title}\n"
            f"H1: {'; '.join(page.h1[:4])}\n"
            f"H2: {'; '.join(page.h2[:8])}\n"
            f"Stats: {', '.join(page.stats_found[:8]) or 'none'}\n"
            f"FAQ: {len(page.faq_pairs)} pairs | Tables: {page.table_count}\n"
            f"Schema types: {[s.get('@type') for s in page.json_ld if isinstance(s, dict)][:6]}\n"
            f"Text excerpt:\n{page.text[:page_chars]}"
        )
    return "\n\n".join(parts)


class Analyzer:
    def __init__(
        self, provider: BaseProvider, crawl: CrawlResult, *, num_queries: int = 7,
        web_search_enabled: bool = True, searxng_url: str = "",
    ):
        self.provider = provider
        self.crawl = crawl
        self.num_queries = num_queries
        self.web_search_enabled = web_search_enabled
        self.searxng_url = searxng_url

    async def plan_queries(self) -> list[PlannedQuery]:
        prompt = QUERY_PLANNER.replace("{site_digest}", _site_digest(self.crawl))
        data = await self._llm_json([{"role": "system", "content": "You output JSON only."}, {"role": "user", "content": prompt}])
        queries = []
        for q in (data or {}).get("queries", [])[: self.num_queries + 1]:
            queries.append(PlannedQuery(query=str(q.get("query", "")).strip(), intent=str(q.get("intent", ""))))
        queries = [q for q in queries if q.query]
        if not queries:
            queries = [PlannedQuery(self.crawl.brand, "branded")]
        return queries

    async def analyze_content(self) -> dict:
        robots = "allowed" if self.crawl.robots.allowed else f"disallowed paths: {self.crawl.robots.disallowed_paths}"
        prompt = CONTENT_ANALYSIS.format(
            domain=self.crawl.root_url,
            brand=self.crawl.brand_from_title or self.crawl.brand,
            robots=robots,
            sitemap=str(self.crawl.sitemap_fetched),
            homepage_title=self.crawl.homepage.title if self.crawl.homepage else "",
            homepage_meta=self.crawl.homepage.meta_description if self.crawl.homepage else "",
            n=min(len(self.crawl.all_pages), 12),
            total=len(self.crawl.all_pages),
            pages=_content_digest(self.crawl),
        )
        return await self._llm_json(
            [{"role": "system", "content": "You output JSON only."}, {"role": "user", "content": prompt}]
        )

    async def brand_knowledge(self) -> dict:
        brand = self.crawl.brand_from_title or self.crawl.brand
        prompt = BRAND_KNOWLEDGE.replace("{brand}", brand).replace("{domain}", self.crawl.root_url)
        try:
            return await self._llm_json([{"role": "user", "content": prompt}])
        except LLMError as exc:
            return {"known": False, "what_you_know": "", "error": str(exc)}

    async def probe_presence(self, query: PlannedQuery) -> PresenceQueryResult:
        """One query: does the domain show up in the AI answer (web search mode)
        or in the top search results (proxy mode)?"""
        domain = self.crawl.root_url
        brand = self.crawl.brand_from_title or self.crawl.brand
        result = PresenceQueryResult(query=query.query, intent=query.intent)

        if self.provider.supports_web_search and self.web_search_enabled:
            result.mode = "ai_web_search"
            try:
                prompt = PRESENCE_WEB_SEARCH.replace("{domain}", domain).replace("{brand}", brand).replace("{query}", query.query)
                answer: SearchAnswer = await self.provider.complete_with_search(
                    [{"role": "system", "content": "You output JSON only."}, {"role": "user", "content": prompt}]
                )
                data = _parse_json(answer.text) or {}
                result.answer_excerpt = str(data.get("answer_excerpt", ""))[:600]
                result.mention_quote = str(data.get("mention_quote", ""))[:400]
                result.cited_urls = [u for u in data.get("cited_urls", []) if isinstance(u, str)][:10]
                cited = [c.url for c in answer.citations] + result.cited_urls
                mentioned_in_text = bool(brand) and brand.lower() in result.answer_excerpt.lower()
                mentioned_in_text = mentioned_in_text and "no reliable" not in result.answer_excerpt.lower()
                appeared = bool(data.get("answer_mentions_site")) or self._domain_in_urls(domain, cited) or mentioned_in_text
                result.appeared = bool(appeared)
                if not appeared and data.get("why_site_missing"):
                    result.note = str(data["why_site_missing"])[:300]
                return result
            except LLMError as exc:
                result.error = f"Provider web search failed ({str(exc)[:160]}); fell back to search proxy."
                result.appeared = None
                # fall through to the proxy path below

        result.mode = "search_proxy"
        try:
            from ..llm.websearch import SearchError, duckduckgo_search, searxng_search
            top = await duckduckgo_search(query.query, max_results=8)
            if not top and self.searxng_url:
                top = await searxng_search(query.query, self.searxng_url, max_results=8)
            if not top:
                # Empty is almost always rate-limiting/bot-block, not evidence
                # of absence - retry once after a short pause.
                await asyncio.sleep(2.0)
                top = await duckduckgo_search(query.query, max_results=8)
                if not top and self.searxng_url:
                    top = await searxng_search(query.query, self.searxng_url, max_results=8)
        except SearchError as exc:
            result.error = str(exc)
            result.appeared = None
            return result
        if not top:
            return await self._model_knowledge_probe(query, result)
        result.top_results = [
            {"url": r.url, "title": r.title, "snippet": r.snippet, "position": r.position} for r in top
        ]
        result.appeared = bool(self._domain_in_urls(domain, [r.url for r in top]))
        judge_prompt = (
            PRESENCE_PROXY_JUDGE.replace("{query}", query.query)
            .replace("{brand}", brand)
            .replace("{domain}", domain)
        )
        lines = "\n".join(f"{r.position}. {r.title} - {r.url}\n   {r.snippet[:180]}" for r in top[:6])
        judge_prompt = judge_prompt.replace("{results}", lines)
        try:
            judgement = await self._llm_json(
                [{"role": "system", "content": "You output JSON only."}, {"role": "user", "content": judge_prompt}]
            )
            result.note = str(judgement.get("reason", ""))[:300]
        except LLMError:
            pass
        return result

    async def _model_knowledge_probe(self, query: PlannedQuery, result: PresenceQueryResult) -> PresenceQueryResult:
        """Fallback when no live search engine is reachable: ask the model
        (from training knowledge only) whether the brand is known and would be
        cited for this question. LABELLED as model knowledge - it is an
        estimate, never presented as live search data."""
        result.mode = "model_knowledge"
        prompt = (
            f"Without searching the web, from your training knowledge only: for the question "
            f"\"{query.query}\", would an AI assistant mention or cite the brand \"{self.crawl.brand_from_title or self.crawl.brand}\" "
            f"(domain {self.crawl.root_url})? Be honest - most brands are not known well enough to be cited.\n"
            f'Answer in JSON only: {{"would_cite": true|false, "reason": "one short sentence"}}'
        )
        try:
            judgement = await self._llm_json([{"role": "system", "content": "You output JSON only."}, {"role": "user", "content": prompt}])
            result.appeared = bool(judgement.get("would_cite"))
            result.note = str(judgement.get("reason", ""))[:300]
        except LLMError as exc:
            result.error = f"Model-knowledge probe failed: {str(exc)[:200]}"
            result.appeared = None
        return result

    @staticmethod
    def _domain_in_urls(domain: str, urls: list[str]) -> bool:
        from .crawler import registrable_domain
        target = registrable_domain(domain)
        return any(registrable_domain(u) == target for u in urls if u)

    async def _llm_json(self, messages: list[dict]) -> dict:
        last_err = ""
        for _ in range(2):
            try:
                text = await self.provider.complete(messages, json_mode=True, temperature=0.1)
            except LLMError as exc:
                last_err = str(exc)
                await asyncio.sleep(1.0)
                continue
            data = _parse_json(text)
            if data is not None:
                return data
            last_err = "Model returned non-JSON output"
            await asyncio.sleep(1.0)
            nudge = {
                "role": "user",
                "content": "Your previous reply was not valid JSON. Output ONLY the JSON object now, no markdown fences, no extra text.",
            }
            messages = [*messages, nudge]
        raise LLMError(f"JSON parse failed after retries: {last_err}")


async def run_analysis(
    provider: BaseProvider, crawl: CrawlResult, *, num_queries: int = 7, web_search_enabled: bool = True,
    progress_cb=None, searxng_url: str = "",
) -> tuple[list[PlannedQuery], list[PresenceQueryResult], AnalysisResult]:
    analyzer = Analyzer(
        provider, crawl, num_queries=num_queries, web_search_enabled=web_search_enabled, searxng_url=searxng_url
    )
    queries = await analyzer.plan_queries()
    if progress_cb:
        await progress_cb(0.38, "Questions planned — probing AI answers")
    results = []
    for i, q in enumerate(queries):
        results.append(await analyzer.probe_presence(q))
        if progress_cb:
            await progress_cb(0.38 + 0.30 * (i + 1) / max(len(queries), 1), f"Query {i + 1}/{len(queries)}: “{q.query[:50]}”")
        if not provider.supports_web_search:
            await asyncio.sleep(1.0)  # be polite to the free search proxy
    errors: list[str] = []
    try:
        content, brand = await asyncio.gather(analyzer.analyze_content(), analyzer.brand_knowledge())
    except LLMError as exc:
        content, brand = {}, {}
        errors.append(f"Content analysis failed: {str(exc)[:200]}")
    if progress_cb:
        await progress_cb(0.72, "Analyzing content for answerability, entity and trust")
    result = AnalysisResult(
        findings=content.get("findings", []),
        strengths=content.get("strengths", []),
        summary=content.get("summary", ""),
        brand_knowledge=brand,
        errors=errors,
    )
    return queries, list(results), result
