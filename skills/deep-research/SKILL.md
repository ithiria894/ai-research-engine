---
name: deep-research
description: Unified research skill — general-purpose deep research OR product competitive analysis. Auto-detects mode from input. Use for ANY research task — SEO, market trends, technical analysis, competitive landscape, best practices, industry updates, product positioning.
argument-hint: "<research question, topic, or product name>"
allowed-tools: [Bash, Read, Write, WebSearch, WebFetch, Agent, mcp__tavily__tavily_search, mcp__tavily__tavily_extract, mcp__tavily__tavily_research, mcp__tavily__tavily_crawl, mcp__tavily__tavily_map, mcp__exa__web_search_exa, mcp__exa__get_code_context_exa, mcp__exa__crawling_exa, mcp__firecrawl__firecrawl_search, mcp__firecrawl__firecrawl_scrape, mcp__firecrawl__firecrawl_crawl, mcp__firecrawl__firecrawl_map, mcp__newsmcp__get_news, mcp__newsmcp__get_topics, mcp__rss-reader__fetch_feed_entries, mcp__rss-reader__fetch_article_content, mcp__devto__get_articles, mcp__twitter__search_tweets, mcp__twitter__search_users, mcp__context7__query-docs, mcp__context7__resolve-library-id, mcp__paper-search__*, mcp__arxiv__*, mcp__semantic-scholar__*, mcp__scholar-mcp__*, mcp__youtube-transcript__*, mcp__open-websearch__*, mcp__paper-distill__*, mcp__superprecio__*, mcp__chrome-devtools__take_screenshot, mcp__gmail__*, mcp__teams__*]
---

# Research — Unified Deep Research + Product Analysis

**ALWAYS read `research-engine.md` FIRST** (same directory as this skill, or `~/MyGithub/ai-research-engine/research-engine.md`) for the full tool inventory, cost rules, and Quota Classification.

## Mode Detection

This skill has two modes. Auto-detect from input:

**Product Mode** — if ANY of these are true:
- Input matches an existing product name in `~/MyGithub/agentic-journal/projects/products/*.md`
- Input contains: "competitive", "market", "SWOT", "positioning", "vs", "alternative to", "compare"
- User explicitly says `--product` or asks about a product idea
- → Go to [Product Mode Workflow](#product-mode-workflow)

**General Mode** — everything else:
- SEO research, technical deep dives, hiring patterns, trend analysis, best practices, any question
- → Go to [General Mode Workflow](#general-mode-workflow)

---

## Agent Model Selection

Research agents are data collectors, not decision makers. Use the cheapest model that can operate the tools reliably.

**Default: launch all research agents with `model: "sonnet"`.**

- **Sonnet** — for all search/collect/extract tasks. Can use every MCP tool, follows structured instructions, costs 5x less than Opus.
- **Haiku** — for simple single-source lookups (e.g., "search arxiv for X"). Costs 25x less than Opus. Use when the agent only needs 1-2 tools.
- **Opus** — NEVER use for research agents. Opus does synthesis in the main thread after agents return. Sending Opus to do web searches is like sending a surgeon to fetch bandages.

The pattern: **Sonnet/Haiku collect → Opus synthesizes.** Research agents bring back raw data + citations. The main thread (Opus) does cross-referencing, gap analysis, and final judgment.

---

## Tools Catalog

Launch as many searches as possible simultaneously. Don't do them one by one.

### Web Search (use ALL of these)
```
mcp__tavily__tavily_search — LLM-optimized search (best for factual queries)
mcp__exa__web_search_exa — semantic search (best for "find pages similar to X")
mcp__open-websearch__* — 8 engines (Bing/Baidu/DDG/Brave/Exa/GitHub/Juejin/CSDN), zero API keys
mcp__firecrawl__firecrawl_search — another web search source
WebSearch — built-in web search
```

### Content Extraction (when you find a good URL)
```
mcp__tavily__tavily_extract — extract clean content from URLs
mcp__exa__crawling_exa — crawl and extract from URLs
mcp__firecrawl__firecrawl_scrape — scrape single page
mcp__rss-reader__fetch_article_content — extract article text
```

### Platform-Specific
```
mcp__devto__get_articles — Dev.to articles by tag/keyword
mcp__twitter__search_tweets — Twitter/X discussions
mcp__newsmcp__get_news — real-time news clusters
mcp__rss-reader__fetch_feed_entries — RSS feeds (Simon Willison, HN, etc.)
gh search issues/repos — GitHub ecosystem data
```

### Technical/Code
```
mcp__context7__query-docs — latest library documentation
mcp__exa__get_code_context_exa — code examples and docs (82.8% completeness vs 59.8% for WebFetch)
```

### Academic Papers (use ALL for comprehensive literature search)
```
mcp__paper-search__* — search 20+ academic platforms (arXiv, S2, OpenAlex, Crossref, CORE, dblp, DOAJ, Zenodo) ⭐919
mcp__arxiv__* — arXiv semantic search + citation analysis + trend analysis ⭐2.4K
mcp__semantic-scholar__* — Full S2 API: citation networks, recommendations, batch ops
mcp__scholar-mcp__* — ~97% peer-reviewed coverage, 6 sources, download + READ paper PDFs ⭐NEW
mcp__paper-distill__* — 11-source parallel academic search with weighted ranking ⭐53
```

### Academic Papers — Worth Installing (not yet installed, need Python ≥3.12 or clone)
```
academia_mcp — ArXiv + ACL Anthology + HF Datasets + Semantic Scholar ⭐78 (needs Python ≥3.12)
openalex-mcp — 250M papers via free OpenAlex API ⭐15 (needs git clone)
PaperMCP — ArXiv/HF/Google Scholar/OpenReview/DBLP/PapersWithCode, 32 tools (github.com/ScienceAIHub/PaperMCP)
research-paper-mcp — autonomous arXiv + S2 ingestion, memory storage (playbooks.com/mcp/marc-shade/research-paper-mcp)
```

### Video/Transcript
```
mcp__youtube-transcript__* — YouTube video transcripts + metadata (free, no key)
```

### Prediction Markets (Round 9)
```
Polymarket Gamma API — real-money outcome predictions (free, zero key, zero limit)
  curl "https://gamma-api.polymarket.com/markets?tag=ai&closed=false"
  When to use: trend-sensitive topics, elections, geopolitics, tech launches, crypto
  Polymarket odds are among the highest-signal data — real money > opinion
```

### Trend & Social Intelligence (Round 9)
```
trendsmcp — Google/YouTube/TikTok/Reddit/Amazon/npm/GitHub trends (100 free/mo)
social-trends-mcp — Reddit + HN trending (free, zero key)
google-trends-mcp — Google Trends wrapper (free)
Bluesky AT Protocol — public.api.bsky.app (free, near-zero rate limit)
Mastodon API — per-instance public timelines + trending (free, 300 req/5min)
Lobste.rs JSON — append .json to any URL (free)
Hashnode GraphQL — gql.hashnode.com (free, zero auth for read)
Discourse API — {instance}/search.json (free, most instances zero auth)
StackExchange API — 170+ sites beyond SO (free key, 10K req/day)
Truth Social API — Mastodon-compatible, US political discourse (needs bearer token)
小紅書 (Xiaohongshu) — Chinese lifestyle/consumer platform (via xiaohongshu-mcp or ScrapeCreators)
```

### Package Registries & Dev Ecosystem (Round 9)
```
PyPI Stats API — pypistats.org/api/ (free, zero key)
crates.io API — Rust packages (free, zero key)
Packagist API — PHP packages (free, zero key)
RubyGems API — Ruby gems (free, zero key)
Homebrew Analytics — formulae.brew.sh/api/ (free, zero key, ZERO rate limit)
Docker Hub API — hub.docker.com/v2/ (free, total pull count only)
HuggingFace Hub API — AI/ML model trending (free, zero key)
libraries.io API — 40+ registries cross-analysis (free key, 60 req/min)
VS Code Marketplace — unofficial endpoint (free, zero key)
OSV.dev — open source vulnerability data (free, zero key)
```

### Citation & Academic Metrics (Round 9)
```
OpenCitations API — citation graph, DOI-to-DOI (free, zero key, 180 req/min)
NIH iCite API — field-normalized impact RCR metric (free, zero key)
ORCID API — researcher identity + publications (free, zero key)
ROR API — Research Organization Registry, 120K+ institutions (free, zero key)
OpenAIRE API — EU-funded research + datasets + software (free)
medRxiv API — health sciences preprints (free, zero key)
Altmetric API — social/news attention metrics (free for research)
```

### Patent & IP (Round 9)
```
USPTO PatentsView API — US patent search (free key, 45 req/min)
EPO OPS — European + WIPO + multi-country patents (free registration, 4 GB/week)
Lens.org API — 140M+ patents + scholarly citation cross-analysis (free for research)
```

### Government & Economic (Round 9)
```
FRED API — 840K+ economic time series (free key, 120 req/min)
BLS API — US employment/wages/CPI (free, v1 zero key 25/day, v2 free key 500/day)
Congress.gov API — US legislation (free key, 1000 req/hr)
Federal Register API — US regulations (free, zero key)
SEC EDGAR — US company filings (free, zero key, 10 req/sec)
UK Companies House — company directors/filings (free key, 600 req/5min)
World Bank API — 16K+ indicators, 200+ countries (free, zero key)
openFDA — drug/device/food safety data (free, zero key, 240 req/min)
```

### Company & Startup (Round 9)
```
YC OSS API — 5,690 YC companies (free, zero key, daily updated)
AI Funding API — aifunding.me AI startup rounds (free, zero key)
Finnhub — stock/news/fundamentals/IPO (free key, 60 req/min)
FMP — IPO calendar + M&A + financials (free key, 250 req/day)
OpenCorporates — 200M+ global companies (free for open-data)
```

### SEO & Web Infrastructure (Round 9)
```
Open PageRank — domain authority via Common Crawl (free key, 4.3M/day)
OpenRank.io — bulk DA on 40M domains (free, 10K req/24h)
crt.sh — SSL cert + subdomain discovery (free, zero key, zero limit)
Google PageSpeed Insights — Lighthouse + CWV (free, 25K req/day)
Tranco — research-grade top-1M domain ranking (free, zero key)
Wayback CDX — URL snapshot history (free, zero key)
Common Crawl CDX — web-scale crawl index (free, zero key)
Serper.dev — Google SERP JSON (free 2,500/mo)
```

### Podcast & Media (Round 9)
```
PodcastIndex API — 4M+ podcasts (free key)
Apple Podcasts/iTunes API — podcast search (free, zero key)
Open Library API — book search (free, zero key)
Internet Archive API — all media types (free, zero key)
```

### Knowledge Graph (Round 9)
```
Wikidata SPARQL — structured entity queries (free, zero key, 60s timeout)
```

### Site Discovery
```
mcp__tavily__tavily_map — find all URLs on a domain
mcp__firecrawl__firecrawl_map — same, different source
mcp__tavily__tavily_crawl — crawl entire site sections
mcp__firecrawl__firecrawl_crawl — same, different source
```

### Deep Research Agents (use for comprehensive multi-source research)
```
GPT Researcher MCP — autonomous deep research agent, 26K⭐, produces cited reports
STORM (Stanford) — Wikipedia-quality report generation, 28K⭐, multi-perspective synthesis
node-DeepResearch (Jina) — iterative search+read+reason until answer found, 5.1K⭐
local-deep-research — ~95% SimpleQA, local+cloud LLMs, arXiv/PubMed/web, 4.2K⭐
Khoj — AI second brain, deep research + custom agents, 33.7K⭐
AI-Research-SKILLs — research skill library for any AI model, 5.8K⭐ (Orchestra Research)
EvoScientist — self-evolving AI scientists, 2.4K⭐
SurfSense — open-source NotebookLM/Perplexity, connects to Tavily/Slack/Notion/GitHub, 13.6K⭐
RAGFlow — RAG engine + agent capabilities, document ingestion + vector indexing, 76.5K⭐
```

### Free APIs (use via Bash curl — zero key, zero quota)
```
GDELT — global events/news: curl "https://api.gdeltproject.org/api/v2/doc/doc?query=...&mode=ArtList&format=json"
HN Firebase — full HN data: curl "https://hacker-news.firebaseio.com/v0/topstories.json"
OpenAlex — 250M papers: curl "https://api.openalex.org/works?search=..."
Semantic Scholar — citation networks, recommendations: curl "https://api.semanticscholar.org/graph/v1/paper/search?query=...&fields=title,year,citationCount"
Crossref — 150M+ DOIs, metadata: curl "https://api.crossref.org/works?query=..."
CORE — 300M+ open access papers: curl "https://api.core.ac.uk/v3/search/works?q=..."
PubMed — biomedical: curl "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=..."
Europe PMC — European biomedical: curl "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=..."
DBLP — CS papers: curl "https://dblp.org/search/publ/api?q=...&format=json"
DOAJ — Open Access Journals: curl "https://doaj.org/api/search/articles/..."
Zenodo — research data: curl "https://zenodo.org/api/records?q=..."
bioRxiv — biology preprints: curl "https://api.biorxiv.org/details/biorxiv/2026-03-01/2026-03-28"
arXiv API — papers by category/keyword: curl "https://export.arxiv.org/api/query?search_query=..."
Unpaywall — find open access PDFs by DOI: curl "https://api.unpaywall.org/v2/{doi}?email=you@example.com"
HN Algolia — full-text search all HN history: curl "http://hn.algolia.com/api/v1/search?query=..."
Stack Overflow — developer adoption trends: curl "https://api.stackexchange.com/2.3/questions?tagged=...&site=stackoverflow"
npm Downloads — package download trends: curl "https://api.npmjs.org/downloads/range/last-month/{pkg}"
Wikipedia — entity verification + pageviews: curl "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=..."
```

### GitHub CLI (use via Bash — already installed)
```
gh search repos "query" --sort stars — find repos by topic
gh search issues "query" — find issues/discussions
gh api repos/{owner}/{repo} — get repo metadata
gh api search/repositories?q=... — advanced search
```

---

## General Mode Workflow

**Architecture: Sonnet collects, Opus synthesizes.**

The skill has three phases. Phase 1 (collection) is delegated to Sonnet/Haiku agents. Phase 1.5 (verification) is one Sonnet agent that audits coverage. Phase 2 (synthesis) is done by you (Opus) in the main thread. NEVER do collection yourself — launch agents.

### Step 0: Topic Classification (Opus, before launching agents)

Before launching any agents, classify the topic to determine which agent clusters are relevant. This prevents wasting tokens on irrelevant sources (e.g., patent search for "best React library").

```
Classify the topic into ONE OR MORE of these categories:

TECH_DEV     — libraries, tools, frameworks, APIs, coding patterns
ACADEMIC     — research questions, literature reviews, scientific topics
MARKET       — competitive analysis, product positioning, market sizing
POLICY       — laws, regulations, government policy, compliance
FINANCIAL    — markets, economics, funding, crypto, company financials
SOCIAL_TREND — what's trending, public sentiment, viral content, predictions
HEALTH       — medical, biomedical, drug safety, clinical trials
GENERAL      — anything that doesn't fit above, or multi-category
```

Each category activates specific agent clusters (see Step 2). A topic can match multiple categories — "AI regulation market impact" would be POLICY + FINANCIAL + TECH_DEV.

### Phase 1: Collection (Sonnet agents, background)

#### Step 1: Understand the Question
- What exactly does the user want to know?
- What would a comprehensive answer look like?
- What categories did Step 0 identify?

#### Step 2: Launch Parallel Sonnet Agents
Design agents based on the topic categories from Step 0. Launch ALL in ONE message with `model: "sonnet"` and `run_in_background: true`.

**ALWAYS include (every topic):**
- **Agent: Web Search** — WebSearch + Tavily Search + Exa Search + Firecrawl Search + open-websearch
- **Agent: News & Events** — newsmcp + GDELT curl + RSS feeds + Google News

**Include if TECH_DEV:**
- **Agent: Code & Libraries** — GitHub CLI + Exa Code Context + Context7 + npm/PyPI/crates.io download APIs
- **Agent: Dev Community** — StackExchange (170+ sites) + Discourse + Hashnode + DEV.to + Lobste.rs + HN Algolia
- **Agent: Package Ecosystem** — npm Downloads + PyPI Stats + Homebrew Analytics + Docker Hub + HuggingFace Hub + libraries.io + OSV.dev (security)

**Include if ACADEMIC:**
- **Agent: Papers** — paper-search-mcp + arxiv + semantic-scholar + paper-distill + OpenAlex curl + DBLP curl + Crossref curl + PubMed curl
- **Agent: Citations & Impact** — OpenCitations + NIH iCite + ORCID + ROR + Altmetric + OpenAIRE + medRxiv/bioRxiv
- **Agent: Patents** — USPTO PatentsView curl + EPO OPS + Lens.org (if IP-relevant)

**Include if MARKET:**
- **Agent: Competitors** — WebSearch "alternative to X" + GitHub repos + npm/PyPI search + Exa semantic search
- **Agent: User Pain Points** — Reddit (mcp-reddit) + StackExchange + Twitter + Discourse + Bluesky
- **Agent: Company & Funding** — SEC EDGAR curl + YC OSS API curl + Finnhub curl + FMP curl + OpenCorporates curl + AI Funding API curl
- **Agent: Distribution** — npm Downloads + Product Hunt API + Wayback CDX + App store (Asodesk/appgoblin if mobile)

**Include if POLICY:**
- **Agent: Government & Regulation** — Congress.gov curl + Federal Register curl + us-gov-open-data-mcp + World Bank curl + OECD
- **Agent: Patents & IP** — USPTO PatentsView + EPO OPS + Lens.org

**Include if FINANCIAL:**
- **Agent: Financial Data** — FRED curl + BLS curl + SEC EDGAR curl + Finnhub curl + FMP curl + CoinGecko curl
- **Agent: Company Intel** — UK Companies House curl + OpenCorporates curl + YC OSS API curl

**Include if SOCIAL_TREND:**
- **Agent: Social Platforms** — Reddit (mcp-reddit) + Twitter + Bluesky AT Protocol curl + Mastodon API curl + Lemmy curl + Hashnode + DEV.to
- **Agent: Trend Signals** — trendsmcp + Google Trends + Polymarket Gamma API curl + TikTok/Instagram (via ScrapeCreators or trendsmcp)
- **Agent: Video & Podcasts** — YouTube transcripts + PodcastIndex curl + iTunes API curl

**Include if HEALTH:**
- **Agent: Biomedical** — PubMed + bioRxiv/medRxiv + Europe PMC + NIH iCite + openFDA curl
- **Agent: Clinical** — BiomCP (PubMed + ClinicalTrials.gov)

**Include if GENERAL or multi-category:**
- Launch agents from ALL matching categories. When in doubt, include rather than exclude.

**Agent: Content Extraction (second wave):**
- Launch AFTER first wave returns if specific URLs need deep-diving: Tavily Extract + Exa Crawl + Firecrawl Scrape

Each agent's prompt MUST include:
- "Report raw findings with URLs. Do NOT synthesize or draw conclusions."
- "Use tables and structured formats. Paste key quotes directly."
- "Cite every finding with a source URL."
- "At the END of your report, add a CONFIDENCE section: rate your confidence 1-5 that you found comprehensive data, and list any GAPS — topics you searched for but found little/nothing on."

Agents return RAW DATA — lists of papers, URLs, quotes, numbers. Not analysis. Plus a confidence rating + gap list for the verification step.

#### Step 3: Wait for all agents to complete
Do not proceed until all background agents have returned.

### Phase 1.5: Verification (Sonnet, BEFORE synthesis — Round 9 新增)

After ALL Phase 1 agents return, launch ONE Sonnet verification agent with ALL agent results:

```
Verification Agent prompt:
"You are a research completeness auditor. Given these findings from [N] agents:
[paste all agent results]

Evaluate:
1. COVERAGE: Which aspects of the research question are well-covered? Which are MISSING?
2. CONTRADICTIONS: Do any sources contradict each other? List each contradiction with both claims + sources.
3. CONFIDENCE: Rate overall confidence 1-5 (1=barely any data, 5=comprehensive multi-source coverage).
4. GAPS: What specific follow-up searches would fill the biggest gaps?

Output a structured JSON:
{
  'coverage_score': 1-5,
  'well_covered': ['topic A', 'topic B'],
  'missing': ['topic X', 'topic Y'],
  'contradictions': [{'claim_a': '...', 'source_a': '...', 'claim_b': '...', 'source_b': '...'}],
  'recommended_followup': ['search query 1', 'search query 2']
}
"
```

**If coverage_score < 3**: Launch follow-up agents targeting the gaps before synthesis.
**If contradictions found**: Flag them explicitly in the final report — never silently merge conflicting claims.

> This step is based on VMAO (ICLR 2026) which improved answer completeness from 3.1 → 4.2/5.

### Phase 2: Synthesis (Opus, main thread)

#### Step 4: Cross-Reference and Synthesize
YOU (Opus) do this — not an agent. Read all agent results and:
- Compare findings across sources
- Flag contradictions
- Identify consensus vs outlier opinions
- Find the GAP — what's missing from existing research/products?
- Cite sources for every claim

#### Step 5: Report

```markdown
# Research: [Topic]
Date: [today]
Sources: [count] sources across [count] tools
Coverage Score: [1-5 from verification agent]

## Key Findings
1. [Finding with source]
2. [Finding with source]
...

## Detailed Analysis
[Organized by subtopic]

## Contradictions & Disputes
[Any conflicting claims between sources — list both sides with citations. Never silently merge.]

## What's New (if researching updates)
[Only things that changed recently]

## Gaps & Limitations
[What the research could NOT find or verify. Be honest about blind spots.]

## Actionable Recommendations
[What to do based on findings]

## Quality Assessment (DRACO dimensions)
- Factual accuracy (52% weight): [self-rate 1-5]
- Analytical depth (22% weight): [self-rate 1-5]
- Presentation (14% weight): [self-rate 1-5]
- Source attribution (12% weight): [self-rate 1-5]

## Sources
[Full list with URLs]
```

#### Step 6: Save Results
Save to a configurable output path (default: `./research/[topic-slug]-[date].md`).

---

## Product Mode Workflow

### Reference Documents
- **Research Engine (MASTER TOOL LIST)**: `research-engine.md` (same directory, or configure path)
- **Existing products / product specs**: configure per project

### Step 1: Understand What to Research

If user gives a product name:
- Read the product spec / README from the repo
- Identify the core value proposition in 1 sentence

If user gives an idea (e.g. "MCP server for browser recording"):
- Clarify the core value proposition in 1 sentence

### Step 2: Phase 0 — Reality Check (FREE, 2 min)
```
idea-reality-mcp: scan GitHub + HN + npm + PyPI + PH
→ Reality score < 30 = green light
→ Reality score > 70 = pivot or differentiate
```

### Step 3: Phase 1 — Broad Scan (parallel agents, ALL FREE TOOLS)

> ⚠️ Free tools first. After Phase 1, ask user: "免費搵到 X 個結果，需唔需要用 paid tools 再深入？"

Launch ALL agents in ONE message with `model: "sonnet"` and `run_in_background: true`.

#### Agent A: Direct Competitors — FREE
```
→ WebSearch + open-websearch + Exa Search ("alternative to {product}")
→ gh search repos + gh api search/repositories (GitHub landscape)
→ npm search + npm Downloads API + PyPI Stats API (package ecosystem adoption velocity)
→ libraries.io API (cross-registry dependents + SourceRank)
→ Homebrew Analytics + Docker Hub API (if CLI/infra tool)
→ VS Code Marketplace (if IDE extension)
→ HuggingFace Hub API (if AI/ML tool)
```

#### Agent B: User Pain Points — FREE
```
→ mcp-reddit / Reddit .json (subreddit pain points)
→ StackExchange API (170+ sites — tagged questions volume + answers)
→ Discourse API (OSS community forums: Rust/React/OpenAI/Julia)
→ Bluesky AT Protocol + Mastodon API (tech discourse)
→ Twitter search (mcp__twitter__search_tweets)
→ Hashnode + DEV.to (developer blog posts about the problem)
→ Lobste.rs JSON (high-signal tech community)
→ WebSearch ("{category} problems frustrations")
```

#### Agent C: Market Trends + News — FREE
```
→ newsmcp (real-time clustered news)
→ GDELT curl (global news events)
→ Dev.to API (trending articles)
→ HN Algolia API (search HN history)
→ rss-reader (competitor blog RSS feeds)
→ trendsmcp / Google Trends (search interest over time)
→ Polymarket Gamma API (prediction market odds if applicable)
```

#### Agent D: Technical Feasibility — FREE
```
→ Context7 (library docs)
→ Exa Code Context (code examples, SDK docs — better than WebFetch per WebCode benchmark)
→ GitHub CLI (reference repos, architecture, contributor activity)
→ YouTube transcripts (conference talks about the space)
→ PodcastIndex + iTunes API (podcast discussions about the space)
→ paper-search-mcp / arxiv-mcp (if research-heavy area)
```

#### Agent E: Distribution & Ecosystem — FREE
```
→ npm Downloads + PyPI Stats + crates.io + Homebrew Analytics (adoption curves)
→ libraries.io (who depends on this? cross-registry)
→ Product Hunt API (launches + upvotes)
→ Wayback CDX (competitor website evolution)
→ Wikipedia API (entity verification)
→ Open PageRank + OpenRank.io (competitor domain authority)
→ crt.sh (competitor infrastructure — subdomains)
→ Asodesk API / appgoblin (if mobile app)
```

#### Agent F: Market Signals — FREE
```
→ jobspy (hiring trends = market demand signal)
→ SEC EDGAR curl (if competitor is public — filings, Form D funding)
→ YC OSS API (is competitor YC-backed?)
→ AI Funding API (AI startup funding rounds)
→ Finnhub curl (stock/news if public company)
→ OpenCorporates curl (company registry info)
→ UK Companies House curl (if UK competitor)
→ Open Collective API (OSS project funding)
→ WebSearch ("{category} funding series A")
```

#### Agent G: SEO & Web Intelligence — FREE
```
→ Open PageRank + OpenRank.io (domain authority comparison)
→ Google PageSpeed Insights (competitor site performance)
→ Serper.dev (Google SERP — who ranks for target keywords?)
→ crt.sh (SSL cert history — how old is their infrastructure?)
→ Tranco (domain ranking comparison)
→ DetectZeStack / Wappalyzer (competitor tech stack)
```

### Step 3.5: Verification (same as General Mode Phase 1.5)

After ALL agents return, launch ONE Sonnet verification agent to check coverage + contradictions. See [Phase 1.5: Verification](#phase-15-verification-sonnet-before-synthesis--round-9-新增) for the full prompt.

If coverage_score < 3 or major gaps found, launch follow-up agents before proceeding.

### Step 4: Phase 2 — Paid Deep Dive (ONLY if Phase 1 insufficient)

> 💰 Ask user first. Budget: ~$0.50-1.00 per session.

```
If need deeper competitor analysis:
  → Tavily Research (deep, multi-source synthesis)
  → Exa Search (semantic: similar tools Phase 1 missed)
  → Firecrawl Scrape (competitor docs/pricing)

If need more pain point evidence:
  → Tavily Search (targeted deep search)

If need social sentiment:
  → Twitter API ($0.005/read — only most important threads)
  → ScrapeCreators (TikTok + Instagram data)
```

### Step 5: Comparison Table

| | Our Product | Competitor A | Competitor B | Competitor C |
|---|---|---|---|---|
| **Name** | | | | |
| **GitHub stars** | | | | |
| **npm downloads** | | | | |
| **Price** | | | | |
| **Key feature 1** | | | | |
| **Key feature 2** | | | | |
| **Key feature 3** | | | | |
| **Weakness** | | | | |
| **Last updated** | | | | |
| **MCP native?** | | | | |

### Step 6: SWOT Analysis

| | Positive | Negative |
|---|---|---|
| **Internal** | **Strengths**: what we do better | **Weaknesses**: what we lack |
| **External** | **Opportunities**: market gaps we can fill | **Threats**: competitors that could kill us |

### Step 7: Positioning Recommendation

1. **Our unique angle** — the 1 sentence that differentiates us
2. **Target user** — who specifically should we market to?
3. **Messaging** — how to describe the product
4. **Missing features** — what should we add?
5. **Distribution priority** — which channels matter most?

### Step 8: Quality Assessment (DRACO dimensions)

Same as General Mode — rate the research output:
- Factual accuracy (52% weight): [self-rate 1-5]
- Analytical depth (22% weight): [self-rate 1-5]
- Presentation (14% weight): [self-rate 1-5]
- Source attribution (12% weight): [self-rate 1-5]

Also include:
- **Contradictions & Disputes** — any conflicting claims between sources
- **Gaps & Limitations** — what the research could NOT find or verify

### Step 9: Save Results
Save findings to a configurable output path (default: `./research/[product]-[date].md`).

---

## Rules

1. **Read research-engine.md FIRST** — every time, no exceptions
2. **Use ALL available FREE tools** — don't just use one source. Parallel everything.
3. **Parallel execution** — launch multiple searches simultaneously
4. **🚨 FREE TOOLS ONLY BY DEFAULT** — NEVER use paid/limited tools without asking first:
   - After free phase, ASK: "Found X results from free sources. Want to use paid/limited APIs for deeper coverage? (Tavily Research, Exa, Firecrawl, Twitter, ScrapeCreators)"
   - If user says NO → go straight to synthesis with free results
   - If user says YES → THEN use the paid tools
   - See research-engine.md **Quota Classification** for which tools are free vs limited
5. **Cite everything** — no claims without sources
6. **Be specific** — "42% increase" not "significant increase"
7. **Report what's NEW** — if the user asks about 2026 updates, don't give generic 2024 advice
8. **Cross-reference** — if only one source says something, flag it as unverified
9. **Exa Code Context > Claude WebFetch** for code docs (WebCode benchmark: 82.8% vs 59.8% completeness)
10. **Be brutally honest** — in product mode, if our product is worse, say so
