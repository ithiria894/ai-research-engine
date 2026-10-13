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
- **An LLM-led source-hypothesis step** that reads the whole question and selects every plausible direct, adjacent, and exploratory source across overlapping clusters
- **A community capability registry** that records what niche communities contain, how to search them, whether a session is needed, and which access routes have actually been verified
- **An optional multi-agent methodology** for parallel collection when the user requests delegation; the same workflow also runs in one main agent
- **A manual maintenance and diagnostic health check** with quick, targeted-source, community and full-inventory modes
- **A verification step** that checks coverage, flags contradictions, and identifies gaps before producing the final report
- **A quality framework** (DRACO dimensions) that scores output on factual accuracy, analytical depth, presentation, and source attribution

## Coverage

| Category | Sources | Examples |
|----------|---------|----------|
| **Web Search** | 10+ engines | Tavily, Exa, Firecrawl, SearXNG, DuckDuckGo, Bing, Brave, Google |
| **Academic Papers** | 250M+ papers | Semantic Scholar, OpenAlex, arXiv, PubMed, Crossref, CORE, DBLP, DOAJ, Zenodo |
| **Citations & Impact** | 6 APIs | OpenCitations, NIH iCite (RCR metric), ORCID, ROR, Altmetric, OpenAIRE |
| **Patents** | 140M+ patents | USPTO PatentsView, EPO OPS, Lens.org, Google Patents BigQuery |
| **Admissions & Education** | Official + community evidence | Program/admissions/faculty/registrar/financial-aid pages, Common Data Set, institutional research, FOI/ATI, Wayback, 1Point3Acres, Reddit, College Confidential, The Student Room, school communities |
| **Social & Community** | 25+ platforms | Reddit, 1Point3Acres, Grapevine, Blind India, TakeUForward, RedBus2US, Yocket, Indian Reddit communities, X/Twitter, Bluesky, Mastodon, HN, Lobste.rs, Discourse, Discord, Telegram, Slack, StackExchange (170+ sites), Hashnode, DEV.to, Lemmy |
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

```text
Question
  → LLM proposes every website/source that may contain useful or unexpected information
  → Nicole adds or removes sources
  → Engine loads each source's access recipe and credential reference
  → Log in when needed and search through the source's first-party API
  → Return the evidence plus a ledger of sources used, unused, empty, or failed
```

That is the complete core loop. `community-sources.json` is a phonebook, not a
classifier. It remembers what each source contains and how to access it. The LLM may
select sources across any number of topics and may add a source that is not yet in the
phonebook. A bounded browser-page route is a fallback only when no usable API exists.

## Source Selection — LLM reads the phonebook

The skill does not assign a query to one rigid category. The LLM reads the question,
checks the phonebook, and proposes every source that may have relevant or surprising
information. Nicole can add or remove sources before the API searches begin.

The question "Has anyone built an MCP server for browser recording?" has very different source needs than "What's the economic impact of AI regulation?" The skill thinks through this before touching any API.

**20+ source clusters, each labeled by access type:**

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

## Health Check

Health checking is never a gate before an ordinary research question. Do not run it or
consult an old report before deciding whether to search a selected source. The actual
retrieval is the current operational signal:

- Relevant data returned → `MATERIAL`
- Successful response with no relevant result → `EMPTY`
- Endpoint, authentication or parser failure → `FAILED`; report it, set the source
  aside for this question, and continue

Use external-source health probes only in a later batched maintenance pass:
- Whether the local registry, CLI and Agent Chrome transport work
- Whether each selected community adapter returns real data
- Whether credentials or a logged-in session are required
- Whether a selected endpoint is healthy, empty, skipped or failed

Quick mode is a local regression check after engine changes; it does not probe the
broad/keyed source inventory. During periodic maintenance, use `--source` to
reproduce failures collected in the ledger, `--community` for a community audit, and
`--full` for an explicit broad audit. Do not interrupt the live research run to diagnose
or repair a failed source. This keeps ordinary research fast and prevents routine work
from spending limited credits. If a selected route is unavailable, the coverage ledger
says so instead of treating its silence as evidence.

## Execution Model

Source quality and retrieval coverage do not depend on a fixed model name. The main
agent can execute the complete workflow itself. When the user explicitly asks for
delegation, independent source lanes can run in parallel and the main thread retains
integration, contradiction checking, and final synthesis.

## What Makes This Different

**vs Google Search**: Google indexes web pages. We query 100+ specialized databases directly. Patent filings, academic citations, package download trends, prediction market odds, SEC company filings, government economic data — none of this shows up on page 1 of Google.

**vs ChatGPT / Claude / Gemini "deep research"**: They often stop after a small set of web searches. We select every plausibly relevant specialized source, verify actual retrieval coverage, flag contradictions before synthesizing, and score output quality explicitly. The engine does not query all 100+ sources blindly; the inventory is a phonebook and the question determines which routes are used.

**vs last30days**: Great tool for social recency (Reddit/X/TikTok/Instagram in the last 30 days). We cover that plus academic papers, patents, government data, package registries, company filings, podcasts, prediction markets, and 80+ more sources with no time restriction.

**vs awesome-mcp-servers**: Lists MCP servers by name. We list every data source with curl examples, exact rate limits, auth requirements, and a methodology for using them together.

**vs public-apis**: Lists 1400+ APIs. We curate the ones that matter for research, show how to use them with AI agents, and provide a workflow that ties them together.

## Files

```
research-engine.md                          # Master inventory and research methodology
community-sources.json                      # Machine-readable community capability registry
social-research.py                          # Verified one-shot community/API adapters
health-check.sh                             # Manual maintenance and route diagnostics
qa/                                         # End-to-end QA scripts
skills/deep-research/
  SKILL.md                                  # LLM-led workflow and report contract
  references/community-source-discovery.md  # Discovery, access, onboarding, and registry rules
```

## Quick Start

### Check the engine and selected source routes

```bash
# Fast local check: registry, CLIs and Agent Chrome transport. No broad API sweep.
bash health-check.sh

# During a later maintenance pass, reproduce failures collected in the ledger.
bash health-check.sh --source reddit --source onepoint3acres

# Periodic community-route audit (no keyed or broad API inventory).
bash health-check.sh --community

# Explicit comprehensive maintenance audit. This can consume limited API/MCP quota.
bash health-check.sh --full
```

The report is written atomically to `health-check-report.md`. If a run is interrupted,
the report is replaced with an explicit `INTERRUPTED / FAILED` marker instead of
leaving an older success result in place. `--full` runs independent zero-key probes in
a bounded parallel pool. Ordinary research does not run a health check automatically.

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
