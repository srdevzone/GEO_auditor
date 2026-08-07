"""Prompt templates. Prompts are the product: they must force evidence-backed
answers, JSON output, and plain-English fixes.
"""

QUERY_PLANNER = """You are a GEO (Generative Engine Optimization) analyst. A user wants to know whether their website appears in AI search answers (ChatGPT, Perplexity, Google AI Overviews, Claude).

Here is the structure and content of the website being audited:

{site_digest}

Your job: design the set of real-world questions a potential customer would ask an AI assistant where this business SHOULD appear.

Rules:
- 7 questions total: 6 informational/commercial questions about the products/services/topics the site actually covers, plus 1 branded question (the company name alone, or name + what it does).
- Questions must be written as a customer would type them ("best x for y", "how much does x cost", "what is x").
- Vary the intent: comparison, pricing, how-to, definition, recommendation.
- Do NOT invent topics the site doesn't cover. If the site is thin, base questions on what little exists.

Return JSON only:
{{"queries": [{{"query": "...", "intent": "one of: commercial/comparison/pricing/informational/navigational/branded"}}]}}"""

PRESENCE_WEB_SEARCH = """You are auditing how visible a website is inside AI search answers.

Target website: {domain} ({brand})
Question to test: "{query}"

Do this:
1. Perform a web search for this question.
2. Write the answer to the question exactly the way ChatGPT or a similar AI assistant would answer it - short, sourced, plain.
3. Then assess: does the target website/domain appear in your answer, either mentioned in the text or listed as a source/citation?

Answer in JSON only:
{{
  "answer_excerpt": "the first 200-400 characters of the assistant-style answer you wrote",
  "answer_mentions_site": true|false,
  "mention_quote": "exact sentence from the answer mentioning the site, or empty string if not mentioned",
  "cited_urls": ["urls cited in your answer (top 8)"],
  "why_site_missing": "if the site is missing: the most likely reason (competition, thin content, not indexed...); else empty string"
}}"""

PRESENCE_PROXY_JUDGE = """You are evaluating search-engine results for AI-visibility.

Question: "{query}"
Brand being audited: {brand} (domain: {domain})

Below are the top search results for this question:

{results}

Would an AI assistant (ChatGPT, Perplexity, Gemini, AI Overview) be likely to cite this brand in its answer for this question, based ONLY on this evidence? Consider prominence: does the brand appear in titles/snippets, does it rank in the top 5, are the results dominated by competitors?

Answer in JSON only:
{{"ai_would_cite": true|false, "reason": "one short sentence"}}"""

CONTENT_ANALYSIS = """You are a GEO (Generative Engine Optimization) auditor. You analyze a crawled website and produce evidence-backed findings on how likely AI engines are to quote and cite it.

AI engines (ChatGPT, Perplexity, Gemini, Google AI Overviews) select sources by their ability to *directly answer questions*: short quotable claims, statistics, Q&A blocks, tables, clear structure. They also need to establish the site's entity (who you are, via structured data and consistent naming) and trust signals (dates, authorship, about pages).

Website being audited:
- Domain: {domain}
- Brand (from title): {brand}
- Robots.txt: {robots}
- Sitemap found: {sitemap}
- Homepage title: {homepage_title}
- Homepage meta description: {homepage_meta}

Crawled pages (first {n} of {total}):

{pages}

Analyze ONLY the evidence above. Produce findings for three dimensions:

- "answerability": can AI engines extract crisp, quotable answers? Consider: stats with numbers, clear Q&A (FAQ sections), tables, headings structure, sentence-level clarity, short quotable claims, content length, thin pages. Cite exact quotes.
- "entity": does the site clearly establish what/who it is? Consider: JSON-LD structured data (Organization, Product, Service, FAQPage...), consistent brand naming across pages, About/Contact pages, robots/sitemap access, whether content is readable by crawlers (JS-rendered), meta descriptions and titles.
- "authority": trust and recognition signals. Consider: publication dates, authorship, original statistics, external citations to credible sources, brand consistency in headings, evidence the site is a primary source vs. aggregator.

For each finding include:
- title: short actionable statement
- severity: critical | major | minor | info (critical = blocks AI engines from citing the site at all; info = polish)
- evidence.page: exact URL the evidence came from
- evidence.quote: exact quote/snippet from that page (verbatim, from the content above)
- evidence.found: plain-English description of what exists today
- evidence.should_be: plain-English description of what it should be instead
- impact: 1-5 (how much fixing this raises AI visibility)
- effort: 1-5 (how hard for a small business owner)
- fix: COPY-PASTEABLE fix - an exact HTML/JSON-LD snippet, a rewording, or a precise step list. This goes straight into the customer's hands.
- jargon: one-line explanation of any jargon term you used, aimed at a business owner. Empty if none.

Also include 2-4 genuine strengths with evidence.

Rules:
- EVERY finding MUST carry evidence. The `evidence` object is REQUIRED, never omit it.
  - evidence.quote: a VERBATIM quote from the crawled content that proves the issue (or proves the positive). For absence findings ("no FAQ exists", "no stats anywhere"), quote the actual page text where the thing is missing - e.g. the section that should have an FAQ, the sentence that should contain a number. Never invent a quote.
  - evidence.found: exactly what exists today, in plain English.
  - evidence.should_be: what it should be instead, in plain English.
- Do not invent issues the evidence doesn't support. If a dimension is genuinely fine, return zero findings for it.
- Prefer a few deep findings over many shallow ones (max 16 findings total).

Return JSON only:
{{"findings": [...], "strengths": [{{"title": "...", "evidence": "..."}}], "summary": "2-3 sentence plain-language summary of the site's GEO health"}}"""

BRAND_KNOWLEDGE = """Without searching the web, using only your training knowledge: what do you know about the company "{brand}" (domain {domain})?

Be honest. If you have no reliable knowledge of this brand, say so explicitly.
Answer in JSON only: {{"known": true|false, "what_you_know": "short paragraph or 'no reliable knowledge'", "confident": true|false}}"""
