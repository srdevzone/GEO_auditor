"""FastAPI application: audit API + provider status + markdown export."""
from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .audit.orchestrator import AuditRunner, store
from .config import settings
from .llm.registry import Registry

app = FastAPI(
    title="GEO Auditor API",
    version="1.0.0",
    description="AI-visibility auditor: score, evidence and prioritized fixes for any website.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = Registry(settings)


class AuditRequest(BaseModel):
    url: str = Field(..., min_length=3, description="Website URL to audit, e.g. https://example.com")
    provider: str | None = Field(None, description="LLM provider id (openai|groq|opencode|ollama|lmstudio). Omit for auto.")
    max_pages: int | None = Field(None, ge=1, le=40)
    num_queries: int | None = Field(None, ge=1, le=12)
    web_search: bool | None = Field(None, description="Set false to force the search proxy even when the provider supports web search.")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/providers")
async def providers() -> dict:
    statuses = await registry.statuses()
    return {"providers": [s.__dict__ for s in statuses], "default": next((s.id for s in statuses if s.configured), None)}


@app.post("/api/audit")
async def start_audit(req: AuditRequest) -> dict:
    job = await store.create(req.url, req.provider, req.max_pages, req.num_queries, req.web_search)
    runner = AuditRunner(registry, max_pages=req.max_pages, num_queries=req.num_queries, web_search=req.web_search)
    asyncio.create_task(runner.run(job.id))  # noqa: RUF006 - job state lives in the store; the task keeps itself alive
    return {"job_id": job.id, "status": job.status}


@app.get("/api/audit/{job_id}")
async def audit_status(job_id: str) -> dict:
    job = await store.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job id")
    return {
        "job_id": job.id,
        "url": job.url,
        "status": job.status,
        "progress": job.progress,
        "stage": job.stage,
        "stage_log": job.stage_log[-30:],
        "error": job.error,
        "result": job.result,
    }


@app.get("/api/audit/{job_id}/markdown")
async def audit_markdown(job_id: str) -> dict:
    job = await store.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job id")
    if job.status != "done" or not job.markdown:
        raise HTTPException(409, "Report not ready")
    return {"markdown": job.markdown}
