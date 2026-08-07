"""Web crawler: robots.txt, sitemap, and internal page discovery.

Uses httpx for transport and BeautifulSoup/trafilatura for parsing - no
hand-rolled HTML parsing. Handles messy sites: redirects, timeouts, non-HTML
files, huge pages, and JS-only (client-side rendered) pages.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import httpx
from bs4 import BeautifulSoup
from trafilatura import extract as trafilatura_extract

from ..config import Settings

SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".css", ".js",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".gz",
    ".mp3", ".mp4", ".webm", ".mov", ".avi", ".woff", ".woff2", ".ttf", ".eot",
    ".xml", ".json", ".txt", ".rss", ".atom", ".webmanifest",
}
SKIP_SUBSTR = {"/cdn-cgi/", "/wp-content/", "/wp-includes/", "/assets/", "/static/", "#", "mailto:", "tel:", "javascript:", "?"}
MAX_HTML_BYTES = 4 * 1024 * 1024


@dataclass
class RobotsInfo:
    fetched: bool = False
    url: str = ""
    allowed: bool = True
    disallowed_paths: list[str] = field(default_factory=list)
    sitemap_urls: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class Page:
    url: str
    status: int = 0
    title: str = ""
    meta_description: str = ""
    meta_robots: str = ""
    lang: str = ""
    canonical: str = ""
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    h3: list[str] = field(default_factory=list)
    text: str = ""                 # readable text (trafilatura), truncated
    full_text_chars: int = 0
    word_count: int = 0
    json_ld: list[dict] = field(default_factory=list)
    faq_pairs: list[dict] = field(default_factory=list)
    table_count: int = 0
    stats_found: list[str] = field(default_factory=list)
    pub_date: str = ""
    has_author: bool = False
    internal_links: list[str] = field(default_factory=list)
    csr_suspected: bool = False    # client-side rendered (little text in raw HTML)
    error: str = ""


@dataclass
class CrawlResult:
    root_url: str
    brand: str = ""
    brand_from_title: str = ""
    homepage: Page | None = None
    pages: list[Page] = field(default_factory=list)
    robots: RobotsInfo = field(default_factory=RobotsInfo)
    sitemap_urls: list[str] = field(default_factory=list)
    sitemap_fetched: bool = False
    crawl_errors: list[str] = field(default_factory=list)

    @property
    def all_pages(self) -> list[Page]:
        out = [self.homepage] if self.homepage else []
        return out + self.pages


STAT_RE = re.compile(
    r"(\d+(?:[.,]\d+)?%|\$\s?\d[\d.,]*[kmb]?\b|\d[\d.,]*\s+(?:million|billion|trillion|years|months|days|users|customers|employees|stars|reviews|times|%))\b",
    re.IGNORECASE,
)


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = "https://" + raw
    parsed = urllib.parse.urlsplit(raw)
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", "", ""))


def domain_of(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc.lower()


def registrable_domain(url: str) -> str:
    """The registrable domain (example.co.uk, shop.example.com -> example.com) using the Public Suffix List."""
    from publicsuffix2 import get_sld
    return get_sld(domain_of(url)) or domain_of(url)


def _clean_title(title: str, url: str) -> str:
    title = re.sub(r"\s*\|\s*$", "", title.strip())
    for sep in (" | ", " – ", " - ", " — ", ": "):
        if sep in title:
            return title.split(sep)[0].strip()
    return title


class Crawler:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    async def _get(self, url: str, *, binary_ok: bool = False) -> tuple[int, bytes | None, str | None]:
        try:
            resp = await self.client.get(url, timeout=self.settings.request_timeout, follow_redirects=True)
        except httpx.HTTPError as exc:
            return 0, None, f"Request failed: {exc.__class__.__name__}"
        if resp.status_code >= 400:
            return resp.status_code, None, f"HTTP {resp.status_code}"
        if not binary_ok:
            ctype = resp.headers.get("content-type", "")
            if not ctype.startswith(("text/html", "application/xhtml")) and "html" not in ctype:
                return resp.status_code, None, f"Not HTML ({ctype})"
        body = resp.content
        if len(body) > MAX_HTML_BYTES:
            body = body[:MAX_HTML_BYTES]
        return resp.status_code, body, None

    async def fetch_robots(self, root_url: str) -> RobotsInfo:
        parsed = urllib.parse.urlsplit(root_url)
        url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        info = RobotsInfo(url=url)
        status, body, err = await self._get(url)
        if err or not body:
            info.error = err or "no body"
            info.fetched = status is not None
            return info
        info.fetched = True
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        user_agent = None
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "user-agent":
                user_agent = value.lower()
            elif key == "disallow" and (user_agent in ("*", "geoauditor") or user_agent is None):
                if value:
                    info.disallowed_paths.append(value)
                    if value in ("/", "/*"):
                        info.allowed = False
            elif key == "sitemap":
                info.sitemap_urls.append(value)
        return info

    async def fetch_sitemap(self, sitemap_urls: list[str], root_url: str, depth: int = 0) -> list[str]:
        if depth > 2 or not sitemap_urls:
            return []
        urls: list[str] = []
        for url in sitemap_urls[:8]:
            _status, body, err = await self._get(url)
            if err or not body:
                continue
            soup = BeautifulSoup(body, "lxml")
            if soup.find("sitemapindex"):
                children = [el.get_text(strip=True) for el in soup.find_all("loc")]
                urls += await self.fetch_sitemap(children, root_url, depth + 1)
            elif soup.find("urlset") or soup.find("url"):
                for el in soup.find_all("loc"):
                    u = el.get_text(strip=True)
                    if u and registrable_domain(u) == registrable_domain(root_url):
                        urls.append(u)
        return urls

    async def crawl(self, raw_url: str, max_pages: int | None = None) -> CrawlResult:
        max_pages = max_pages or self.settings.max_pages
        root = normalize_url(raw_url)
        result = CrawlResult(root_url=root, brand=registrable_domain(root))
        result.robots = await self.fetch_robots(root)
        sitemap_urls = list(result.robots.sitemap_urls)
        if sitemap_urls:
            result.sitemap_urls = await self.fetch_sitemap(sitemap_urls, root)
            result.sitemap_fetched = True

        homepage = await self._fetch_page(root)
        if homepage.error:
            raise RuntimeError(f"Could not fetch {root}: {homepage.error}")
        result.homepage = homepage
        result.brand_from_title = _clean_title(homepage.title, root)

        # Discover internal pages: homepage links first, then sitemap.
        candidates: list[str] = []
        seen: set[str] = {root}
        for link in homepage.internal_links:
            if link not in seen:
                seen.add(link)
                candidates.append(link)
        for u in result.sitemap_urls:
            if u not in seen:
                seen.add(u)
                candidates.append(u)

        while candidates and len(result.pages) < max_pages:
            url = candidates.pop(0)
            page = await self._fetch_page(url)
            if page.error or page.status >= 400:
                result.crawl_errors.append(f"{url}: {page.error or page.status}")
                continue
            result.pages.append(page)
            for link in page.internal_links:
                if link not in seen and len(seen) < max_pages * 4:
                    seen.add(link)
                    candidates.append(link)
        return result

    async def _fetch_page(self, url: str) -> Page:
        page = Page(url=url)
        status, body, err = await self._get(url)
        page.status = status
        if err or not body:
            page.error = err or "empty body"
            return page
        try:
            html = body.decode("utf-8", errors="replace")
        except Exception:
            html = ""
        soup = BeautifulSoup(html, "lxml")

        page.title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:300]
        for tag in soup.find_all("meta"):
            if tag.get("name", "").lower() == "description":
                page.meta_description = (tag.get("content") or "")[:500]
            if tag.get("name", "").lower() == "robots":
                page.meta_robots = tag.get("content", "").lower()
            if tag.get("property", "").lower() in ("og:locale", "og:lang"):
                page.lang = tag.get("content", "").lower()
        if not page.lang:
            html_tag = soup.find("html")
            if html_tag and html_tag.get("lang"):
                page.lang = html_tag.get("lang").lower()

        link = soup.find("link", rel=lambda v: v and "canonical" in v) if soup.find else None
        if link and link.get("href"):
            page.canonical = link["href"]

        for level, attr in (("h1", page.h1), ("h2", page.h2), ("h3", page.h3)):
            for tag in soup.find_all(level)[:15]:
                txt = tag.get_text(" ", strip=True)
                if txt:
                    attr.append(txt[:200])

        for script in soup.find_all("script"):
            if script.get("type", "").strip() in ("application/ld+json", "application/json"):
                try:
                    import json as _json
                    data = _json.loads(script.string or "null")
                except Exception:
                    continue
                page.json_ld.append(data)
                if isinstance(data, dict) and data.get("@graph"):
                    page.json_ld.extend(data.get("@graph", []))

        for tag in soup.find_all(attrs={"itemtype": True}):
            if "FAQPage" in tag.get("itemtype", ""):
                page.faq_pairs.extend(self._extract_faq_soup(tag))
        if not page.faq_pairs:
            faq_schema = next((j for j in page.json_ld if isinstance(j, dict) and j.get("@type") == "FAQPage"), None)
            if faq_schema:
                page.faq_pairs = self._extract_faq_schema(faq_schema)

        page.table_count = len(soup.find_all("table"))
        page.pub_date = self._extract_date(soup, html)
        page.has_author = bool(re.search(r"author|byline|written by", html[:200000], re.IGNORECASE))

        raw_text = trafilatura_extract(html, include_comments=False, include_tables=True, favor_recall=True)
        if not raw_text:
            raw_text = soup.get_text(" ", strip=True)
        page.full_text_chars = len(raw_text)
        page.word_count = len(raw_text.split())
        page.text = raw_text[: self.settings.max_page_chars]
        page.csr_suspected = len(raw_text) < 200 and len(html) > 20000

        for match in STAT_RE.finditer(raw_text):
            s = match.group(0).strip()
            if s not in page.stats_found and len(page.stats_found) < 12:
                page.stats_found.append(s)

        page.internal_links = self._internal_links(soup, url)
        return page

    def _extract_faq_soup(self, tag: Any) -> list[dict]:
        pairs = []
        for block in tag.find_all(attrs={"itemtype": True}):
            if "Question" in block.get("itemtype", ""):
                q = block.find(attrs={"itemprop": "name"})
                a = block.find(attrs={"itemprop": "text"})
                if q and a:
                    pairs.append({"question": q.get_text(" ", strip=True), "answer": a.get_text(" ", strip=True)[:500]})
        return pairs

    def _extract_faq_schema(self, schema: dict) -> list[dict]:
        pairs = []
        for entry in schema.get("mainEntity", []):
            if isinstance(entry, dict) and entry.get("@type") == "Question":
                q = str(entry.get("name", ""))
                answer = entry.get("acceptedAnswer", {})
                a = str(answer.get("text", "")) if isinstance(answer, dict) else str(answer)
                if q and a:
                    pairs.append({"question": q, "answer": a[:500]})
        return pairs

    def _extract_date(self, soup: Any, html: str) -> str:
        for meta in soup.find_all("meta"):
            prop = (meta.get("property") or meta.get("itemprop") or "").lower()
            if prop in ("article:published_time", "datepublished", "datecreated") and meta.get("content"):
                return meta["content"][:10]
        for tag in soup.find_all("time"):
            if tag.get("datetime"):
                return tag["datetime"][:10]
        m = re.search(r"<time[^>]*datetime=\"(\d{4}-\d{2}-\d{2})", html)
        return m.group(1) if m else ""

    def _internal_links(self, soup: Any, base_url: str) -> list[str]:
        root_domain = registrable_domain(base_url)
        links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or any(s in href for s in SKIP_SUBSTR):
                continue
            try:
                joined = urllib.parse.urljoin(base_url, href)
            except ValueError:
                continue
            parsed = urllib.parse.urlsplit(joined)
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
                continue
            if parsed.scheme not in ("http", "https"):
                continue
            if registrable_domain(joined) != root_domain:
                continue
            cleaned = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path, "", ""))
            if cleaned != base_url and cleaned not in links:
                links.append(cleaned)
        return links[:60]
