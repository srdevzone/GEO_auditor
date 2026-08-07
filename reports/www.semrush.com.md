# GEO Audit Report — Semrush

**URL:** https://www.semrush.com/  
**Generated:** 2026-08-07T20:10 UTC  
**LLM provider:** OpenCode (opencode)  
**Search evidence mode:** AI-answer probing (provider web search)  
**Pages crawled:** 16


## Overall AI-visibility score: 79.0/100 — grade **B**

Good - visible in places, missing in others


## Score breakdown (how this number is calculated)

| Dimension | Weight | Score | Weighted | How it was measured |
|---|---:|---:|---:|---|
| AI presence | 35% | 100.0 | 35.0 | 7 of 7 queries surfaced the domain (ai_web_search) |
| Answerability | 30% | 30 | 9.0 | 7 finding(s), 70 points deducted. |
| Entity & foundation | 20% | 100.0 | 20.0 | No issues found in this dimension. |
| Authority & trust | 15% | 100.0 | 15.0 | No issues found in this dimension. |

_Weights: presence 35%, answerability 30%, entity 20%, authority 15%. Presence is measured live; other dimensions start at 100 and lose points per evidence-backed finding (critical=25, major=12, minor=5, info=1)._


## AI presence check (query by query)

| Query | Intent | Surfaced? | Mode | Evidence |
|---|---|---|---|---|
| What is AI visibility tracking and how does Semrush measure  | informational | YES | ai_web_search | Semrush measures it with its AI Visibility Toolkit, using prompt/response data to detect mentions and citations and combining topic coverage  (cites: https://www.semrush.com/kb/1607-semrush-ai-visibil |
| What is the best SEO and AI search platform for tracking bra | commercial | YES | ai_web_search | Semrush is the best all-in-one choice for SEO and AI search visibility.  (cites: https://www.semrush.com/features/brand-sentiment/, https://toolchase.com/blog/best-ai-seo-tools-2026/, https://aitoolru |
| How much does Semrush cost for SEO and AI search tracking? | pricing | YES | ai_web_search | Semrush’s SEO + AI Search plans start at $139/month monthly, or $117.33/month when billed annually.  (cites: https://www.semrush.com/pricing/seo-ai-search/) |
| How do I connect Semrush data to ChatGPT, Claude, or Perplex | how-to | YES | ai_web_search | Use Semrush’s official MCP integration.  (cites: https://developer.semrush.com/api/v3/introduction/semrush-mcp/, https://www.semrush.com/kb/1619-getting-started-with-mcp, https://help.openai.com/en/ar |
| Semrush vs other keyword research tools: which has the large | comparison | YES | ai_web_search | Ahrefs appears to have the largest currently published keyword database among major tools: 28.7 billion filtered keywords, versus Semrush’s   (cites: https://ahrefs.com/keywords-explorer, https://www. |
| How can I use the Semrush API to build custom SEO and compet | informational | YES | ai_web_search | Use Semrush’s API as a backend data layer: obtain an API key, choose the relevant API, and call report endpoints with parameters such as dat  (cites: https://developer.semrush.com/api/v3/get-started/a |
| What is Semrush? | branded | YES | ai_web_search | Semrush is a digital marketing and brand-visibility platform that helps businesses improve SEO, monitor AI-search visibility, research keywo  (cites: https://www.semrush.com/kb/995-what-is-semrush, ht |

## What's broken (with proof)


### Answerability

**[MAJOR] Turn the FAQ label into real question-and-answer blocks**  
*FAQPage is structured data that identifies question-and-answer content for search engines.*  
Page: https://www.semrush.com/features/keyword-research/  
Quote: “Learn how to do keyword research
FAQ
Keyword research is the process of finding the exact words and phrases people type into search engines.”  
Found: The page has an FAQ heading and one explanatory sentence, but the crawl detected 0 FAQ pairs.  
Should be: Add multiple visible questions with concise answers and FAQPage structured data.  

**[MINOR] Present plan information in a semantic comparison table**  
*Semantic HTML uses elements such as table, caption, th, and td to explain content structure to machines.*  
Page: https://www.semrush.com/pricing/  
Quote: “Plans & Pricing
Start with what you need. Add more as you grow.
- SEOFor freelancers and small businesses looking to grow their online visibility with SEO”  
Found: Pricing is presented as headings and bullet lists; the crawl detected no HTML tables.  
Should be: Use a real HTML table with one row per plan, consistent columns, prices, limits, and feature comparisons.  

**[MINOR] Separate homepage statistics into clean, quotable elements**  
*Quotable means an AI can copy a complete claim without reconstructing fragmented page text.*  
Page: https://www.semrush.com/  
Quote: “- 
          28BKeywords More keywords means more ways to win.
- 
          43TBacklinks Build credibility with the largest database on the market.”  
Found: The homepage contains numeric claims, but the crawl output concatenates values and labels such as “28BKeywords.”  
Should be: Render each statistic as a separate number, label, and supporting sentence in readable text.  

**[MAJOR] Add consistent Organization and WebSite structured data across key domains**  
*Structured data is machine-readable JSON-LD that tells search engines what an organization or page represents.*  
Page: https://www.semrush.com/  
Quote: “The leading platform to grow and measure brand visibility across every digital channel.”  
Found: The homepage has Corporation schema, while many sampled pages have no schema. The enterprise subdomain has Organization, WebSite, WebPage, and BreadcrumbList schema.  
Should be: Use consistent Organization, WebSite, WebPage, BreadcrumbList, and relevant Product or Service schema on the main site and important product pages.  

**[MAJOR] Publish an XML sitemap and reference it in robots.txt**  
*An XML sitemap is a machine-readable URL list that helps crawlers discover important pages.*  
Page: https://www.semrush.com/  
Quote: “Be found everywhere search happens”  
Found: Robots.txt allows crawling, but no sitemap was found in the crawl.  
Should be: Publish a current XML sitemap containing canonical, indexable URLs and reference it from robots.txt.  

**[MAJOR] Add methodology, dates, and source context to major data claims**  
*Methodology explains how a statistic was collected, calculated, and checked.*  
Page: https://www.semrush.com/features/market-analysis/  
Quote: “Semrush is built on real data from 200M+ panelists, giving you a real-time view into any market, competitor, or audience across 190+ countries.”  
Found: The page makes a substantial first-party data claim but the supplied content includes no publication date, author, methodology link, or external source citation.  
Should be: State when the data was collected or updated, explain the methodology, identify the responsible team or author, and link to supporting documentation.  

**[MAJOR] Reconcile conflicting database-size claims**  
*A primary source is the organization that owns and produces the underlying data.*  
Page: https://developer.semrush.com/api/  
Quote: “- 26.4Bkeywords
- 808Mdomain profiles
- 43Tbacklinks”  
Found: The API page states 26.4B keywords, while the homepage states 28B keywords and the keyword research page states “28 billion.”  
Should be: Use one current, dated definition for each metric, or explain why product and API counts differ.  


## What's working

- **Strong AI-oriented product positioning** — https://www.semrush.com/mcp/ — “Access Semrush's full dataset right from ChatGPT, Claude, Perplexity, Gemini, and more. Ask in natural language. Get clear, data-backed answers.”
- **Many pages contain concise, extractable claims and statistics** — https://www.semrush.com/one/ — “28M Trusted by 28M+ marketers worldwide”; “35% Chosen by 35% of the Fortune 500”; “21 Awarded best SEO software suite 21 times”.
- **Enterprise pages use comparatively strong entity markup** — https://enterprise.semrush.com/ — the crawl found “Organization,” “WebSite,” “WebPage,” and “BreadcrumbList” schema types.

## Fix list, in priority order (impact ÷ effort)

| # | Priority | Fix (copy-paste) | Impact | Effort |
|---|---|---|---|---|
| 1 | Plan next quarter | Add this visible HTML near the FAQ heading: <section aria-labelledby="faq-heading"><h2 id="faq-heading">Frequently asked questions</h2><h3>What is keyword research?</h3><p>Keyword research is the proc | 3 | 3 |
| 2 | Plan next quarter | Add a semantic table such as: <table><caption>Semrush plan comparison</caption><thead><tr><th>Plan</th><th>Monthly price</th><th>Websites</th><th>Daily keywords</th><th>AI visibility</th></tr></thead> | 3 | 3 |
| 3 | Plan next quarter | Replace concatenated stat markup with: <section aria-label="Semrush data statistics"><div><strong>28B</strong><span>keywords</span><p>More keywords means more ways to win.</p></div><div><strong>43T</s | 3 | 3 |
| 4 | Plan next quarter | Add this JSON-LD to the shared site template: <script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","@id":"https://www.semrush.com/#organization","name":"Semrush", | 3 | 3 |
| 5 | Plan next quarter | Create https://www.semrush.com/sitemap.xml with all canonical indexable URLs, then add this line to robots.txt: Sitemap: https://www.semrush.com/sitemap.xml. Submit the sitemap in Google Search Consol | 3 | 3 |
| 6 | Plan next quarter | Place this disclosure below the claim: <p><strong>Data methodology:</strong> This market analysis uses Semrush panel data from 200M+ panelists across 190+ countries. Data last updated: <time datetime= | 3 | 3 |
| 7 | Plan next quarter | Choose the authoritative current figure and update every page to the same wording, for example: <p>Our database contains <strong>28 billion keywords</strong> as of January 2026. API availability may v | 3 | 3 |

## Plain-language summary

Semrush has strong product clarity, substantial first-party statistics, and unusually direct integration with AI assistants. Its GEO visibility is held back by inconsistent structured data, absent sitemap discovery, weak FAQ extraction, fragmented statistics, and unsupported or conflicting data claims.
