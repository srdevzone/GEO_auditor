"""Crawler unit tests against a local HTML fixture (no network)."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audit.crawler import Crawler
from app.config import Settings

FAUX = """<html lang="en">
<head>
  <title>Acme Plumbing | Best plumbers in Denver</title>
  <meta name="description" content="Acme Plumbing fixes leaks fast. 10,000 jobs done since 2010.">
  <meta property="og:locale" content="en_US">
  <link rel="canonical" href="https://acmeplumbing.com/">
</head>
<body>
  <h1>Acme Plumbing</h1>
  <h2>24/7 emergency repairs</h2>
  <h2>Pricing</h2>
  <p>We have fixed over <strong>10,000 leaks</strong> since 2010 with a 99% satisfaction rate.</p>
  <table><tr><td>a</td><td>b</td></tr></table>
  <script type="application/ld+json">{"@type": "Organization", "name": "Acme Plumbing"}</script>
  <time datetime="2024-03-01">March 1</time>
  <a href="/pricing">Pricing</a>
  <a href="/about-us">About</a>
  <a href="https://external.org/foo">external</a>
  <a href="/assets/img/logo.png">logo</a>
  <a href="/pricing?utm=1">pricing dup</a>
</body>
</html>"""

FAUX_ABOUT = """<html><head><title>About Acme</title></head>
<body><h1>About us</h1><p>We are Acme, Denver's plumbers since 2010.</p></body></html>"""


@pytest.fixture
def client():
    routes = {
        "https://acmeplumbing.com/": (200, FAUX),
        "https://acmeplumbing.com/pricing": (200, FAUX_ABOUT),
        "https://acmeplumbing.com/about-us": (200, FAUX_ABOUT),
        "https://acmeplumbing.com/robots.txt": (200, "User-agent: *\nAllow: /\nSitemap: https://acmeplumbing.com/sitemap.xml"),
        "https://acmeplumbing.com/sitemap.xml": (200, '<urlset><url><loc>https://acmeplumbing.com/about-us</loc></url></urlset>'),
        "https://acmeplumbing.com/404": (404, "nope"),
        "https://acmeplumbing.com/secret": (200, FAUX_ABOUT),
    }

    class FakeTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            url = str(request.url)
            if url.endswith("secret") and "/robots.txt" in str(request.url):
                pass
            status, body = routes.get(url, (200, FAUX_ABOUT))
            return httpx.Response(status, content=body, headers={"content-type": "text/html"})

    return httpx.AsyncClient(transport=FakeTransport())


@pytest.mark.asyncio
async def test_crawl_extracts_structure(client):
    crawler = Crawler(Settings(), client)
    result = await crawler.crawl("https://acmeplumbing.com", max_pages=3)
    hp = result.homepage
    assert hp.title.startswith("Acme Plumbing")
    assert "10,000" in hp.text or "10,000" in " ".join(hp.stats_found)
    assert len(hp.h1) == 1 and hp.h1[0] == "Acme Plumbing"
    assert len(hp.json_ld) == 1
    assert hp.table_count == 1
    assert hp.pub_date == "2024-03-01"
    assert len(result.pages) == 2  # pricing + about-us (404 and external skipped)


@pytest.mark.asyncio
async def test_robots_and_sitemap(client):
    crawler = Crawler(Settings(), client)
    result = await crawler.crawl("https://acmeplumbing.com", max_pages=3)
    assert result.robots.allowed is True
    assert "https://acmeplumbing.com/about-us" in result.sitemap_urls
    assert result.sitemap_fetched is True
