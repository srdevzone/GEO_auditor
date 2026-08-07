"""Report assembly: build the final JSON report + a copy-pasteable Markdown export.

Everything in the report is traceable to evidence collected during the audit:
crawl data, presence probe results, or LLM findings (each with a verbatim quote).
"""
from __future__ import annotations

from datetime import UTC, datetime

from .analyzer import AnalysisResult, PresenceQueryResult
from .crawler import CrawlResult
from .scoring import WEIGHTS, ScoreResult


def build_report(
    crawl: CrawlResult,
    analysis: AnalysisResult,
    queries: list,
    presence_results: list[PresenceQueryResult],
    score: ScoreResult,
    provider_id: str,
    provider_name: str,
    provider_note: str,
    search_mode: str,
    job_id: str = "",
) -> dict:
    report = {
        "meta": {
            "job_id": job_id,
            "url": crawl.root_url,
            "brand": crawl.brand_from_title or crawl.brand,
            "generated_at": datetime.now(UTC).isoformat(),
            "provider": {"id": provider_id, "name": provider_name, "note": provider_note},
            "search_mode": search_mode,
            "crawled_pages": [p.url for p in crawl.all_pages],
            "crawled_count": len(crawl.all_pages),
            "crawl_errors": crawl.crawl_errors[:20],
        },
        "score": {
            "overall": score.overall,
            "grade": score.grade,
            "grade_blurb": score.grade_blurb,
            "weight_table": score.weight_table,
            "weights": WEIGHTS,
            "dimensions": [
                {
                    "dimension": d.dimension,
                    "label": d.label,
                    "weight": d.weight,
                    "score": d.score,
                    "weighted": d.weighted,
                    "measured": d.measured,
                    "skipped": d.skipped,
                    "skip_reason": d.skip_reason,
                    "deductions": d.deductions,
                }
                for d in score.dimensions
            ],
            "how_calculated": (
                "Presence = measured query hit-rate. Other dimensions start at 100 and lose "
                "deterministic points per finding (critical=25, major=12, minor=5, info=1). "
                "Overall = weighted average of non-skipped dimensions (weights: presence 35%, "
                "answerability 30%, entity 20%, authority 15%)."
            ),
        },
        "presence": [
            {
                "query": p.query,
                "intent": p.intent,
                "mode": p.mode,
                "appeared": p.appeared,
                "answer_excerpt": p.answer_excerpt,
                "mention_quote": p.mention_quote,
                "cited_urls": p.cited_urls[:10],
                "top_results": p.top_results[:8],
                "note": p.note,
                "error": p.error,
            }
            for p in presence_results
        ],
        "summary": analysis.summary,
        "strengths": analysis.strengths,
        "brand_knowledge": analysis.brand_knowledge,
        "findings": [
            {
                "dimension": f.dimension,
                "severity": f.severity,
                "title": f.title,
                "evidence": f.evidence,
                "impact": f.impact,
                "effort": f.effort,
                "priority_score": f.priority_score,
                "bucket": f.bucket,
                "fix": f.fix,
                "jargon": f.jargon,
            }
            for f in score.findings
        ],
        "fixes": [
            {
                "rank": i + 1,
                "title": f.title,
                "fix": f.fix,
                "impact": f.impact,
                "effort": f.effort,
                "priority_score": f.priority_score,
                "bucket": f.bucket,
                "jargon": f.jargon,
                "dimension": f.dimension,
            }
            for i, f in enumerate(score.findings)
        ],
        "crawl": {
            "robots": {
                "allowed": crawl.robots.allowed,
                "disallowed_paths": crawl.robots.disallowed_paths,
                "sitemap_urls": crawl.robots.sitemap_urls,
                "error": crawl.robots.error,
            },
            "sitemap": {"found": crawl.sitemap_fetched, "url_count": len(crawl.sitemap_urls)},
            "pages": [
                {
                    "url": p.url,
                    "status": p.status,
                    "title": p.title,
                    "word_count": p.word_count,
                    "full_text_chars": p.full_text_chars,
                    "csr_suspected": p.csr_suspected,
                    "faq_pairs": len(p.faq_pairs),
                    "stats": p.stats_found[:10],
                    "tables": p.table_count,
                    "schema_types": [s.get("@type") for s in p.json_ld if isinstance(s, dict)][:8],
                    "pub_date": p.pub_date,
                    "has_author": p.has_author,
                    "meta_robots": p.meta_robots,
                    "h1": p.h1[:6],
                }
                for p in crawl.all_pages
            ],
        },
        "errors": analysis.errors,
    }
    return report


def to_markdown(report: dict) -> str:
    score = report["score"]
    m = []
    m.append(f"# GEO Audit Report — {report['meta']['brand']}")
    m.append(f"\n**URL:** {report['meta']['url']}  ")
    m.append(f"**Generated:** {report['meta']['generated_at'][:16]} UTC  ")
    m.append(f"**LLM provider:** {report['meta']['provider']['name']} ({report['meta']['provider']['id']})  ")
    m.append(f"**Search evidence mode:** {report['meta']['search_mode']}  ")
    m.append(f"**Pages crawled:** {report['meta']['crawled_count']}\n")

    m.append(f"\n## Overall AI-visibility score: {score['overall']}/100 — grade **{score['grade']}**")
    m.append(f"\n{score['grade_blurb']}\n")

    m.append("\n## Score breakdown (how this number is calculated)")
    m.append("\n| Dimension | Weight | Score | Weighted | How it was measured |")
    m.append("|---|---:|---:|---:|---|")
    for d in score["dimensions"]:
        d["skip_reason"] or "—"
        measured = d["skip_reason"] if d["skipped"] else d["measured"]
        m.append(f"| {d['label']} | {d['weight']:.0%} | {d['score']} | {d['weighted']} | {measured} |")
    m.append("\n_Weights: presence 35%, answerability 30%, entity 20%, authority 15%. Presence is measured live; "
             "other dimensions start at 100 and lose points per evidence-backed finding "
             "(critical=25, major=12, minor=5, info=1)._\n")

    m.append("\n## AI presence check (query by query)")
    m.append("\n| Query | Intent | Surfaced? | Mode | Evidence |")
    m.append("|---|---|---|---|---|")
    for p in report["presence"]:
        status = {True: "YES", False: "no", None: "error"}.get(p["appeared"], "?")
        if p["mention_quote"]:
            evidence = p["mention_quote"][:140]
        elif p["appeared"] and p["answer_excerpt"]:
            evidence = p["answer_excerpt"][:140]
        elif p["top_results"] and p["appeared"]:
            evidence = p["top_results"][0]["title"]
        else:
            evidence = p["answer_excerpt"][:140] or p["note"] or p["error"] or ""
        if p.get("cited_urls"):
            evidence = f"{evidence}  (cites: {', '.join(p['cited_urls'][:3])})"
        m.append(f"| {p['query'][:60]} | {p['intent']} | {status} | {p['mode']} | {evidence[:200]} |")

    m.append("\n## What's broken (with proof)\n")
    by_dim = {}
    for f in report["findings"]:
        by_dim.setdefault(f["dimension"], []).append(f)
    for dim in ("presence", "answerability", "entity", "authority"):
        if dim not in by_dim:
            continue
        m.append(f"\n### {dim.capitalize()}\n")
        for f in by_dim[dim]:
            sev = f["severity"].upper()
            m.append(f"**[{sev}] {f['title']}**  ")
            if f.get("jargon"):
                m.append(f"*{f['jargon']}*  ")
            if f["evidence"].get("page"):
                m.append(f"Page: {f['evidence']['page']}  ")
            if f["evidence"].get("quote"):
                m.append(f"Quote: “{f['evidence']['quote']}”  ")
            if f["evidence"].get("found"):
                m.append(f"Found: {f['evidence']['found']}  ")
            if f["evidence"].get("should_be"):
                m.append(f"Should be: {f['evidence']['should_be']}  ")
            m.append("")
    if report["strengths"]:
        m.append("\n## What's working\n")
        for s in report["strengths"]:
            m.append(f"- **{s.get('title', '')}** — {s.get('evidence', '')}")
    m.append("\n## Fix list, in priority order (impact ÷ effort)\n")
    m.append("| # | Priority | Fix (copy-paste) | Impact | Effort |")
    m.append("|---|---|---|---|---|")
    for fix in report["fixes"]:
        m.append(f"| {fix['rank']} | {fix['bucket']} | {fix['fix'][:200].replace(chr(10), ' ')} | {fix['impact']} | {fix['effort']} |")
    m.append("\n## Plain-language summary")
    m.append(f"\n{report['summary'] or 'No summary was generated.'}\n")
    return "\n".join(m)
