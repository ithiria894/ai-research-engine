#!/usr/bin/env bash
# Research Engine Health Check
# Tests every zero-key free API, CLI, and detects connected MCP servers.
# Writes a timestamped report so research agents skip dead tools instead of
# silently fetching nothing.
#
# Usage: bash health-check.sh
# Output: health-check-report.md (in this dir)

set -uo pipefail
REPORT="$(dirname "$0")/health-check-report.md"
TIMEOUT=25          # per-try ceiling; crt.sh / S2 are slow, give them room
CONNECT_TIMEOUT=10
PASS=0; FAIL=0; WARN=0
CLAUDE_CFG="$HOME/.claude.json"

# Each test: name | method | url | extra-curl-args | expect-substring (optional)
# We check HTTP 2xx AND a non-empty plausible body.
results=()

check() {
  local name="$1" url="$2"; shift 2
  local extra=("$@")
  local code size tmp
  # ONE curl per endpoint (body to tmp, code via -w). Doing two separate curls
  # would double-hit rate-limited APIs (e.g. GDELT 1req/5s) and falsely fail them.
  tmp=$(mktemp)
  # --retry 3 + --retry-all-errors so transient 429 / 5xx / 000-timeout (DOAJ,
  # crt.sh, Semantic Scholar, PyPI) get re-attempted instead of falsely reported
  # dead. curl retries on a fresh transfer each time, with exponential-ish backoff.
  code=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" \
    --retry 3 --retry-delay 2 --retry-all-errors --retry-connrefused \
    -A "ResearchEngineHealthCheck/1.0" "${extra[@]}" -o "$tmp" -w "%{http_code}" "$url" 2>/dev/null)
  size=$(wc -c < "$tmp" 2>/dev/null || echo 0)
  rm -f "$tmp"
  if [[ "$code" =~ ^2 ]] && [[ "$size" -gt 2 ]]; then
    results+=("✅ | $name | $code | OK")
    ((PASS++))
  elif [[ "$code" =~ ^2 ]]; then
    results+=("⚠️ | $name | $code | 2xx but EMPTY body")
    ((WARN++))
  elif [[ "$code" == "429" ]]; then
    results+=("⚠️ | $name | 429 | rate-limited (TRANSIENT — retry with spacing, not dead)")
    ((WARN++))
  else
    results+=("❌ | $name | ${code:-000} | dead/blocked/changed")
    ((FAIL++))
  fi
  sleep 0.3  # gentle spacing so shared-IP rate limits (GDELT/S2) don't cascade
}

echo "Running research engine health check..."

# ── Zero-key free APIs (the bulk agents rely on) ──────────────────────
check "HN Algolia (search)"     "https://hn.algolia.com/api/v1/search?query=ai&tags=story"
check "HN Firebase (topstories)" "https://hacker-news.firebaseio.com/v0/topstories.json"
check "Lobste.rs JSON"          "https://lobste.rs/hottest.json"
check "Bluesky searchPosts"     "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=ai&limit=5"
check "Mastodon trends"         "https://mastodon.social/api/v1/trends/statuses"
check "Lemmy search"            "https://lemmy.world/api/v3/search?q=ai&type_=Posts&limit=5"
check "DEV.to articles"         "https://dev.to/api/articles?tag=ai&per_page=5"
# Reddit .json is IP-blocked from server/datacenter IPs (403) — NOT tested here.
#   Reddit research MUST go through dialog-mcp (reddit-research) or the logged-in
#   Chrome session. See the deep-research skill's Forum Deep Dive HARD RULE.
check "StackExchange search"    "https://api.stackexchange.com/2.3/search?intitle=ai&site=stackoverflow"
check "GDELT doc"               "https://api.gdeltproject.org/api/v2/doc/doc?query=ai&mode=ArtList&format=json&maxrecords=5"
check "OpenAlex works"          "https://api.openalex.org/works?search=ai&per-page=3"
check "Semantic Scholar"        "https://api.semanticscholar.org/graph/v1/paper/search?query=ai&fields=title&limit=3"
check "arXiv API"               "https://export.arxiv.org/api/query?search_query=cat:cs.AI&max_results=3"
check "Crossref"                "https://api.crossref.org/works?query=ai&rows=3"
check "DBLP"                     "https://dblp.org/search/publ/api?q=ai&format=json&h=3"
check "DOAJ"                     "https://doaj.org/api/search/articles/ai"
check "Zenodo"                  "https://zenodo.org/api/records?q=ai&size=3"
check "PubMed esearch"          "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=ai&retmax=3"
check "Europe PMC"              "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=ai&format=json&pageSize=3"
check "bioRxiv details"         "https://api.biorxiv.org/details/biorxiv/2026-01-01/2026-01-07/0/json"
check "OpenCitations"           "https://api.opencitations.net/index/v2/citations/doi:10.1371/journal.pbio.1002541"
check "NIH iCite"               "https://icite.od.nih.gov/api/pubs?pmids=28882288&fields=relative_citation_ratio"
check "ORCID"                   "https://pub.orcid.org/v3.0/0000-0001-5109-3700/works" -H "Accept: application/json"
check "ROR"                     "https://api.ror.org/v2/organizations?query=MIT"
check "Polymarket Gamma"        "https://gamma-api.polymarket.com/markets?closed=false&limit=3"
check "npm downloads"           "https://api.npmjs.org/downloads/range/last-month/react"
check "PyPI Stats"              "https://pypistats.org/api/packages/requests/recent"
check "crates.io"              "https://crates.io/api/v1/crates/serde/downloads"
check "Packagist"               "https://packagist.org/packages/monolog/monolog.json"
check "RubyGems"                "https://rubygems.org/api/v1/gems/rails.json"
check "Homebrew Analytics"      "https://formulae.brew.sh/api/formula/wget.json"
check "Docker Hub"              "https://hub.docker.com/v2/repositories/library/nginx"
check "HuggingFace Hub"         "https://huggingface.co/api/models?sort=downloads&direction=-1&limit=3"
check "OSV.dev query"           "https://api.osv.dev/v1/query" -X POST -d '{"package":{"name":"lodash","ecosystem":"npm"}}'
check "Federal Register"        "https://www.federalregister.gov/api/v1/documents.json?per_page=3"
check "World Bank"              "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json&per_page=3"
check "openFDA"                 "https://api.fda.gov/drug/event.json?limit=3"
check "USASpending"             "https://api.usaspending.gov/api/v2/references/toptier_agencies/"
check "SEC EDGAR"               "https://data.sec.gov/submissions/CIK0000320193.json" -H "User-Agent: ResearchEngine health@example.com"
check "YC OSS API"              "https://raw.githubusercontent.com/yc-oss/api/main/companies/all.json"
check "crt.sh"                  "https://crt.sh/?q=crt.sh&output=json&deduplicate=y"
check "Tranco"                  "https://tranco-list.eu/api/ranks/domain/google.com"
check "Wikipedia API"           "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=ai&format=json"
check "Wikidata SPARQL"         "https://query.wikidata.org/sparql?query=SELECT%20%3Fitem%20WHERE%7B%3Fitem%20wdt%3AP31%20wd%3AQ146%7DLIMIT%201&format=json"
check "Open Library"            "https://openlibrary.org/search.json?q=artificial+intelligence&limit=3"
check "Internet Archive"        "https://archive.org/advancedsearch.php?q=ai&rows=3&output=json"
# Google PageSpeed now needs an API key (keyless quota = 0 → 429). Not a zero-key test.
#   Set PAGESPEED_API_KEY and append &key=$PAGESPEED_API_KEY to use it.
check "DeFiLlama protocols"     "https://api.llama.fi/protocols"
check "CoinGecko markets"       "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&per_page=3"
check "DexScreener search"      "https://api.dexscreener.com/latest/dex/search?q=SOL"
check "AI Funding API"          "https://aifunding.me/api/v1/rounds?limit=5"
# Hashnode GraphQL moved to a PAID tier (2026-05-13) — no free endpoint. Removed.
#   Needs a Hashnode PAT: -H "Authorization: Bearer $HASHNODE_PAT".

# ── llms.txt / GEO ecosystem (Round 11) ───────────────────────────────
check "llmstxt.site directory"  "https://directory.llmstxt.cloud/"
check "Context7 (reachable)"    "https://context7.com/"
check "GitMCP (reachable)"      "https://gitmcp.io/"
# Perplexity / OpenAI / Anthropic probing = key-based APIs, not zero-key. Not tested here.
#   Use Sonar (api.perplexity.ai) with PERPLEXITY_API_KEY for AI-answer probing.

# ── GEO skills-marketplace APIs (Round 12, verified 2026-05-31) ────────
check "skills.sh search"        "https://www.skills.sh/api/search?q=geo"
check "agentskills.to list"     "https://www.agentskills.to/api/skills?q=seo"
check "skilldock.io skills"     "https://api.skilldock.io/v1/skills"
check "Otterly OpenAPI spec"    "https://data.otterly.ai/v1/openapi.json"

# ── MCP liveness probe (Round 12) ─────────────────────────────────────
# CONNECTED ≠ WORKING. A configured MCP can be quota-dead. We hit each keyed
# service's REST endpoint with the REAL key (read from ~/.claude.json) so the
# report shows ACTUAL usability, not just "listed in config".
#   ⚠️ tavily/exa probes spend ~1 search credit each when quota IS available
#      (free when already exhausted). Worth it: accurate > free (engine philosophy).
#   OAuth MCPs (dialog-mcp) can't be auth'd from bash — only Claude's stored
#   token works; we report reachability + tell the agent to confirm in-session.
mcp_results=()
if [[ -f "$CLAUDE_CFG" ]]; then
  TKEY=$(jq -r '.mcpServers.tavily.url // ""' "$CLAUDE_CFG" | grep -oP 'tavilyApiKey=\K[^&"]+' || true)
  if [[ -n "${TKEY:-}" ]]; then
    c=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" -o /dev/null -w "%{http_code}" \
      -X POST "https://api.tavily.com/search" -H "Authorization: Bearer $TKEY" \
      -H "Content-Type: application/json" -d '{"query":"healthcheck","max_results":1}')
    case "$c" in
      2*)  mcp_results+=("✅ | tavily | $c | search OK — quota available");;
      432) mcp_results+=("❌ | tavily | 432 | QUOTA EXCEEDED — connected but search DEAD");;
      4*)  mcp_results+=("⚠️ | tavily | $c | reachable, auth/plan issue");;
      *)   mcp_results+=("❌ | tavily | ${c:-000} | unreachable");;
    esac
  else mcp_results+=("⚠️ | tavily | — | not configured / no key in ~/.claude.json"); fi

  EKEY=$(jq -r '.mcpServers.exa.url // ""' "$CLAUDE_CFG" | grep -oP 'exaApiKey=\K[^&"]+' || true)
  if [[ -n "${EKEY:-}" ]]; then
    c=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" -o /dev/null -w "%{http_code}" \
      -X POST "https://api.exa.ai/search" -H "x-api-key: $EKEY" \
      -H "Content-Type: application/json" -d '{"query":"healthcheck","numResults":1}')
    case "$c" in
      2*)  mcp_results+=("✅ | exa | $c | search OK — credits available");;
      402) mcp_results+=("❌ | exa | 402 | CREDITS EXCEEDED — connected but search DEAD");;
      4*)  mcp_results+=("⚠️ | exa | $c | reachable, auth/plan issue");;
      *)   mcp_results+=("❌ | exa | ${c:-000} | unreachable");;
    esac
  else mcp_results+=("⚠️ | exa | — | not configured / no key in ~/.claude.json"); fi

  FKEY=$(jq -r '.mcpServers.firecrawl.env.FIRECRAWL_API_KEY // ""' "$CLAUDE_CFG")
  if [[ -n "${FKEY:-}" ]]; then
    body=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" \
      "https://api.firecrawl.dev/v1/team/credit-usage" -H "Authorization: Bearer $FKEY")
    rem=$(echo "$body" | jq -r '.data.remaining_credits // empty' 2>/dev/null)
    if [[ -n "$rem" ]]; then mcp_results+=("✅ | firecrawl | 200 | $rem credits remaining");
    else mcp_results+=("❌ | firecrawl | — | credit-usage probe failed (key dead?)"); fi
  else mcp_results+=("⚠️ | firecrawl | — | no FIRECRAWL_API_KEY in config"); fi

  # dialog-mcp: OAuth remote MCP — bash can't present Claude's token. initialize
  # without auth returns 401 (= endpoint reachable). True test = Claude calling it.
  DURL=$(jq -r '.mcpServers["dialog-mcp"].url // ""' "$CLAUDE_CFG")
  if [[ -n "$DURL" ]]; then
    c=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" -o /dev/null -w "%{http_code}" \
      -X POST "$DURL" -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
      -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hc","version":"1"}}}')
    case "$c" in
      401|403) mcp_results+=("➖ | dialog-mcp | $c | endpoint reachable (OAuth) — confirm via Claude tool call");;
      2*)      mcp_results+=("✅ | dialog-mcp | $c | initialize OK");;
      *)       mcp_results+=("❌ | dialog-mcp | ${c:-000} | unreachable");;
    esac
  fi

  # context7: stdio MCP, zero-key. Probe public API; real test = Claude resolve-library-id.
  c=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" -o /dev/null -w "%{http_code}" \
    "https://context7.com/api/v1/search?query=react" || true)
  case "$c" in
    2*) mcp_results+=("✅ | context7 | $c | search API OK");;
    *)  mcp_results+=("➖ | context7 | ${c:-000} | stdio MCP — confirm via Claude resolve-library-id");;
  esac
fi

# ── Write report ──────────────────────────────────────────────────────
{
  echo "# Research Engine — Health Check Report"
  echo ""
  echo "> Auto-generated by \`health-check.sh\`. Re-run before any research session."
  echo "> Generated: $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo ""
  echo "**Summary: ✅ $PASS working · ⚠️ $WARN suspect · ❌ $FAIL dead** (of $((PASS+WARN+FAIL)) zero-key APIs tested)"
  echo ""
  echo "Agents: only use ✅ sources from this list. Treat ❌ as unavailable — do NOT cite \"found nothing\" from a dead endpoint as evidence of absence."
  echo ""
  echo "## Zero-key free APIs"
  echo ""
  echo "| Status | Source | HTTP | Note |"
  echo "|--------|--------|------|------|"
  printf '%s\n' "${results[@]}" | sed 's/^/| /; s/ | /| /g; s/$/ |/'
  echo ""
  echo "## CLIs"
  echo ""
  echo "| Status | Tool | Note |"
  echo "|--------|------|------|"
  for cli in gh python3 node curl jq pnpm npm; do
    if command -v "$cli" >/dev/null 2>&1; then
      echo "| ✅ | $cli | $(command -v "$cli") |"
    else
      echo "| ❌ | $cli | NOT INSTALLED |"
    fi
  done
  # gh auth status
  if gh auth status >/dev/null 2>&1; then
    echo "| ✅ | gh (auth) | authenticated |"
  else
    echo "| ⚠️ | gh (auth) | NOT authenticated — gh search may fail |"
  fi
  echo ""
  echo "## MCP liveness (real probe — CONNECTED ≠ WORKING)"
  echo ""
  echo "Each keyed service hit with its real key. ❌ = configured but the actual"
  echo "call fails (quota/credits dead). ➖ = endpoint reachable but final word"
  echo "needs Claude calling the tool in-session (OAuth / stdio transport)."
  echo ""
  echo "| Status | MCP | HTTP | Note |"
  echo "|--------|-----|------|------|"
  printf '%s\n' "${mcp_results[@]:-}" | sed '/^$/d; s/^/| /; s/ | /| /g; s/$/ |/'
  echo ""
  echo "## All configured MCP servers"
  echo ""
  echo "Detected from Claude config. A research agent can only use an MCP if it shows here."
  echo "Presence = configured (may still be quota-dead — see liveness table above)."
  echo ""
  echo "| MCP server |"
  echo "|------------|"
  for cfg in "$HOME/.claude.json" "$HOME/.config/claude/.mcp.json" "$HOME/.mcp.json"; do
    if [[ -f "$cfg" ]]; then
      jq -r '(.mcpServers // {}) | keys[]' "$cfg" 2>/dev/null | sort -u | sed 's/^/| /; s/$/ |/'
      break
    fi
  done
} > "$REPORT"

echo ""
echo "Report written to $REPORT"
echo "Summary: PASS=$PASS WARN=$WARN FAIL=$FAIL"
