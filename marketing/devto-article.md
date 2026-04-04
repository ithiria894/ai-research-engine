---
title: "AI Research Engine: 100+ Free APIs, 18 Source Clusters, Zero Google Required"
published: false
tags: [mcp, ai, opensource, showdev]
canonical_url: https://github.com/ithiria894/ai-research-engine
series: "MCP Tools I Built"
---

I asked Claude to research whether anyone had built an MCP server for browser automation. It did three web searches, came back confident, said the space was "relatively sparse." I shipped a version. Two weeks later I found four existing tools — two with 500+ stars — that did the same thing. One was literally on the front page of HN the week before I started building.

Claude wasn't lying. It checked what it could check. The problem is what "researching" actually means when the only tool is web search.

So I spent a weekend auditing where research data actually lives. Academic papers with 250M+ entries. 140M+ patent filings. npm/PyPI/crates.io download trends. SEC company filings. FRED's 840K economic time series. Prediction markets. Podcast databases with 190M+ episodes. Reddit, Hacker News, Bluesky, 170 StackExchange sites. Nearly all of it is free, has a working API, and returns better signal than a Google search. And almost nobody queries more than 2-3 of these at once.

That's the problem I built this to fix.

## When AI "researches" for you, it's using a flashlight in an ocean

Google indexes web pages. That's what it's for. It doesn't index arXiv preprints, USPTO patent applications, PyPI download stats, Polymarket odds, or SEC EDGAR filings. When Claude or ChatGPT does "deep research," it's running 5-10 web searches in a row and synthesizing the results. Useful. Not comprehensive.

There's a 2025 NeurIPS paper called DeepTRACE that measured citation accuracy across AI research tools. Range: 40-80%. Meaning up to 60% of the citations in an AI-generated research report are wrong, incomplete, or hallucinated. The tools are great at *sounding* thorough. They're not great at being thorough.

The real data lives in 100+ specialized databases. Most are free. None of them are on page 1 of Google.

## "Just ask AI to search the web"

Yes, you can. It helps. I'm not pretending web search is useless.

But web search has hard limits. It doesn't reach into package registries to tell you a competing library has 2M weekly downloads. It doesn't pull from Polymarket to check what the prediction market thinks about a regulatory outcome. It doesn't cross-reference patent filings to tell you someone already IP-protected the exact mechanism you're designing around.

You can ask Claude to search harder. It will search harder — through the same 10-20 indexed web pages. The databases just aren't there.

## What this is

An open-source data source inventory and multi-agent methodology. Two pieces:

**`research-engine.md`** — a complete reference for 100+ free APIs. Every entry has a curl example you can run right now, rate limits, and auth requirements. No AI required. Just a list of sources that exist, that are free, that most people don't know about.

**`skills/deep-research/`** — a Claude Code skill that turns the inventory into a multi-agent workflow. Copy it to `~/.claude/skills/deep-research/` and invoke with `/deep-research "your question"`.

The workflow is the interesting part.

## Step 0: the pharmacist picks your medicines

Before a single agent launches, the skill reasons about your specific question and selects which of 18 source clusters would actually contain relevant data.

"Has anyone built X?" has different source needs than "What's the economic impact of Y?" The skill thinks through this before touching any API, then shows you its reasoning:

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

Before presenting this, the skill silently checks whether each MCP server actually responds, whether API keys are set, and whether CLI tools are installed. You see exactly what's missing with a one-line install command. You're never silently missing coverage without knowing it.

Option (b) is for when you want results immediately. The engine runs every free curl API plus already-installed MCPs, skips anything needing setup, and notes in the final report what was skipped. **The AI picks sources like a pharmacist, not like someone who knocked over the whole shelf.**

## 18 source clusters

Each labeled by access type: 🟢 FREE (curl directly, zero setup) / 🔑 KEY (free API key required) / 📦 MCP (server must be installed) / 💰 PAID

| Cluster | What's in it |
|---------|-------------|
| Web Search | Tavily, Exa, Firecrawl, SearXNG, DuckDuckGo, Bing, Brave |
| Academic Papers 🟢 | Semantic Scholar, OpenAlex, arXiv, PubMed, Crossref — 250M+ papers |
| Citations & Impact 🟢 | OpenCitations, NIH iCite, ORCID, Altmetric |
| Patents 🟢 | USPTO PatentsView, EPO OPS, Lens.org — 140M+ patents |
| Social & Community 🟢 | Reddit, Bluesky, Mastodon, HN, StackExchange (170+ sites), Discourse |
| Package Registries 🟢 | npm, PyPI, crates.io, RubyGems, NuGet, Docker Hub, HuggingFace |
| Company & Startup 🟢 | SEC EDGAR, YC OSS API, Finnhub, OpenCorporates |
| Government & Economic 🔑 | FRED (840K time series), BLS, Census, Congress.gov, World Bank, IMF |
| News & Media 🟢 | GDELT, NewsAPI, NYTimes, RSS feeds |
| Podcasts 🔑 | PodcastIndex, Apple Podcasts — 190M+ episodes |
| Trends & Predictions 📦 | Google Trends, Polymarket, TikTok, YouTube |
| SEO & Web 🟢 | Open PageRank, crt.sh, Wayback CDX, Common Crawl, Cloudflare Radar |
| Knowledge Graph 🟢 | Wikidata SPARQL, Wikipedia API |
| Books & Archive 🟢 | Open Library, Internet Archive |
| AI Brand Visibility 📦 | Aperture, AICW, Citatra |
| Code & Libraries 📦 | GitHub, code search |
| Competitive Intel 📦 | idea-reality-mcp |
| Biomedical 🟢 | openFDA, PubChem, ClinicalTrials.gov |

Most of these are 🟢. Zero API key. Zero signup. Run the curl, get data.

## After the agents return: verification

Once Sonnet agents come back with raw findings, a verification agent audits the whole result set before synthesis:

- Coverage score 1-5
- Contradictions between sources flagged explicitly
- Missing topics identified
- If score < 3, follow-up agents launch automatically

This step exists specifically because of the DeepTRACE number. Synthesizing before checking coverage gives you a confident-sounding report that quietly missed half the picture. **Contradictions get flagged, never silently merged.**

Synthesis is done by Opus in the main thread. Opus never gets used for data collection — that's Sonnet's job, at 5x lower cost. Right model for each step.

## What makes this different

**vs Google**: Indexes web pages. We query 100+ specialized databases directly. Patent filings, academic citations, package download trends, prediction market odds — none of this shows up on page 1.

**vs ChatGPT / Claude deep research**: 5-10 web searches, 40-80% citation accuracy (DeepTRACE, NeurIPS 2025). We run 100+ parallel queries across specialized APIs, verify coverage, and flag contradictions before synthesizing.

**vs awesome-mcp-servers**: Lists server names. We list every source with curl examples, rate limits, auth requirements, and a methodology for using them together.

The inventory (`research-engine.md`) is also just a standalone reference. You don't need the multi-agent workflow to use it. Every API has a working curl example you can run right now:

```bash
# Search 250M+ academic papers
curl "https://api.openalex.org/works?search=large+language+models&sort=publication_date:desc"

# Check prediction market odds
curl "https://gamma-api.polymarket.com/markets?tag=ai&closed=false"

# Search US patents
curl "https://search.patentsview.org/api/v1/patent/?q=machine+learning"

# Python package download trends
curl "https://pypistats.org/api/packages/langchain/recent"
```

## About me

I'm a CS dropout, been working as a backend engineer for about a year, been using Claude Code for a few months. She/her. I built this because I kept making product decisions based on research that felt thorough but wasn't — then finding competitors or prior art after I'd already built something.

The immediate trigger was applying for Anthropic's fellowship. I needed the research to actually hold up, not just feel complete. So I went back and rebuilt the methodology from scratch, sourced every database I could find, and turned it into a reusable skill.

The inventory is the part I think is most broadly useful. Even if you never use the multi-agent workflow, having a single file with 100+ free research APIs and working curl examples is just a good thing to have.

## Try it

```bash
# Use the inventory directly — curl examples for everything
# https://github.com/ithiria894/ai-research-engine/blob/main/research-engine.md

# Use as a Claude Code skill
cp -r skills/deep-research/ ~/.claude/skills/deep-research/
# Then: /deep-research "your question"
```

{% github ithiria894/ai-research-engine %}

If you know a free research API that isn't in the list, open an issue. The bar is: free or meaningful free tier, working API, and you include name, URL, what it provides, and rate limits. That's it.

**The data was always there. It just needed someone to write down where it lives.**
