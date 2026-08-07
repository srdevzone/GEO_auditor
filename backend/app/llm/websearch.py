"""Search proxy used when the active LLM provider has no native web search.

DuckDuckGo HTML results are parsed and returned as structured results. This is a
*proxy* for AI-search visibility: AI engines source much of their training and
retrieval from the same index, so "is the domain in the top results for a
query" is a meaningful, real (not mocked) signal. The report always labels
results produced through this proxy.
"""
from __future__ import annotations

import random
import urllib.parse
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

UAS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    position: int


class SearchError(Exception):
    pass


def _decode_target(href: str) -> str:
    """DDG wraps result URLs in /l/?uddg=<urlencoded>; unwrap it."""
    if "/l/?" in href:
        parsed = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
        uddg = parsed.get("uddg", [None])[0]
        if uddg:
            return urllib.parse.unquote(uddg)
    return href


async def duckduckgo_search(query: str, max_results: int = 8, timeout: float = 15) -> list[SearchResult]:
    params = {"q": query, "kl": "us-en"}
    headers = {
        "User-Agent": random.choice(UAS),  # noqa: S311
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://duckduckgo.com/",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        try:
            resp = await client.get("https://html.duckduckgo.com/html/", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SearchError(f"DuckDuckGo request failed: {exc}") from exc
    if "No results" in resp.text or "anomaly" in resp.text or "challenge" in resp.text:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    results: list[SearchResult] = []
    for el in soup.select("div.result"):
        a = el.select_one("a.result__a")
        if not a:
            continue
        url = _decode_target(a.get("href", ""))
        title = a.get_text(" ", strip=True)
        snip_el = el.select_one("a.result__snippet")
        snippet = snip_el.get_text(" ", strip=True) if snip_el else ""
        results.append(SearchResult(url=url, title=title, snippet=snippet, position=len(results) + 1))
        if len(results) >= max_results:
            break
    return results


async def searxng_search(query: str, instance_url: str, max_results: int = 8, timeout: float = 20) -> list[SearchResult]:
    """SearXNG JSON API - works if the user points GEO_SEARXNG_URL at a tolerant
    public instance or their own self-hosted one."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": random.choice(UAS)}) as client:  # noqa: S311
        try:
            resp = await client.get(
                instance_url.rstrip("/") + "/search",
                params={"q": query, "format": "json", "language": "en"},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchError(f"SearXNG request failed: {exc}") from exc
    results = []
    for i, r in enumerate(data.get("results", [])[:max_results]):
        url = r.get("url", "")
        if not url:
            continue
        results.append(SearchResult(url=url, title=r.get("title", ""), snippet=r.get("content", ""), position=i + 1))
    return results
