"""Deterministic scoring: every point on the 0-100 scale must be traceable.

Dimensions and weights (chosen because they are the things that decide whether
an AI engine quotes a site - see README for the research behind each):

  presence     35%  - the site actually appears inside AI answers for the
                      queries customers ask (measured live, or via a labelled
                      search-engine proxy)
  answerability 30% - the site's content can be *lifted* into an answer:
                      quotable claims, stats, Q&A, tables, structure
  entity        20%  - AI engines can identify the site as a real entity:
                      structured data, naming consistency, crawlability
  authority     15%  - trust signals: dates, authorship, primary sources,
                      brand recognition

Deductions are deterministic per finding severity:
  critical 25, major 12, minor 5, info 1 (points off that dimension).
Presence is scored from the measured query hit-rate, not from findings.

The report exposes the full arithmetic (dimension score + each deduction) so
there is no magic number.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .analyzer import PresenceQueryResult
from .crawler import CrawlResult

DIMENSIONS = ["presence", "answerability", "entity", "authority"]
WEIGHTS = {"presence": 0.35, "answerability": 0.30, "entity": 0.20, "authority": 0.15}
SEVERITY_POINTS = {"critical": 25, "major": 12, "minor": 5, "info": 1}
GRADES = [
    (85, "A", "Strong AI visibility - you are showing up in AI answers"),
    (70, "B", "Good - visible in places, missing in others"),
    (55, "C", "Mediocre - AI engines can find you but rarely quote you"),
    (40, "D", "Weak - you are mostly invisible inside AI answers"),
    (0, "F", "Invisible - AI engines cannot find or quote this site"),
]


@dataclass
class DimensionScore:
    dimension: str
    label: str
    weight: float
    score: float = 0.0
    weighted: float = 0.0
    deductions: list[dict] = field(default_factory=list)  # {title, points, severity, finding_title}
    measured: str = ""          # human-readable description of how the score was derived
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class Finding:
    dimension: str
    severity: str
    title: str
    evidence: dict
    impact: int
    effort: int
    fix: str
    jargon: str = ""

    @property
    def priority_score(self) -> float:
        return round(self.impact / max(self.effort, 1), 2)

    @property
    def bucket(self) -> str:
        if self.impact >= 4 and self.effort <= 2:
            return "Do this week"
        if self.priority_score >= 1.5:
            return "Do this month"
        return "Plan next quarter"


@dataclass
class ScoreResult:
    overall: float
    grade: str
    grade_blurb: str
    dimensions: list[DimensionScore]
    findings: list[Finding]
    presence: list[PresenceQueryResult]
    weight_table: list[dict]


def _validate_finding(raw: dict, dimension: str) -> Finding | None:
    severity = str(raw.get("severity", "minor")).lower()
    if severity not in SEVERITY_POINTS:
        severity = "minor"
    evidence = raw.get("evidence") or {}
    if not isinstance(evidence, dict):
        evidence = {}
    # tolerate models that put evidence fields at the top level
    for k in ("quote", "found", "should_be", "page"):
        if not evidence.get(k) and raw.get(k):
            evidence[k] = raw[k]
    try:
        impact = max(1, min(5, int(raw.get("impact", 3))))
        effort = max(1, min(5, int(raw.get("effort", 3))))
    except (TypeError, ValueError):
        impact, effort = 3, 3
    return Finding(
        dimension=dimension,
        severity=severity,
        title=str(raw.get("title", "Untitled finding")),
        evidence={
            "page": str(evidence.get("page", "")),
            "quote": str(evidence.get("quote", "")),
            "found": str(evidence.get("found", "")),
            "should_be": str(evidence.get("should_be", "")),
        },
        impact=impact,
        effort=effort,
        fix=str(raw.get("fix", "")),
        jargon=str(raw.get("jargon", "")),
    )


def score_report(crawl: CrawlResult, analysis: dict, presence_results: list[PresenceQueryResult], brand_knowledge: dict) -> ScoreResult:
    # ---- collect & validate findings -------------------------------------
    findings: list[Finding] = []
    for raw in analysis.get("findings", []):
        if not isinstance(raw, dict):
            continue
        dim = str(raw.get("dimension", "answerability")).lower()
        if dim not in DIMENSIONS:
            dim = "answerability"
        f = _validate_finding(raw, dim)
        if f and (f.evidence["quote"] or f.evidence["found"] or f.evidence["should_be"]):
            findings.append(f)

    # ---- presence dimension (measured, not LLM-scored) --------------------
    pres_dims: list[DimensionScore] = []
    valid = [p for p in presence_results if p.appeared is not None]
    errored = [p for p in presence_results if p.appeared is None]
    dim = DimensionScore("presence", "AI presence", WEIGHTS["presence"])
    if not valid and not presence_results:
        dim.skipped = True
        dim.skip_reason = "No queries were tested."
    elif not valid:
        dim.skipped = True
        dim.skip_reason = f"All {len(presence_results)} presence probes failed ({errored[0].error if errored else 'unknown error'})."
    else:
        hits = sum(1 for p in valid if p.appeared)
        dim.score = round(100 * hits / len(valid), 1)
        modes = sorted({p.mode for p in valid})
        dim.measured = f"{hits} of {len(valid)} queries surfaced the domain ({', '.join(modes)})"
        for p in valid:
            label = "surfaced" if p.appeared else "missing"
            dim.deductions.append({"title": f"{label} in AI answer", "query": p.query, "points": 0, "appeared": p.appeared})
    pres_dims.append(dim)

    # ---- other dimensions from findings ------------------------------------
    labels = {"answerability": "Answerability", "entity": "Entity & foundation", "authority": "Authority & trust"}
    rest: list[DimensionScore] = []
    for d in ("answerability", "entity", "authority"):
        s = DimensionScore(d, labels[d], WEIGHTS[d])
        d_findings = [f for f in findings if f.dimension == d]
        if not d_findings:
            s.score = 100.0
            s.measured = "No issues found in this dimension."
            rest.append(s)
            continue
        total = 0
        for f in d_findings:
            points = SEVERITY_POINTS[f.severity]
            total += points
            s.deductions.append({"title": f.title, "points": points, "severity": f.severity, "finding_title": f.title})
        s.score = max(0, round(100 - total, 1))
        s.measured = f"{len(d_findings)} finding(s), {total} points deducted."
        rest.append(s)

    dimensions = pres_dims + rest
    # ---- overall: weighted sum over non-skipped dimensions ------------------
    active = [d for d in dimensions if not d.skipped]
    for d in active:
        d.weighted = round(d.score * d.weight, 1)
    weight_total = sum(d.weight for d in active) or 1.0
    overall = round(sum(d.weighted for d in active) / weight_total, 1) if active else 0.0
    grade, blurb = next((g, b) for threshold, g, b in GRADES if overall >= threshold)

    # ---- fix priority: impact x effort (impact / effort) ---------------------
    findings_sorted = sorted(findings, key=lambda f: (-f.priority_score, -f.impact))
    weight_table = [
        {"dimension": d.dimension, "label": d.label, "weight": d.weight, "score": d.score,
         "weighted": d.weighted, "skipped": d.skipped, "skip_reason": d.skip_reason}
        for d in dimensions
    ]
    return ScoreResult(overall, grade, blurb, dimensions, findings_sorted, presence_results, weight_table)
