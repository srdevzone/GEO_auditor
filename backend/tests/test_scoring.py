"""Unit tests for the deterministic parts of the GEO Auditor (no network, no LLM)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audit.crawler import normalize_url, registrable_domain
from app.audit.scoring import Finding, score_report
from app.llm.base import _parse_json
from app.llm.websearch import _decode_target


def make_finding(dim="answerability", severity="minor", quote="q"):
    return Finding(
        dimension=dim, severity=severity, title="t", fix="add FAQ JSON-LD",
        evidence={"page": "https://x.example/a", "quote": quote, "found": "f", "should_be": "s"},
        impact=3, effort=2,
    )


class DummyCrawl:
    brand = "example.com"
    root_url = "https://example.com"
    homepage = None
    pages = []
    sitemap_fetched = True
    crawl_errors = []
    robots = None
    all_pages = []

    class Robots:
        allowed = True
        disallowed_paths = []
        sitemap_urls = []


def test_severity_points_are_deterministic():
    crawl = DummyCrawl()
    score = score_report(crawl, {"findings": []}, [], {})
    # no findings -> full marks on the three finding-based dimensions
    by = {d.dimension: d for d in score.dimensions}
    assert by["answerability"].score == 100
    assert by["entity"].score == 100
    assert by["authority"].score == 100


def test_deductions_are_exact():
    crawl = DummyCrawl()
    findings = [
        make_finding("answerability", "critical"),   # -25
        make_finding("answerability", "major"),      # -12
        make_finding("entity", "major"),             # -12
    ]
    score = score_report(crawl, {"findings": [f.__dict__ | {"evidence": f.evidence} for f in findings]}, [], {})
    by = {d.dimension: d for d in score.dimensions}
    assert by["answerability"].score == 63
    assert by["entity"].score == 88
    assert by["authority"].score == 100


def test_overall_is_weighted_average():
    crawl = DummyCrawl()
    # presence measured 50%, others perfect -> 0.35*50 + 0.65*100 = 82.5
    class P:
        def __init__(self, appeared, mode="ai_web_search"):
            self.appeared = appeared
            self.mode = mode
            self.query = "q"
            self.intent = "i"
            self.answer_excerpt = ""
            self.mention_quote = ""
            self.cited_urls = []
            self.top_results = []
            self.note = ""
            self.error = ""

    score = score_report(crawl, {"findings": []}, [P(True), P(False)], {})
    assert score.overall == 82.5
    assert score.grade == "B"


def test_findings_without_evidence_are_dropped():
    crawl = DummyCrawl()
    bogus = make_finding(quote="").__dict__
    bogus["evidence"] = {}
    score = score_report(crawl, {"findings": [bogus]}, [], {})
    assert score.findings == []


def test_fix_priority_ordering_impact_over_effort():
    low = make_finding(quote="a")
    low.title = "low-impact-fix"
    low.impact, low.effort = 5, 4
    high = make_finding(quote="b")
    high.title = "high-impact-fix"
    high.impact, high.effort = 4, 1
    crawl = DummyCrawl()
    score = score_report(crawl, {"findings": [low.__dict__ | {"evidence": low.evidence}, high.__dict__ | {"evidence": high.evidence}]}, [], {})
    titles = [f.title for f in score.findings]
    assert titles == ["high-impact-fix", "low-impact-fix"]  # 4/1 = 4.0 before 5/4 = 1.25
    assert score.findings[0].priority_score == 4.0


def test_normalize_url():
    assert normalize_url("example.com") == "https://example.com/"
    assert normalize_url("http://Example.COM/Path") == "http://example.com/Path"
    assert registrable_domain("https://www.shop.example.co.uk/x") == "example.co.uk"


def test_parse_json_handles_fences_and_noise():
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json('here is the answer: {"a": 1} thanks!') == {"a": 1}
    assert _parse_json("no json here") is None


def test_ddg_url_unwrap():
    assert _decode_target("//duckduckgo.com/l/?uddg=https%3A%2F%2Fx.com%2Fa&rut=1") == "https://x.com/a"
    assert _decode_target("https://plain.example/x") == "https://plain.example/x"
