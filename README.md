# AI Research Engine

The most comprehensive data source inventory and methodology for AI-powered research. 100+ free APIs, 40+ MCP servers, and a multi-agent workflow that makes "just Google it" look like using a flashlight to search the ocean floor.

## The Problem

When you ask AI to research something, here's what actually happens:

1. **"Just ask AI"** — It answers from training data. Outdated, often wrong, and it won't tell you what it doesn't know.
2. **"AI helps you Google"** — Google only indexes a fraction of the world's data. No academic papers, no patent filings, no package download stats, no prediction market odds, no SEC company filings, no app store data.
3. **"Google it yourself"** — You get the first page of results. Maybe the second. You miss everything that isn't SEO-optimized.

The real data lives in 100+ specialized databases, registries, and APIs. Most of them are free. Almost nobody uses more than 2 or 3 at once.

## What This Is

A research infrastructure for AI agents. Not another chatbot wrapper. Not another "deep research" tool that just does 5 Google searches in a row.

This is:
- **A complete inventory** of 100+ free data sources with curl examples, rate limits, and auth requirements for every single one
- **A multi-agent methodology** where cheap models (Sonnet) collect from dozens of sources in parallel, then a powerful model (Opus) cross-references and synthesizes
- **A source selection step** that reasons about your specific question and picks which of 18 source clusters are actually relevant — like a pharmacist picking medicines for a patient, not just dumping the whole pharmacy
- **A pre-flight check** that silently verifies what tools are installed before presenting options, so you're never silently missing coverage
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
Step 0: Source Selection (Opus, before any agents launch)
  Analyze the question → reason about which of 18 source clusters are relevant
  Pre-flight check: silently verify what tools are installed/configured
  Present sources grouped by WHY (not just a flat list)
  Flag missing tools with install instructions
  User confirms: go / just use what's ready / let me adjust

Phase 1: Collection (Sonnet agents, parallel)
  Launch one agent per confirmed cluster, all in the background
  Each agent: raw findings + confidence score + gaps
  Sonnet costs 5x less than Opus — right model for data collection

Phase 1.5: Verification
  One Sonnet agent audits all results:
  → Coverage score 1-5
  → Contradictions flagged
  → Missing topics identified
  → If score < 3, launch follow-up agents

Phase 2: Synthesis (Opus, main thread — never delegated)
  Cross-reference all sources
  Flag contradictions (never silently merge conflicting claims)
  Score on DRACO dimensions (factual accuracy, analytical depth, presentation, source attribution)
  Output structured report with full citations
```

## Source Selection — the "Pharmacist Model"

The skill doesn't just fire all 18 clusters at every question. That wastes time and tokens. Before launching a single agent, it reasons about your specific question and picks which clusters would actually contain relevant data.

The question "Has anyone built an MCP server for browser recording?" has very different source needs than "What's the economic impact of AI regulation?" The skill thinks through this before touching any API.

**18 source clusters, each labeled by access type:**

- 🟢 **FREE** — curl directly, zero key, zero setup
- 🔑 **KEY** — free API key required
- 📦 **MCP** — MCP server must be installed
- 💰 **PAID** — has quota or credits that may cost money
- 🔧 **CLI** — needs a CLI tool installed

Sources are grouped and presented by the *reason* they were selected. So instead of a flat list of 40 tools, you see something like:

```
Does this already exist?
  ✅ Code & Libraries — GitHub repos, npm/PyPI packages
  ✅ Package Registries — all free, no setup needed
  ⚠️ Competitive Intelligence — idea-reality-mcp not installed
     → Install: uvx idea-reality-mcp (30 seconds)
     → Or skip — I'll use Web Search + GitHub instead

What are people saying?
  ✅ Social Platforms — Reddit, Bluesky, StackExchange (all free)
  ⚠️ Twitter — MCP installed but reads cost $0.01 each

Is this space growing?
  ✅ News & Events — GDELT + newsmcp
  ⚠️ Trends — trendsmcp not installed

Maybe related (want me to include these?):
  ❓ Academic Papers — might be research on browser automation
  ❓ Patent & IP — someone might have patented this

Skipping (clearly not relevant):
  ⬚ Biomedical
  ⬚ Government & Economic

Options:
  (a) Go with everything (install missing tools first)
  (b) Just use what's ready now — zero setup friction
  (c) Let me adjust
```

Option (b) is designed for users who want results immediately. The engine degrades gracefully: uses every 🟢 FREE curl API plus already-installed MCPs, skips anything that needs setup, and notes in the final report what coverage was skipped.

## Pre-flight Check

Before presenting the source list, the skill silently verifies:
- Whether each MCP server responds
- Whether required API keys are set
- Whether CLI tools are installed

You're never silently missing coverage. If something isn't set up, you see exactly what's missing and a one-line install command.

## Model Selection

The skill tells you exactly which models it's using and why:

- **Sonnet** — all search/collect/extract agents. Can use every tool, costs 5x less than Opus.
- **Haiku** — simple single-source lookups. Costs 25x less than Opus. Used when an agent only needs 1-2 tools.
- **Opus** — synthesis only, in the main thread. Never used for collection. Synthesis is the part where quality actually matters.

After source selection is confirmed, you choose the collection model (recommended: Sonnet) before any agents launch.

## What Makes This Different

**vs Google Search**: Google indexes web pages. We query 100+ specialized databases directly. Patent filings, academic citations, package download trends, prediction market odds, SEC company filings, government economic data — none of this shows up on page 1 of Google.

**vs ChatGPT / Claude / Gemini "deep research"**: They do 5-10 web searches and synthesize. We do 100+ parallel queries across specialized APIs, verify coverage and flag contradictions before synthesizing, and score output quality explicitly. Their citation accuracy is 40-80% (DeepTRACE, NeurIPS 2025). The verification step exists specifically to catch that.

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
