"""Audit pipeline orchestration.

Stages: crawl -> query planning -> presence probing -> content analysis ->
scoring -> report. Progress is recorded per stage so the UI can render a live
tracker. Jobs live in an in-memory store (no DB - explicitly not needed).
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field

from ..config import settings
from ..llm.base import LLMError
from ..llm.registry import Registry
from .analyzer import run_analysis
from .crawler import Crawler
from .report import build_report, to_markdown
from .scoring import score_report


@dataclass
class AuditJob:
    id: str
    url: str
    provider_id: str | None
    status: str = "queued"              # queued | running | done | failed
    progress: float = 0.0
    stage: str = ""
    stage_log: list[dict] = field(default_factory=list)
    result: dict | None = None
    markdown: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class JobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, AuditJob] = {}
        self._lock = asyncio.Lock()

    async def create(
        self, url: str, provider_id: str | None, max_pages: int | None, num_queries: int | None, web_search: bool | None
    ) -> AuditJob:
        job = AuditJob(id=uuid.uuid4().hex[:12], url=url, provider_id=provider_id)
        job.result = {
            "request": {
                "url": url, "provider_id": provider_id, "max_pages": max_pages,
                "num_queries": num_queries, "web_search": web_search,
            }
        }
        async with self._lock:
            self.jobs[job.id] = job
        return job

    async def get(self, job_id: str) -> AuditJob | None:
        async with self._lock:
            return self.jobs.get(job_id)

    async def update(self, job_id: str, **kwargs) -> None:
        async with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            for k, v in kwargs.items():
                setattr(job, k, v)
            job.updated_at = time.time()

    async def log(self, job_id: str, stage: str, message: str) -> None:
        async with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            job.stage = stage
            job.stage_log.append({"stage": stage, "message": message, "at": time.strftime("%H:%M:%S")})


store = JobStore()


class AuditRunner:
    def __init__(self, registry: Registry, max_pages: int | None = None, num_queries: int | None = None, web_search: bool | None = None):
        self.registry = registry
        self.max_pages = max_pages or settings.max_pages
        self.num_queries = num_queries or settings.num_queries
        self.web_search = settings.web_search_enabled if web_search is None else web_search

    async def run(self, job_id: str) -> None:
        job = await store.get(job_id)
        if not job:
            return
        try:
            provider = await self.registry.get(job.provider_id)
            await store.update(job_id, status="running", progress=0.02)
            web_search = provider.supports_web_search and self.web_search
            provider_line = f"Using {provider.display_name} (model: {getattr(provider, 'model', 'n/a')}, web search: {web_search})"
            await store.log(job_id, "provider", provider_line)
            excluded: set[str] = set()
            try:
                await self._pipeline(job_id, provider, job.url)
            except LLMError as exc:
                # Graceful fallback: the provider failed; retry once with the
                # next available provider rather than killing the audit.
                excluded.add(provider.id)
                self.registry.mark_failed(provider.id)
                fallback = await self.registry.get(None, exclude=excluded)
                if fallback is not provider:
                    message = f"{provider.display_name} failed ({str(exc)[:120]}); retrying with {fallback.display_name}"
                    await store.log(job_id, "provider", message)
                    provider = fallback
                    await self._pipeline(job_id, provider, job.url)
                else:
                    raise
        except LookupError as exc:
            await store.update(job_id, status="failed", error=str(exc))
            await store.log(job_id, "error", f"Audit failed: {exc}")
        except Exception as exc:
            await store.update(job_id, status="failed", error=f"{exc.__class__.__name__}: {exc}")
            await store.log(job_id, "error", f"Audit failed: {exc.__class__.__name__}: {exc}")

    async def _pipeline(self, job_id: str, provider, url: str) -> None:
        import httpx
        async with httpx.AsyncClient(headers=settings.browser_headers) as client:
            crawler = Crawler(settings, client)
            await store.log(job_id, "crawl", f"Crawling {url} (robots, sitemap, up to {self.max_pages} pages)")
            crawl = await crawler.crawl(url, max_pages=self.max_pages)
            await store.update(job_id, progress=0.3)
            robots_state = "allowed" if crawl.robots.allowed else "BLOCKED"
            sitemap_state = "found" if crawl.sitemap_fetched else "missing"
            await store.log(job_id, "crawl", f"Crawled {len(crawl.all_pages)} page(s); robots={robots_state}; sitemap={sitemap_state}")

            await store.log(job_id, "plan", "Planning the questions customers would ask AI about this business")

            async def progress_cb(pct: float, message: str) -> None:
                await store.update(job_id, progress=min(pct, 0.95))
                await store.log(job_id, "presence", message)

            queries, presence_results, analysis = await run_analysis(
                provider, crawl, num_queries=self.num_queries, web_search_enabled=self.web_search,
                progress_cb=progress_cb, searxng_url=settings.searxng_url,
            )
            await store.update(job_id, progress=0.8)
            hits = sum(1 for p in presence_results if p.appeared)
            mode = "AI web search" if provider.supports_web_search and self.web_search else "search proxy"
            done_line = f"Presence probes done: {hits}/{len(presence_results)} queries surfaced the domain ({mode})"
            await store.log(job_id, "presence", done_line)

            await store.log(job_id, "score", "Scoring and prioritizing fixes")
            score = score_report(crawl, {"findings": analysis.findings}, presence_results, analysis.brand_knowledge)
            modes = sorted({p.mode for p in presence_results})
            if "ai_web_search" in modes:
                search_mode = "AI-answer probing (provider web search)"
            else:
                search_mode = f"labelled proxy ({', '.join(modes)})"
            report = build_report(
                crawl, analysis, queries, presence_results, score,
                provider.id, provider.display_name, getattr(provider, "search_note", ""), search_mode,
                job_id=job_id,
            )
            report["summary"] = analysis.summary
            markdown = to_markdown(report)
            await store.update(job_id, status="done", progress=1.0, result=report, markdown=markdown)
            await store.log(job_id, "done", f"Audit complete. Score: {score.overall}/100 ({score.grade})")
