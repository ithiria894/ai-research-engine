# AI Research Engine

A source inventory and workflow for AI agents doing research. Every source is reached through its official REST API, a one-shot CLI, or a logged-in browser session. No MCP servers.

On 2026-10-30 the full health check probed 75 zero-key APIs (68 working, 1 suspect, 6 dead), 12 keyed APIs, Tavily, Exa, Firecrawl and 12 community routes. The numbers in this README come from that run, not from vendor pages.

## The problem

When you ask an AI to research something, it usually does one of three things:

1. Answers from training data. Outdated, and it won't tell you what it doesn't know.
2. Runs a handful of web searches. Web search barely touches academic citations, patent filings, package download stats, prediction markets, SEC filings or most forum threads.
3. Reports "nothing found" when the tool it called was broken. That one is the worst, because it looks like an answer.

Most of the useful data sits in specialized databases and community sites. Many are free. Agents rarely use more than two or three of them, and when one fails they rarely say so.

## What this is

- **An inventory** (`research-engine.md`) of free and free-tier sources with a curl or CLI recipe, auth requirement and last verified date for each.
- **A community phonebook** (`community-sources.json`) recording what each forum contains, how to search it, and whether it needs a login.
- **Adapters** (`social-research.py`) for sources that need more than one curl: Reddit search, Xiaohongshu, 1Point3Acres, Grapevine, College Confidential, The Student Room, BC Transfer Guide, ScrapeCreators and TikHub.
- **A health check** (`health-check.sh`) for batched maintenance, plus end-to-end QA scripts in `qa/`.
- **A coverage ledger** that every research run must output: which sources returned data, which were empty, which failed, which were skipped. A failed tool is never reported as "no results".

## Coverage

| Category | Sources (verified routes) |
|----------|---------------------------|
| Web search | Tavily, Exa, Firecrawl (all free tiers, keyed), Bing RSS (zero key, weak for CJK), host-native search in Claude/Codex |
| Page extraction | r.jina.ai (zero key), Tavily extract, Exa contents, Firecrawl scrape |
| Academic | OpenAlex, Semantic Scholar (429 rate limits without a key), arXiv, Crossref, DBLP, DOAJ, Zenodo, PubMed, Europe PMC, bioRxiv, OpenCitations, NIH iCite, ORCID, ROR |
| Reddit | Logged-in browser session (`reddit-search`) for live search and full comment trees, Arctic Shift for archive search |
| Other forums | Hacker News (Algolia), Lobste.rs, StackExchange, any Discourse forum, Lemmy, Bluesky, Mastodon tag timelines, DEV.to, V2EX, PTT, Weibo (browser), 1Point3Acres, Grapevine, College Confidential, The Student Room |
| Korean | Naver official Search API (blog, cafe, kin, local, datalab) |
| Chinese | Bilibili, V2EX, Weibo, Xiaohongshu (browser session or TikHub), 1Point3Acres |
| X / Twitter | Search, threads and timelines through the official `@steipete/bird` CLI with a logged-in account's session cookies; FxTwitter for single tweets with no account |
| Video | yt-dlp subtitles; Groq transcription when there are none |
| Legal | CanLII (keyed), Federal Register |
| Government & economic | FRED, Census, Congress.gov, govinfo, OpenFEC, OpenStates, World Bank, openFDA, USASpending, SEC EDGAR |
| Packages & code | npm, PyPI, crates.io, Packagist, RubyGems, Homebrew, Docker Hub, Hugging Face, libraries.io, OSV, GitHub API, context7 docs |
| Markets | Polymarket, CoinGecko, DeFiLlama, DexScreener, FMP, Twelve Data, Alpha Vantage |
| Reference | Wikipedia, Wikidata SPARQL, Open Library, Internet Archive, Wayback |
| Self-hosted (on demand) | SearXNG metasearch (252 engines), RSSHub (1,995 site namespaces), MediaCrawler (Xiaohongshu, Douyin, Kuaishou, Bilibili, Weibo, Tieba, Zhihu; needs a login per platform). Started per query by `tools/*.sh`, stopped after |

Known gaps as of 2026-10-30: Serper's one-time trial is used up, SerpAPI has no key, DuckDuckGo and Startpage HTML return bot challenges from this machine, and Zhihu and Xiaohongshu need accounts. Finnhub rejects our key even from a logged-in browser, CourtListener needs an account that is stuck at an hCaptcha, and WHO GHO (HTTP 500) and Marginalia (no response) failed their probes. OpenReview now goes through Agent Chrome, Open PageRank uses its new Keywords Everywhere endpoint, and OpenSanctions is searched from its free bulk data on this machine (`tools/opensanctions.py`).

## How it works

```text
Question
  → LLM proposes every source that may hold useful or surprising information
  → Nicole adds or removes sources
  → Load each source's access recipe and credential reference
  → Search through the source's own API (browser session only when it has none)
  → Return the evidence plus a ledger: used, empty, failed, skipped
```

`community-sources.json` is a phonebook, not a classifier. It remembers what a source holds and how to reach it. The LLM can pick sources across any number of topics and add sources that aren't in the phonebook yet.

## Why no MCP

Every research MCP we had was a thin wrapper around a public API. Wrappers broke in ways that were hard to see: an MCP configured for one project directory was missing in another, a removed server left the skill calling tools that no longer existed, and agents treated the silence as "no data". A direct curl or CLI call works from any directory, in any agent, with nothing running in the background.

Keys live in gopass. `~/.config/research-engine/keys.env` is the copy that scripts read.

## Reddit notes

- `/search.json` returns 403 ("blocked by network security") even inside a logged-in browser session since 2026-10-30. Comment-tree `.json` still works.
- `social-research.py reddit-search` uses the search page that Reddit's own web UI loads, with cursor paging for posts and comments.
- Reddit's search is semantic and cross-language. A query with no literal match still returns "related" posts, and a Chinese query returns English posts. Each result carries `query_terms_in_text`, and a run with zero literal matches reports `status: no_lexical_match` instead of `ok`.
- New Reddit Data API apps are only approved for moderation use cases (see reddit.com/wiki/api), so research stays on the browser session.

## Research run

Every research job gets a run folder (default `~/MyGithub/research-runs/`, outside this repo):

```bash
RUN=$(python3 research_run.py init my-topic --query "the exact question")
curl -s "https://hn.algolia.com/api/v1/search?query=x" | python3 research_run.py add "$RUN" --source hn --ext json
python3 research_run.py ledger "$RUN" --source hn --status MATERIAL --items 3 --evidence 0001
python3 research_run.py check "$RUN"   # fails on missing perspectives, adversarial search, a quote not found verbatim, or an untraced number
python3 library.py index               # make the run searchable next time
```

Ideas taken from last30days (failure reasons), hyperresearch (quote integrity, untrusted fencing, overturn sources,
scholarly-first, syndication dedupe) and STORM (perspectives). Details: `docs/research-workflow-spec.md`.

## Health check

Research runs don't wait for a health check. The retrieval itself is the signal: data back means `MATERIAL`, a clean empty response means `EMPTY`, an error means `FAILED`. Failures go into the ledger and get fixed in a later maintenance pass.

```bash
bash health-check.sh                 # local regression: registry, CLIs, browser transport
bash health-check.sh --source reddit # reproduce one failed source
bash health-check.sh --community     # every community route, no keyed APIs
bash health-check.sh --full          # everything, including keyed APIs (uses free-tier quota)
```

QA suites:

```bash
bash qa/agent-chrome-qa.sh       # browser transport, Reddit search, XHS failure paths, full-URL tabs (20 checks)
bash qa/community-sources-qa.sh  # phonebook and community adapters (13 checks)
bash qa/health-check-qa.sh       # health-check behaviour (14 checks)
bash qa/research-run-qa.sh       # run folder, ledger, quote and number integrity, gates (45 checks)
bash qa/scholar-qa.sh            # merged scholarly search, retractions, full text (11 checks)
bash qa/library-qa.sh            # past-run search in English, Chinese, Korean (13 checks)
bash qa/failure-reasons-qa.sh    # every adapter failure names a ledger reason (5 checks)
bash qa/opensanctions-qa.sh      # local sanctions/PEP lookup, checksum and schema-drift guards (11 checks)
```

## Files

```
research-engine.md          Master inventory, routing notes, sharpening log
community-sources.json      Community phonebook
social-research.py          One-shot adapters (no MCP, no cookie export)
research_run.py             Run folder: verbatim query, raw evidence, ledger, quote/adversarial gates
scholar.py                  Scholarly search across 5 sources, merged by DOI, with retraction flags
library.py                  Full-text search over past runs (SQLite FTS5, rebuildable)
docs/                       research-workflow-spec.md: the rules the tools and skill enforce
health-check.sh             Maintenance probes; writes health-check-report.md
tools/                      On-demand launchers (searxng.sh, rsshub.sh, mediacrawler.sh) and opensanctions.py (local bulk lookup)
qa/                         End-to-end QA scripts
source-scans/               Reproducible prior-art and source sweeps
skills/deep-research/       The skill itself (single source of truth)
```

This repo is the only copy of the skill. Install it with a symlink so edits land here:

```bash
ln -s ~/MyGithub/ai-research-engine/skills/deep-research ~/.claude/skills/deep-research
ln -s ~/.claude/skills/deep-research ~/.codex/skills/deep-research   # Codex follows the same file
```

Personal context the skill may need lives in `~/.config/research-engine/private-context.md`, outside any repo.

## Quick start

```bash
# Academic papers
curl "https://api.openalex.org/works?search=large+language+models&sort=publication_date:desc"

# Prediction markets
curl "https://gamma-api.polymarket.com/markets?tag=ai&closed=false"

# A single tweet, no key
curl "https://api.fxtwitter.com/AnthropicAI/status/1925591505332576377"

# Reddit posts or comments (needs the logged-in agent Chrome)
python3 social-research.py reddit-search "quantization" --subreddit LocalLLaMA --limit 25
python3 social-research.py reddit-search "quantization" --subreddit LocalLLaMA --type comments
```

## Contributing

Found a free source we're missing? Open an issue or PR with the name, URL, what data it returns, rate limits, auth requirements and a curl you ran yourself.

## License

MIT
