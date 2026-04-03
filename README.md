# AI Research Engine

The most comprehensive data source inventory and methodology for AI-powered research. 100+ free APIs, 40+ MCP servers, and a multi-agent workflow that makes "just Google it" look like using a flashlight to search the ocean floor.

## The Problem

When you ask AI to research something, here's what actually happens:

1. **"Just ask AI"** - It answers from training data. Outdated, often wrong, and it won't tell you what it doesn't know.
2. **"AI helps you Google"** - Google only indexes a fraction of the world's data. No academic papers, no patent filings, no package download stats, no prediction market odds, no SEC company filings, no app store data.
3. **"Google it yourself"** - You get the first page of results. Maybe the second. You miss everything that isn't SEO-optimized.

The real data lives in 100+ specialized databases, registries, and APIs. Most of them are free. Almost nobody uses more than 2 or 3 at once.

## What This Is

A research infrastructure for AI agents. Not another chatbot wrapper. Not another "deep research" tool that just does 5 Google searches in a row.

This is:
- **A complete inventory** of 100+ free data sources with curl examples, rate limits, and auth requirements for every single one
- **A multi-agent methodology** where cheap models (Sonnet) collect from dozens of sources in parallel, then a powerful model (Opus) cross-references and synthesizes
- **A verification step** that checks coverage, flags contradictions, and identifies gaps before producing the final report
- **A quality framework** (DRACO dimensions) that scores output on factual accuracy, analytical depth, presentation, and source attribution

## Coverage

| Category | Sources | Examples |
|----------|---------|----------|
| **Web Search** | 10+ engines | Tavily, Exa, Firecrawl, SearXNG, DuckDuckGo, Bing, Brave, Google |
| **Academic Papers** | 250M+ papers | Semantic Scholar, OpenAlex, arXiv, PubMed, Crossref, CORE, DBLP, DOAJ, Zenodo |
| **Citations & Impact** | 6 APIs | OpenCitations, NIH iCite (RCR metric), ORCID, ROR, Altmetric, OpenAIRE |
| **Patents** | 140M+ patents | USPTO PatentsView, EPO OPS, Lens.org, Google Patents BigQuery |
| **Social & Community** | 15+ platforms | Reddit, X/Twitter, Bluesky, Mastodon, HN, Lobste.rs, Discourse, Discord, Telegram, Slack, StackExchange (170+ sites), Hashnode, DEV.to, Lemmy |
| **Trends & Predictions** | 8+ sources | Google Trends, TrendsMCP, Polymarket, TikTok, Instagram, YouTube, Truth Social |
| **News & Media** | 6+ sources | GDELT, newsmcp, NewsAPI, NYTimes, RSS feeds, Google News |
| **Podcasts** | 190M+ episodes | PodcastIndex, Apple Podcasts/iTunes, Listen Notes |
| **Package Registries** | 10 registries | npm, PyPI, crates.io, Packagist, RubyGems, NuGet, Homebrew, Docker Hub, HuggingFace, libraries.io (40+ registries) |
| **Company & Startup** | 7+ sources | SEC EDGAR, UK Companies House, YC OSS API, Finnhub, FMP, OpenCorporates, AI Funding API |
| **Government & Economic** | 10+ sources | FRED (840K time series), BLS, Census, Congress.gov, Federal Register, World Bank, IMF, OECD, openFDA, USASpending |
| **SEO & Web Infrastructure** | 8+ sources | Open PageRank, crt.sh, Google PageSpeed, Tranco, Wayback CDX, Common Crawl, Serper.dev, Cloudflare Radar |
| **AI Brand Visibility** | 3 tools | Aperture, AICW, Citatra (track how ChatGPT/Perplexity/Claude mention your brand) |
| **Knowledge Graph** | 2 sources | Wikidata SPARQL, Wikipedia API |
| **Books & Media** | 3 sources | Open Library, Internet Archive, Rumble |

## How It Works

```
Phase 0: Reality Check (2 min)
  idea-reality-mcp scans GitHub + HN + npm + PyPI + Product Hunt
  → Score < 30 = green light, > 70 = pivot

Phase 1: Parallel Collection (10-30 min)
  Launch N Sonnet agents, each covering a source cluster
  Every agent reports: raw findings + confidence score + gaps

Phase 1.5: Verification (new)
  One Sonnet agent audits all results:
  → Coverage score 1-5
  → Contradictions flagged
  → Missing topics identified
  → If score < 3, launch follow-up agents

Phase 2: Paid Deep Dive (optional, only if user approves)
  Tavily Research, Exa semantic search, Firecrawl scraping

Phase 3: Synthesis (Opus)
  Cross-reference all sources
  Flag contradictions (never silently merge conflicting claims)
  Score on DRACO dimensions (factual accuracy, analytical depth, presentation, source attribution)
  Output structured report with full citations
```

## What Makes This Different

**vs Google Search**: Google indexes web pages. We query 100+ specialized databases directly. Patent filings, academic citations, package download trends, prediction market odds, SEC company filings, government economic data -- none of this shows up on page 1 of Google.

**vs ChatGPT / Claude / Gemini "deep research"**: They do 5-10 web searches and synthesize. We do 100+ parallel queries across specialized APIs, then verify coverage and flag contradictions before synthesizing. Their citation accuracy is 40-80% (DeepTRACE, NeurIPS 2025). We add a verification step specifically to catch that.

**vs last30days**: Great tool for social recency (Reddit/X/TikTok/Instagram in the last 30 days). We cover that plus academic papers, patents, government data, package registries, company filings, podcasts, prediction markets, and 80+ more sources with no time restriction.

**vs awesome-mcp-servers**: Lists MCP servers by name. We list every data source with curl examples, exact rate limits, auth requirements, and a methodology for using them together.

**vs public-apis**: Lists 1400+ APIs. We curate the ones that matter for research, show how to use them with AI agents, and provide a workflow that ties them together.

## Files

```
research-engine.md          # Master inventory: every API, MCP, and data source
skills/deep-research/       # Claude Code skill: the multi-agent workflow
  SKILL.md                  # Full methodology + agent prompts + report template
```

## Quick Start

### Use the data source inventory directly

`research-engine.md` is a standalone reference. Every API has a curl example you can run right now:

```bash
# Search 250M+ academic papers
curl "https://api.openalex.org/works?search=large+language+models&sort=publication_date:desc"

# Check prediction market odds
curl "https://gamma-api.polymarket.com/markets?tag=ai&closed=false"

# Search US patents
curl "https://search.patentsview.org/api/v1/patent/?q=machine+learning"

# Get Python package download trends
curl "https://pypistats.org/api/packages/langchain/recent"

# Search 840K+ economic time series
curl "https://api.stlouisfed.org/fred/series/search?search_text=unemployment&api_key=YOUR_FREE_KEY&file_type=json"
```

### Use as a Claude Code skill

Copy `skills/deep-research/` to `~/.claude/skills/deep-research/` and invoke with `/deep-research "your question"`.

The skill reads `research-engine.md` on every run to get the latest tool inventory.

## Contributing

Found a free API or MCP server we're missing? Open an issue or PR. The bar is:
- Must be free or have a meaningful free tier
- Must have a working API (not just a website)
- Must include: name, URL, what data it provides, rate limits, auth requirements

## License

MIT
