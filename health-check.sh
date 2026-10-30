#!/usr/bin/env bash
# Research Engine Health Check + Repair Triage
# Tests: (1) zero-key free APIs, (2) keyed APIs with REAL keys from keys.env,
# (3) MCP liveness with real keys (quota-death detection), (4) CLIs.
# Writes a timestamped report that, for every failure, TELLS you how to fix it
# (⚠️ ACTION NEEDED section), so research agents skip dead tools instead of
# silently fetching nothing.
#
# Usage: bash health-check.sh [--quick | --community | --full] [--source ID ...]
# Keys:  ~/.config/research-engine/keys.env (sourced if present)
# Output: health-check-report.md (in this dir)

set -uo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPORT="${HEALTH_CHECK_REPORT:-$SCRIPT_DIR/health-check-report.md}"
REPORT_DIR="$(dirname -- "$REPORT")"
SOCIAL="${SOCIAL:-$SCRIPT_DIR/social-research.py}"
REGISTRY="${REGISTRY:-$SCRIPT_DIR/community-sources.json}"
TIMEOUT="${HEALTH_CHECK_TIMEOUT:-10}"
CONNECT_TIMEOUT="${HEALTH_CHECK_CONNECT_TIMEOUT:-3}"
RETRIES="${HEALTH_CHECK_RETRIES:-0}"
MAX_PARALLEL="${HEALTH_CHECK_JOBS:-12}"
SOURCE_TIMEOUT="${HEALTH_CHECK_SOURCE_TIMEOUT:-30}"
MODE="quick"
SELECTED_SOURCES=()
PASS=0; FAIL=0; WARN=0
CLAUDE_CFG="$HOME/.claude.json"

usage() {
  cat <<'EOF'
Usage: bash health-check.sh [--quick | --community | --full] [--source ID ...]

  --quick       Local regression after engine changes: registry, CLI and Chrome transport (default).
  --community   Probe every source in community-sources.json, but no paid/keyed inventory.
  --source ID   During later maintenance, reproduce a failed source from the ledger; repeatable.
  --full        Comprehensive inventory plus every community source and keyed API.

`--full` can consume limited API/MCP quota; run it only as an explicit maintenance audit.

Environment overrides: HEALTH_CHECK_REPORT, HEALTH_CHECK_TIMEOUT,
HEALTH_CHECK_CONNECT_TIMEOUT, HEALTH_CHECK_RETRIES, HEALTH_CHECK_JOBS,
HEALTH_CHECK_SOURCE_TIMEOUT, SOCIAL and REGISTRY.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick) MODE="quick" ;;
    --community) MODE="community" ;;
    --full) MODE="full" ;;
    --source)
      [[ $# -ge 2 ]] || { echo "health-check: --source needs an ID" >&2; exit 2; }
      SELECTED_SOURCES+=("$2")
      shift
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "health-check: unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

source_selected() {
  local wanted="$1" selected
  [[ "$MODE" == "full" || "$MODE" == "community" ]] && return 0
  for selected in "${SELECTED_SOURCES[@]:-}"; do
    [[ "$selected" == "$wanted" ]] && return 0
  done
  return 1
}

registry_valid() {
  [[ -f "$REGISTRY" ]] && jq -e '
    .schema_version and (.sources | type == "array" and length > 0) and
    all(.sources[];
      (.id | type == "string" and length > 0) and
      (.name | type == "string" and length > 0) and
      (.domains | type == "array" and length > 0) and
      (.access | type == "object") and
      (.routes | type == "object") and
      (.verification | type == "object") and
      (.verification.status == "working" or .verification.status == "conditional" or
        .verification.status == "failed") and
      (.access.credential_ref == null or
        (.access.credential_ref | type == "string" and startswith("gopass://")))
    )
  ' "$REGISTRY" >/dev/null 2>&1
}

# Argument/configuration errors are not health-check runs. Validate them before
# installing the EXIT trap so a typo cannot replace the last valid report.
if [[ ${#SELECTED_SOURCES[@]} -gt 0 ]]; then
  registry_valid || { echo "health-check: registry missing or invalid: $REGISTRY" >&2; exit 2; }
  for selected in "${SELECTED_SOURCES[@]}"; do
    if ! jq -e --arg id "$selected" 'any(.sources[]; .id == $id)' "$REGISTRY" >/dev/null; then
      echo "health-check: unknown source id: $selected" >&2
      exit 2
    fi
  done
fi

# Load obtained API keys so keyed APIs get a REAL probe (not just "needs key").
KEYS_FILE="$HOME/.config/research-engine/keys.env"
if [[ -f "$KEYS_FILE" ]]; then set -a; source "$KEYS_FILE" 2>/dev/null; set +a; fi

# Each test: name | method | url | extra-curl-args | expect-substring (optional)
# We check HTTP 2xx AND a non-empty plausible body.
results=()
keyed=()       # real-key probe rows
actions=()     # ⚠️ ACTION NEEDED triage: each = "icon|what|how-to-fix"
CHECK_DIR=$(mktemp -d)
CHECK_SEQ=0
CHECK_PIDS=()
CHECK_FILES=()
RUN_FINISHED=0
RUN_STARTED=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

on_exit() {
  local rc=$?
  if [[ "$RUN_FINISHED" -eq 0 ]]; then
    local failed_report
    failed_report=$(mktemp "$REPORT_DIR/.health-check-report.failed.XXXXXX")
    {
      echo "# Research Engine — Health Check Report"
      echo ""
      echo "> Status: **INTERRUPTED / FAILED**"
      echo "> Started: $RUN_STARTED"
      echo "> Mode: $MODE"
      echo "> Exit code: $rc"
      echo ""
      echo "This run did not complete. Do not reuse an older success report or interpret missing rows as healthy."
    } > "$failed_report"
    mv "$failed_report" "$REPORT"
  fi
  [[ -d "$CHECK_DIR" ]] && rm -rf "$CHECK_DIR"
}
trap on_exit EXIT
trap 'exit 124' INT TERM

# Record a repair action (shown at top of report so the check TELLS you the fix).
act(){ actions+=("$1"); }

check_worker() {
  local outfile="$1" name="$2" url="$3"; shift 3
  local jq_filter=""
  if [[ "${1:-}" == "--jq" ]]; then
    jq_filter="$2"
    shift 2
  fi
  local extra=("$@")
  local code size tmp json_ok=1 status row
  # ONE curl per endpoint (body to tmp, code via -w). Doing two separate curls
  # would double-hit rate-limited APIs (e.g. GDELT 1req/5s) and falsely fail them.
  tmp=$(mktemp)
  # A health check must be bounded. One retry is enough to separate a transient
  # blip from a consistently unhealthy endpoint; long retry loops belong in the
  # actual source adapter, not in a maintenance probe.
  code=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" \
    --retry "$RETRIES" --retry-delay 1 --retry-all-errors --retry-connrefused \
    --retry-max-time "$((TIMEOUT * (RETRIES + 1) + 5))" \
    -A "ResearchEngineHealthCheck/1.0" "${extra[@]}" -o "$tmp" -w "%{http_code}" "$url" 2>/dev/null || true)
  size=$(wc -c < "$tmp" 2>/dev/null || echo 0)
  if [[ -n "$jq_filter" ]] && ! jq -e "$jq_filter" "$tmp" >/dev/null 2>&1; then
    json_ok=0
  fi
  rm -f "$tmp"
  if [[ "$code" =~ ^2 ]] && [[ "$size" -gt 2 ]] && [[ "$json_ok" -eq 1 ]]; then
    status="pass"; row="✅ | $name | $code | OK"
  elif [[ "$code" =~ ^2 ]] && [[ "$size" -gt 2 ]] && [[ "$json_ok" -eq 0 ]]; then
    status="warn"; row="⚠️ | $name | $code | response failed JSON success check"
  elif [[ "$code" =~ ^2 ]]; then
    status="warn"; row="⚠️ | $name | $code | 2xx but EMPTY body"
  elif [[ "$code" == "429" ]]; then
    status="warn"; row="⚠️ | $name | 429 | rate-limited (TRANSIENT — retry with spacing, not dead)"
  else
    status="fail"; row="❌ | $name | ${code:-000} | dead/blocked/changed"
  fi
  printf '%s\t%s\n' "$status" "$row" > "$outfile"
}

collect_oldest_check() {
  local pid="${CHECK_PIDS[0]}" outfile="${CHECK_FILES[0]}" status row
  wait "$pid" || true
  if [[ -s "$outfile" ]]; then
    IFS=$'\t' read -r status row < "$outfile"
  else
    status="fail"
    row="❌ | internal health-check worker | — | worker exited without a result"
  fi
  results+=("$row")
  case "$status" in
    pass) ((PASS++)) ;;
    warn) ((WARN++)) ;;
    *) ((FAIL++)) ;;
  esac
  CHECK_PIDS=("${CHECK_PIDS[@]:1}")
  CHECK_FILES=("${CHECK_FILES[@]:1}")
}

check() {
  [[ "$MODE" == "full" ]] || return 0
  local outfile="$CHECK_DIR/$CHECK_SEQ.result"
  CHECK_SEQ=$((CHECK_SEQ + 1))
  check_worker "$outfile" "$@" &
  CHECK_PIDS+=("$!")
  CHECK_FILES+=("$outfile")
  if [[ ${#CHECK_PIDS[@]} -ge "$MAX_PARALLEL" ]]; then
    collect_oldest_check
  fi
}

drain_checks() {
  while [[ ${#CHECK_PIDS[@]} -gt 0 ]]; do
    collect_oldest_check
  done
}

echo "Running research engine health check (mode=$MODE)..."
if [[ ${#SELECTED_SOURCES[@]} -gt 0 ]]; then
  echo "Selected community sources: ${SELECTED_SOURCES[*]}"
fi

# ── Zero-key free APIs (the bulk agents rely on) ──────────────────────
check "HN Algolia (search)"     "https://hn.algolia.com/api/v1/search?query=ai&tags=story"
check "HN Firebase (topstories)" "https://hacker-news.firebaseio.com/v0/topstories.json"
check "Lobste.rs JSON"          "https://lobste.rs/hottest.json"
check "Bluesky searchPosts"     "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=ai&limit=5"
check "Mastodon trends"         "https://mastodon.social/api/v1/trends/statuses"
check "Lemmy search"            "https://lemmy.world/api/v3/search?q=ai&type_=Posts&limit=5"
check "DEV.to articles"         "https://dev.to/api/articles?tag=ai&per_page=5"
check "Bilibili public search"  "https://api.bilibili.com/x/web-interface/search/all/v2?keyword=AI&page=1" --jq '.code == 0 and ([.data.result[]?.data?[]?] | length > 0)' -H "Referer: https://www.bilibili.com/"
check "V2EX hot topics"         "https://www.v2ex.com/api/topics/hot.json" --jq 'type == "array" and length > 0 and .[0].id != null'
check "V2EX node topics"        "https://www.v2ex.com/api/topics/show.json?node_name=python&page=1" --jq 'type == "array" and length > 0 and .[0].id != null'
check "LinkedIn public via Jina" "https://r.jina.ai/https://www.linkedin.com/in/satyanadella/"
# Reddit .json is IP-blocked from this box (403) — NOT tested here.
#   Reddit research MUST go through agent-chrome.py (logged-in browser) or
#   Arctic Shift. See the deep-research skill's Forum Deep Dive HARD RULE.
check "Arctic Shift posts search" "https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=programming&limit=1&sort=desc"
check "Arctic Shift comments tree" "https://arctic-shift.photon-reddit.com/api/comments/tree?link_id=t3_x8i09x&limit=3"
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

# ── Round 13 new zero-key sources (verified 2026-05-31) ───────────────
check "OpenReview"              "https://api2.openreview.net/notes?content.venue=ICLR%202025&limit=2"
check "CourtListener v4"        "https://www.courtlistener.com/api/rest/v4/search/?q=copyright&type=o"
check "SEC EFTS full-text"      "https://efts.sec.gov/LATEST/search-index?q=%22AI%22&forms=10-K"
check "Socrata Discovery"       "https://api.us.socrata.com/api/catalog/v1?q=budget&limit=2"
check "OpenRouter models"       "https://openrouter.ai/api/v1/models"
check "Ollama registry"         "https://ollama.com/api/tags"
check "ClinicalTrials v2"       "https://clinicaltrials.gov/api/v2/studies?query.cond=cancer&pageSize=2"
check "PubChem PUG-REST"        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin/property/MolecularFormula/JSON"
check "GBIF occurrence"         "https://api.gbif.org/v1/occurrence/search?q=Puma&limit=2"
check "USGS Earthquake"         "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit=2&starttime=2026-05-01"
check "WHO GHO OData"           "https://ghoapi.azureedge.net/api/Indicator"
check "Marginalia Search"       "https://api.marginalia.nu/public/search/llm?count=2"
# 2026-10-30 prior-art harvest (last30days, x-tweet-fetcher, RSSHub): zero-key routes verified live
check "Greenhouse jobs API"     "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs" --jq '(.jobs | length) > 0'
check "Lever jobs API"          "https://api.lever.co/v0/postings/palantir?mode=json&limit=2" --jq 'type == "array" and length > 0'
check "Ashby jobs API"          "https://api.ashbyhq.com/posting-api/job-board/linear" --jq '(.jobs | length) > 0'
check "FxTwitter single tweet"  "https://api.fxtwitter.com/AnthropicAI/status/1925591505332576377" --jq '.code == 200 and .tweet.text != null'
check "Telegram t.me/s preview" "https://t.me/s/durov"
check "Juejin search API"       "https://api.juejin.cn/search_api/v1/search?aid=2608&uuid=1&spider=0" --jq '.err_no == 0 and (.data | length) > 0' -X POST -H "Content-Type: application/json" -d '{"key_word":"claude","id_type":0,"cursor":"0","limit":3,"search_type":0,"sort_type":0,"version":1}'
check "DCInside search"         "https://search.dcinside.com/combine/q/%EC%84%B1%ED%98%95" -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
check "Wikimedia Pageviews"     "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/2026/05/01"
drain_checks

# Parallel keyless web search (search.parallel.ai/mcp). Plain HTTP JSON-RPC, no key, no
# resident MCP: initialize -> session id -> tools/call web_search. Added 2026-10-30.
if [[ "$MODE" == "full" ]]; then
  ptmp=$(mktemp -d)
  pe="https://search.parallel.ai/mcp"
  curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" -D "$ptmp/h" -o /dev/null \
    -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -X POST "$pe" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"research-engine-healthcheck","version":"1"}}}'
  psid=$(grep -i '^mcp-session-id:' "$ptmp/h" | awk '{print $2}' | tr -d '\r')
  pcode=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$((TIMEOUT * 3))" -o "$ptmp/b" -w '%{http_code}' \
    -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' ${psid:+-H "Mcp-Session-Id: $psid"} \
    -X POST "$pe" -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"web_search","arguments":{"objective":"health check","search_queries":["anthropic claude"],"session_id":"re-healthcheck"}}}')
  # The endpoint answers plain JSON (2026-10-30); still accept an SSE "data:" frame if it switches.
  pbody=$(grep '^data:' "$ptmp/b" | tail -1 | sed 's/^data: *//'); [[ -n "$pbody" ]] || pbody=$(cat "$ptmp/b")
  pn=$(jq -r '.result.content[0].text' <<<"$pbody" 2>/dev/null | jq '.results | length' 2>/dev/null)
  if [[ "$pcode" =~ ^2 && "${pn:-0}" -ge 1 ]]; then
    results+=("✅ | Parallel keyless web search | $pcode | $pn results"); ((PASS++))
  else
    results+=("❌ | Parallel keyless web search | ${pcode:-000} | results=${pn:-none} session=${psid:+yes}"); ((FAIL++))
  fi
  rm -rf "$ptmp"
fi

# ── MCP liveness probe (Round 12) ─────────────────────────────────────
# CONNECTED ≠ WORKING. A configured MCP can be quota-dead. We hit each keyed
# service's REST endpoint with the REAL key (read from keys.env since 2026-10-30;
# these MCPs were removed, and reading ~/.claude.json made the probes report
# "not configured" forever) so the report shows ACTUAL usability.
#   Tavily uses the free /usage endpoint; Exa has none, so it spends ~1 search.
#   Firecrawl uses the free v2 credit-usage endpoint.
#   OAuth MCPs (dialog-mcp) can't be auth'd from bash — only Claude's stored
#   token works; we report reachability + tell the agent to confirm in-session.
mcp_results=()
if [[ "$MODE" == "full" && -f "$CLAUDE_CFG" ]]; then
  TKEY=${TAVILY_API_KEY:-}
  if [[ -n "${TKEY:-}" ]]; then
    tbody=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" -w "\n%{http_code}" \
      "https://api.tavily.com/usage" -H "Authorization: Bearer $TKEY")
    c=$(tail -1 <<<"$tbody")
    tused=$(head -n -1 <<<"$tbody" | jq -r '"\(.account.plan_usage)/\(.account.plan_limit)"' 2>/dev/null)
    case "$c" in
      2*)  mcp_results+=("✅ | tavily | $c | REST OK — plan usage $tused");;
      432) mcp_results+=("❌ | tavily | 432 | QUOTA EXCEEDED — connected but search DEAD");;
      4*)  mcp_results+=("⚠️ | tavily | $c | reachable, auth/plan issue");;
      *)   mcp_results+=("❌ | tavily | ${c:-000} | unreachable");;
    esac
  else mcp_results+=("⚠️ | tavily | — | no TAVILY_API_KEY in keys.env"); fi

  EKEY=${EXA_API_KEY:-}
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
  else mcp_results+=("⚠️ | exa | — | no EXA_API_KEY in keys.env"); fi

  FKEY=${FIRECRAWL_API_KEY:-}
  if [[ -n "${FKEY:-}" ]]; then
    body=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" \
      "https://api.firecrawl.dev/v2/team/credit-usage" -H "Authorization: Bearer $FKEY")
    rem=$(echo "$body" | jq -r '.data.remainingCredits // empty' 2>/dev/null)
    if [[ -n "$rem" ]]; then mcp_results+=("✅ | firecrawl | 200 | $rem credits remaining");
    else mcp_results+=("❌ | firecrawl | — | credit-usage probe failed (key dead?)"); fi
  else mcp_results+=("⚠️ | firecrawl | — | no FIRECRAWL_API_KEY in keys.env"); fi

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

# ── Keyed-API real-key probe (Round 14) ──────────────────────────────
# CONNECTED ≠ USABLE for key-gated APIs too. Now that we hold real keys
# (keys.env), hit each with its actual key so the report shows ✅ verified
# instead of a dormant "needs key". Empty key → ➖ + an ACTION to go get it.
kcheck(){  # name | keyvar | success-grep | curl-args...
  local name="$1" kv="$2" ok="$3"; shift 3
  local key="${!kv:-}" tmp code
  if [[ -z "$key" ]]; then
    keyed+=("🔑 | $name | — | no key set")
    if [[ "$kv" == "TIKHUB_API_KEY" ]]; then
      act "💰|$name 未有 funded key|註冊 key 並入錢後填入 ~/.config/research-engine/keys.env；小紅書 routes 不接受 free credit"
    else
      act "🔑|$name 未有 key|申請 free key 填入 ~/.config/research-engine/keys.env（見 engine「🔑 Key Activation Checklist」）"
    fi
    return
  fi
  tmp=$(mktemp)
  code=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" \
        --retry "$RETRIES" --retry-delay 1 --retry-all-errors \
        --retry-max-time "$((TIMEOUT * (RETRIES + 1) + 5))" \
        -A "ResearchEngineHealthCheck/1.0" -o "$tmp" -w "%{http_code}" "$@" 2>/dev/null)
  if [[ "$code" =~ ^2 ]] && grep -qi "$ok" "$tmp" 2>/dev/null; then
    keyed+=("✅ | $name | $code | key OK")
  elif [[ "$code" =~ ^2 ]]; then
    keyed+=("⚠️ | $name | $code | 2xx 但搵唔到「$ok」（key 弱/受限？）")
    act "⚠️|$name key 回應異常 ($code)|檢查 plan limit / endpoint 版本"
  else
    keyed+=("❌ | $name | ${code:-000} | key REJECTED / endpoint down")
    act "❌|$name key 唔 work ($code)|retest；過期或被 flag 就去 dashboard 重新生成"
  fi
  rm -f "$tmp"; sleep 0.3
}
if [[ "$MODE" == "full" ]]; then
  echo "Probing keyed APIs with real keys..."
  kcheck "FRED"          FRED_API_KEY          "observations" "https://api.stlouisfed.org/fred/series/observations?series_id=GDP&api_key=${FRED_API_KEY:-}&file_type=json&limit=1"
  kcheck "US Census"     CENSUS_API_KEY        "NAME"         "https://api.census.gov/data/2021/acs/acs5?get=NAME&for=state:06&key=${CENSUS_API_KEY:-}"
  kcheck "CanLII"        CANLII_API_KEY        "caseDatabases" "https://api.canlii.org/v1/caseBrowse/en/?api_key=${CANLII_API_KEY:-}"
  # Naver: OFFICIAL Search API only. Never drive naver.com with a browser (permanent account ban).
  kcheck "Naver Search"  NAVER_CLIENT_ID       "\"items\""    "https://openapi.naver.com/v1/search/blog.json?query=test&display=1" -H "X-Naver-Client-Id: ${NAVER_CLIENT_ID:-}" -H "X-Naver-Client-Secret: ${NAVER_CLIENT_SECRET:-}"
  kcheck "Open PageRank" OPENPAGERANK_API_KEY  "page_rank"    "https://openpagerank.com/api/v1.0/getPageRank?domains%5B%5D=google.com" -H "API-OPR: ${OPENPAGERANK_API_KEY:-}"
  kcheck "FMP"           FMP_API_KEY           "symbol"       "https://financialmodelingprep.com/stable/quote?symbol=AAPL&apikey=${FMP_API_KEY:-}"
  kcheck "OpenStates"    OPENSTATES_API_KEY    "results"      "https://v3.openstates.org/jurisdictions?per_page=1" -H "X-API-Key: ${OPENSTATES_API_KEY:-}"
  kcheck "OpenSanctions" OPENSANCTIONS_API_KEY "results"      "https://api.opensanctions.org/search/default?q=test&limit=1" -H "Authorization: ApiKey ${OPENSANCTIONS_API_KEY:-}"
  kcheck "Congress.gov"  CONGRESS_API_KEY      "bills"        "https://api.congress.gov/v3/bill?api_key=${CONGRESS_API_KEY:-}&format=json&limit=1"
  kcheck "govinfo"       GOVINFO_API_KEY       "collection"   "https://api.govinfo.gov/collections?api_key=${GOVINFO_API_KEY:-}"
  kcheck "OpenFEC"       OPENFEC_API_KEY       "results"      "https://api.open.fec.gov/v1/candidates/?api_key=${OPENFEC_API_KEY:-}&per_page=1"
  kcheck "Finnhub"       FINNHUB_API_KEY       "c"            "https://finnhub.io/api/v1/quote?symbol=AAPL&token=${FINNHUB_API_KEY:-}"
  kcheck "ScrapeCreators social" SCRAPECREATORS_API_KEY "credit" "https://api.scrapecreators.com/v1/account/credit-balance" -H "x-api-key: ${SCRAPECREATORS_API_KEY:-}"
  kcheck "TikHub social" TIKHUB_API_KEY         "data"   "https://api.tikhub.io/api/v1/tikhub/user/get_user_info" -H "Authorization: Bearer ${TIKHUB_API_KEY:-}"
fi

# ── Declared-but-EMPTY keys ───────────────────────────────────────────
# keys.env can contain `FOO_API_KEY=` with nothing after the `=`. Every downstream
# check then sees the var as "set", builds a request with an empty credential, and
# gets a 401 that reads like "the key expired" instead of "there was never a key".
# Same silent-failure class as the browser bug: the tool looks present and isn't.
emptykeys=()
if [[ -f "$KEYS_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*($|#.*$|\"\"[[:space:]]*(#.*)?$|\'\'[[:space:]]*(#.*)?$) ]]; then
      emptykeys+=("${BASH_REMATCH[2]}")
    fi
  done < "$KEYS_FILE"
  if [[ ${#emptykeys[@]} -gt 0 ]]; then
    act "🔑|keys.env 有 ${#emptykeys[@]} 個 key 聲明咗但係空：${emptykeys[*]}|去申請填返，或者由 keys.env 刪走 — 空 key 會令 request 帶住空 credential 出去，收到 401 睇落似「key 過期」，其實根本冇 key"
  fi
fi

# ── Browser session (agent Chrome) — the 403-bypass path ─────────────
# Reddit / Quora / LinkedIn / 小紅書 all 403 or login-wall plain curl. The ONLY
# reliable path is running the request inside the logged-in agent Chrome. This
# section exists because that path was invisible to the health check for months
# while it was silently broken — agents "found nothing" and nobody could tell.
browser=()
BPASS=0; BWARN=0; BFAIL=0
bact(){
  browser+=("$1")
  case "$1" in
    "✅ | "*) ((BPASS++)) ;;
    "⚠️ | "*) ((BWARN++)) ;;
    "❌ | "*) ((BFAIL++)) ;;
  esac
}
AC="$HOME/.local/bin/agent-chrome.py"
CDP_PORT="${AGENT_CHROME_PORT:-9223}"

echo "Probing agent Chrome browser session..."
if ! command -v python3 >/dev/null 2>&1 || [[ ! -f "$AC" ]]; then
  bact "❌ | agent-chrome.py | — | MISSING at $AC"
  act "❌|agent-chrome.py 唔見咗|Reddit/login-gated 站全部研究唔到。restore 返個 script"
else
  ver=$(curl -s --connect-timeout 3 --max-time 8 "http://127.0.0.1:$CDP_PORT/json/version" 2>/dev/null | jq -r '.Browser // empty' 2>/dev/null)
  if [[ -z "$ver" ]]; then
    bact "❌ | agent Chrome (CDP :$CDP_PORT) | — | NOT RUNNING"
    act "❌|agent Chrome 冇開 (port $CDP_PORT)|開返：DISPLAY=:0 setsid /usr/bin/google-chrome --remote-debugging-port=$CDP_PORT --user-data-dir=\$HOME/.config/agent-chrome --no-first-run --no-default-browser-check --restore-last-session=false >/tmp/agent-chrome.log 2>&1 &"
  else
    bact "✅ | agent Chrome (CDP :$CDP_PORT) | 200 | $ver"

    # Regression guard: async JS must resolve. Without awaitPromise every
    # `await fetch(...)` returned {} and agents concluded "browser unavailable".
    pr=$(timeout "$SOURCE_TIMEOUT" python3 "$AC" eval active 'Promise.resolve("AWAIT_OK")' 2>&1 | tail -1)
    if [[ "$pr" == "AWAIT_OK" ]]; then
      bact "✅ | CDP awaitPromise | — | async JS resolves (no silent {})"
    else
      bact "❌ | CDP awaitPromise | — | async JS returned '$pr' — every fetch will look empty"
      act "❌|agent-chrome.py eval 唔 await promise|所有 browser fetch 會靜靜哋回 {}。加返 awaitPromise:True 落 Runtime.evaluate"
    fi

    # End-to-end Reddit probes run only when selected. Quick mode validates
    # the transport without spending time on unrelated source calls.
    if source_selected reddit; then
    # /search.json is blocked in-session since 2026-10-30; probe the shreddit route agents use.
    tmpb=$(mktemp)
    if timeout "$SOURCE_TIMEOUT" python3 "$SOCIAL" reddit-search llm --subreddit LocalLLaMA --limit 3 \
        >"$tmpb" 2>/dev/null; then
      n=$(jq -r '.count' "$tmpb" 2>/dev/null || echo 0)
      if [[ "${n:-0}" -ge 1 ]]; then
        bact "✅ | Reddit search via browser | 200 | $n posts, $(wc -c <"$tmpb") bytes"
      else
        bact "❌ | Reddit search via browser | 200 | empty result set (login wall / shadow-block?)"
        act "❌|Reddit browser fetch 攞到 0 結果|睇 \`agent-chrome.py login-check https://www.reddit.com/\`；可能要重新登入"
      fi
    else
      bact "❌ | Reddit search via browser | — | fetch FAILED"
      act "❌|Reddit browser fetch 失敗|跑 \`bash qa/agent-chrome-qa.sh\` 睇邊一步斷"
    fi
    rm -f "$tmpb"

    ccode=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
      'https://www.reddit.com/r/LocalLLaMA/search.json?q=llm&limit=3' 2>/dev/null)
    bact "ℹ️ | Reddit via plain curl (control) | ${ccode:-000} | 403/429 是預期 — 證明 browser 路線係必需"

    # Login state per site — content-based whoami, not cookie-name guessing
    # (session cookies are httpOnly, so document.cookie always looks logged-out).
    for site in "https://www.reddit.com/"; do
      lc=$(timeout "$SOURCE_TIMEOUT" python3 "$AC" login-check "$site" 2>&1 | tail -1)
      case "$lc" in
        in*)  bact "✅ | login: $site | — | ${lc#in	}";;
        out*) bact "❌ | login: $site | — | LOGGED OUT — ${lc#out	}"
              act "❌|Reddit 未登入|喺 agent Chrome (port $CDP_PORT) 手動登入一次，session 會 persist";;
        *)    bact "⚠️ | login: $site | — | $lc";;
      esac
    done
    fi

    # XHS has no honest cookie-name-only whoami. Probe the actual native search
    # page through the one-shot adapter; login wall must be FAILED, not 0 results.
    if source_selected xiaohongshu; then
    tmpx=$(mktemp)
    if [[ -f "$SOCIAL" ]] && timeout "$SOURCE_TIMEOUT" python3 "$SOCIAL" xhs-search '咖啡' --route browser >"$tmpx" 2>"$tmpx.err"; then
      xn=$(jq -r '.count // 0' "$tmpx" 2>/dev/null || echo 0)
      bact "✅ | Xiaohongshu native search via browser | 200 | $xn notes"
    elif [[ ! -f "$SOCIAL" ]]; then
      bact "❌ | Xiaohongshu browser adapter | — | MISSING at $SOCIAL"
      act "❌|XHS browser adapter 唔見咗|restore ai-research-engine/social-research.py"
    else
      xerr=$(tail -1 "$tmpx.err" 2>/dev/null)
      bact "❌ | Xiaohongshu native search via browser | — | ${xerr:-FAILED}"
      act "❌|小紅書 native search 未可用|喺 Agent Chrome 手動登入小紅書一次，再跑 social-research.py xhs-search '咖啡' --route browser"
    fi
    rm -f "$tmpx" "$tmpx.err"
    fi

    # 1Point3Acres: use the site's own tRPC endpoint inside the persisted
    # Agent Chrome session.  This is deliberately not a DOM-scraping probe.
    if source_selected onepoint3acres; then
    tmp1p=$(mktemp)
    if [[ -f "$SOCIAL" ]] && RESEARCH_ENGINE_NO_AUTO_LOGIN=1 timeout "$SOURCE_TIMEOUT" python3 "$SOCIAL" onepoint-search \
        '加拿大 找工' --limit 3 >"$tmp1p" 2>"$tmp1p.err"; then
      one_route=$(jq -r '.route // empty' "$tmp1p" 2>/dev/null)
      one_n=$(jq -r '.count // 0' "$tmp1p" 2>/dev/null || echo 0)
      one_auth=$(jq -r '.authenticated // false' "$tmp1p" 2>/dev/null)
      if [[ "$one_route" == "browser-session-api" && "$one_auth" == "true" && "${one_n:-0}" -ge 1 ]]; then
        bact "✅ | 1Point3Acres first-party API via browser | 200 | $one_n results; authenticated tRPC route"
      else
        bact "❌ | 1Point3Acres first-party API via browser | 200 | unexpected route/auth/count"
        act "❌|1Point3Acres API adapter 回應不完整|跑 social-research.py onepoint-search '加拿大 找工' --limit 3；不要改用 DOM crawler"
      fi
    elif [[ ! -f "$SOCIAL" ]]; then
      bact "❌ | 1Point3Acres API adapter | — | MISSING at $SOCIAL"
      act "❌|1Point3Acres API adapter 唔見咱|restore ai-research-engine/social-research.py"
    else
      one_err=$(tail -1 "$tmp1p.err" 2>/dev/null)
      bact "❌ | 1Point3Acres first-party API via browser | — | ${one_err:-FAILED}"
      act "❌|1Point3Acres session 未可用|重用 Agent Chrome 內 Google session 登入，然後重跑；不要改用 DOM crawler"
    fi
    rm -f "$tmp1p" "$tmp1p.err"
    fi

    if source_selected grapevine; then
    tmpgv=$(mktemp)
    if [[ -f "$SOCIAL" ]] && timeout "$SOURCE_TIMEOUT" python3 "$SOCIAL" grapevine-search \
        'software engineer' --limit 2 >"$tmpgv" 2>"$tmpgv.err"; then
      gv_route=$(jq -r '.route // empty' "$tmpgv" 2>/dev/null)
      gv_n=$(jq -r '.count // 0' "$tmpgv" 2>/dev/null || echo 0)
      if [[ "$gv_route" == "browser-session-api" && "${gv_n:-0}" -ge 1 ]]; then
        bact "✅ | Grapevine first-party API via browser | 200 | $gv_n results"
      else
        bact "❌ | Grapevine first-party API via browser | 200 | unexpected route/count"
        act "❌|Grapevine API adapter 回應不完整|跑 social-research.py grapevine-search 'software engineer' --limit 2；不要改用 DOM crawler"
      fi
    elif [[ ! -f "$SOCIAL" ]]; then
      bact "❌ | Grapevine API adapter | — | MISSING at $SOCIAL"
    else
      gv_err=$(tail -1 "$tmpgv.err" 2>/dev/null)
      bact "❌ | Grapevine first-party API via browser | — | ${gv_err:-FAILED}"
      act "❌|Grapevine API route 未可用|查清 CORS/API schema；不要改用寬頻 DOM crawler"
    fi
    rm -f "$tmpgv" "$tmpgv.err"
    fi

    if source_selected the-student-room; then
    tmptsr=$(mktemp)
    if [[ -f "$SOCIAL" ]] && timeout "$SOURCE_TIMEOUT" python3 "$SOCIAL" studentroom-thread \
        7507123 --max-posts 1 >"$tmptsr" 2>"$tmptsr.err"; then
      tsr_route=$(jq -r '.route // empty' "$tmptsr" 2>/dev/null)
      tsr_n=$(jq -r '.loaded_posts // 0' "$tmptsr" 2>/dev/null || echo 0)
      if [[ "$tsr_route" == "public-thread-via-agent-chrome" && "${tsr_n:-0}" -ge 1 ]]; then
        bact "✅ | The Student Room public thread via browser | 200 | $tsr_n post parsed"
      else
        bact "❌ | The Student Room public thread via browser | 200 | unexpected route/count"
      fi
    elif [[ ! -f "$SOCIAL" ]]; then
      bact "❌ | The Student Room adapter | — | MISSING at $SOCIAL"
    else
      tsr_err=$(tail -1 "$tmptsr.err" 2>/dev/null)
      bact "❌ | The Student Room public thread via browser | — | ${tsr_err:-FAILED}"
      act "❌|The Student Room browser route 未可用|用 web search discovery，再跑 social-research.py studentroom-thread THREAD_ID"
    fi
    rm -f "$tmptsr" "$tmptsr.err"
    fi

    if source_selected blind; then
      tmpblind=$(mktemp)
      if timeout "$SOURCE_TIMEOUT" python3 "$AC" fetch 'https://www.teamblind.com/' \
          --out "$tmpblind" >/dev/null 2>&1; then
        if grep -Eq '\\?"isLoggedIn\\?":true' "$tmpblind"; then
          bact "✅ | Blind authenticated home feed | 200 | server payload confirms isLoggedIn=true"
        else
          bact "❌ | Blind authenticated home feed | 200 | authenticated marker missing"
          act "❌|Blind session 未登入|用 gopass://research-engine/community/blind 登入 Agent Chrome"
        fi
      else
        bact "❌ | Blind browser route | — | fetch FAILED"
        act "❌|Blind browser route 失敗|check Agent Chrome and teamblind.com access"
      fi
      rm -f "$tmpblind"
    fi
  fi
fi

# Public phonebook and API adapters do not require Agent Chrome.
if registry_valid; then
  source_count=$(jq '.sources | length' "$REGISTRY")
  bact "✅ | Community source phonebook | local | $source_count sources; valid JSON schema shell check"
else
  bact "❌ | Community source phonebook | local | missing or invalid: $REGISTRY"
  act "❌|Community source phonebook 壞咗|validate community-sources.json and restore required fields"
fi

if source_selected college-confidential; then
  tmpcc=$(mktemp)
  if [[ -f "$SOCIAL" ]] && timeout "$SOURCE_TIMEOUT" python3 "$SOCIAL" collegeconf-search \
      'Eli Whitney Students Program' --limit 1 >"$tmpcc" 2>"$tmpcc.err"; then
    cc_route=$(jq -r '.route // empty' "$tmpcc" 2>/dev/null)
    cc_n=$(jq -r '.count // 0' "$tmpcc" 2>/dev/null || echo 0)
    if [[ "$cc_route" == "public-discourse-json" && "${cc_n:-0}" -ge 1 ]]; then
      bact "✅ | College Confidential public Discourse API | 200 | $cc_n search result"
    else
      bact "❌ | College Confidential public Discourse API | 200 | unexpected route/count"
    fi
  elif [[ ! -f "$SOCIAL" ]]; then
    bact "❌ | College Confidential adapter | — | MISSING at $SOCIAL"
    act "❌|College Confidential adapter 唔見咗|restore $SOCIAL"
  else
    cc_err=$(tail -1 "$tmpcc.err" 2>/dev/null)
    bact "❌ | College Confidential public Discourse API | — | ${cc_err:-FAILED}"
    act "❌|College Confidential JSON route 未可用|check search.json/topic JSON schema"
  fi
  rm -f "$tmpcc" "$tmpcc.err"
fi

if source_selected bc-transfer-guide; then
  tmpbc=$(mktemp)
  if [[ -f "$SOCIAL" ]] && timeout "$SOURCE_TIMEOUT" python3 "$SOCIAL" bctransfer-institutions \
      --query UBCV --limit 1 >"$tmpbc" 2>"$tmpbc.err"; then
    bc_route=$(jq -r '.route // empty' "$tmpbc" 2>/dev/null)
    bc_n=$(jq -r '.count // 0' "$tmpbc" 2>/dev/null || echo 0)
    if [[ "$bc_route" == "official-public-api" && "${bc_n:-0}" -ge 1 ]]; then
      bact "✅ | BC Transfer Guide official API | 200 | UBCV institution route working"
    else
      bact "❌ | BC Transfer Guide official API | 200 | unexpected route/count"
    fi
  elif [[ ! -f "$SOCIAL" ]]; then
    bact "❌ | BC Transfer Guide adapter | — | MISSING at $SOCIAL"
    act "❌|BC Transfer Guide adapter 唔見咗|restore $SOCIAL"
  else
    bc_err=$(tail -1 "$tmpbc.err" 2>/dev/null)
    bact "❌ | BC Transfer Guide official API | — | ${bc_err:-FAILED}"
    act "❌|BC Transfer Guide API 未可用|check public agreementws endpoint/schema"
  fi
  rm -f "$tmpbc" "$tmpbc.err"
fi

# ── MCP availability BY CWD SCOPE ─────────────────────────────────────
# .mcp.json is project-scoped: a server only loads when Claude's cwd is that
# project. An agent launched from ~ gets a DIFFERENT toolset than one launched
# from ~/.claude. Listing "all configured servers" without saying where they
# load from is how a skill ends up telling agents to call tools that don't exist.
mcp_scope=()
for cfg in "$HOME/.claude.json:user-global (every cwd)" \
           "$HOME/.mcp.json:cwd=~ (the default)" \
           "$HOME/.claude/.mcp.json:cwd=~/.claude ONLY" \
           "$HOME/MyGithub/.mcp.json:cwd=~/MyGithub ONLY"; do
  f="${cfg%%:*}"; where="${cfg#*:}"
  if [[ -f "$f" ]]; then
    names=$(jq -r '(.mcpServers // {}) | keys | join(", ")' "$f" 2>/dev/null)
    [[ -z "$names" ]] && names="(none)"
    mcp_scope+=("$where | ${f/#$HOME/\~} | $names")
  fi
done

# ── Build repair triage from zero-key failures + MCP quota deaths ──────
for row in "${results[@]:-}"; do
  case "$row" in
    "❌ | "*) nm=$(echo "$row"|awk -F' \\| ' '{print $2}'); co=$(echo "$row"|awk -F' \\| ' '{print $3}')
      case "$nm" in
        GDELT*)        act "❌|GDELT ${co}|shared-IP 1req/5s，慣性 flaky — retry / 換時間，唔好當真死";;
        "Open Library"*) act "❌|Open Library ${co}|偶發 timeout — retry 通常返生";;
        crt.sh*)       act "❌|crt.sh ${co}|postgres 慢，已加 retry — 持續死先當 dead";;
        *)             act "❌|$nm ${co}|curl 重試；查 endpoint 有冇搬（見 engine stale-URL log）";;
      esac;;
  esac
done
for row in "${mcp_results[@]:-}"; do
  case "$row" in
    "❌ | tavily"*) act "❌|Tavily quota 爆 (432)|search 改用 open-websearch / Firecrawl Search";;
    "❌ | exa"*)    act "❌|Exa credits 爆 (402)|改用 open-websearch；或 top-up dashboard.exa.ai";;
    "❌ | "*)       nm=$(echo "$row"|awk -F' \\| ' '{print $2}'); act "❌|MCP $nm 唔通|睇 engine「💀 死咗 MCP queue」嘅 fix path";;
  esac
done

KFAIL=0; MFAIL=0
for row in "${keyed[@]:-}"; do
  [[ "$row" == "❌ | "* ]] && KFAIL=$((KFAIL + 1))
done
for row in "${mcp_results[@]:-}"; do
  [[ "$row" == "❌ | "* ]] && MFAIL=$((MFAIL + 1))
done

# ── Write report atomically ───────────────────────────────────────────
REPORT_TMP=$(mktemp "$REPORT_DIR/.health-check-report.success.XXXXXX")
{
  echo "# Research Engine — Health Check Report"
  echo ""
  echo "> Status: **COMPLETED**"
  if (( FAIL > 0 || BFAIL > 0 || KFAIL > 0 || MFAIL > 0 )); then
    echo "> Result: **UNHEALTHY**"
  else
    echo "> Result: **HEALTHY**"
  fi
  echo "> Point-in-time maintenance snapshot, not a pre-search allowlist. Use \`--source\` in a later maintenance pass to reproduce failures collected in the ledger."
  echo "> Generated: $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo "> Mode: $MODE"
  if [[ ${#SELECTED_SOURCES[@]} -gt 0 ]]; then
    echo "> Selected sources: ${SELECTED_SOURCES[*]}"
  fi
  echo ""
  echo "**Broad inventory: ✅ $PASS working · ⚠️ $WARN suspect · ❌ $FAIL dead** (of $((PASS+WARN+FAIL)) zero-key APIs tested)"
  echo ""
  echo "**Local/community routes: ✅ $BPASS working · ⚠️ $BWARN suspect · ❌ $BFAIL failed**"
  if [[ "$MODE" != "full" ]]; then
    echo ""
    echo "> The broad zero-key and keyed inventories were intentionally skipped. Use \`--full\` for the comprehensive audit."
  fi
  echo ""
  echo "At research time, execute each selected source directly. If it fails, record \`FAILED\`; never cite a broken endpoint's silence as evidence of absence."
  echo ""
  # ── ⚠️ ACTION NEEDED (repair triage) — the check now TELLS you how to fix ──
  echo "## ⚠️ ACTION NEEDED — repair triage"
  echo ""
  if [[ ${#actions[@]} -eq 0 ]]; then
    echo "✅ 全部健康，冇嘢要修。"
  else
    echo "| | 問題 | 點修 |"
    echo "|---|------|------|"
    printf '%s\n' "${actions[@]}" | awk -F'|' '{printf "| %s | %s | %s |\n",$1,$2,$3}'
    echo ""
    echo "> 🔑 = 去申請 free key · ❌ = 壞咗要 fix/換 · ⚠️ = 要查。Fix 完 re-run \`bash health-check.sh\` 確認。"
  fi
  echo ""
  echo "## 🌐 Browser session (agent Chrome) — the 403-bypass path"
  echo ""
  echo "Reddit, Quora, LinkedIn, 小紅書 and friends 403 / login-wall plain \`curl\`."
  echo "The working path is running the request **inside** the logged-in agent Chrome:"
  echo ""
  echo '```bash'
  echo "python3 ~/.local/bin/agent-chrome.py fetch 'https://www.reddit.com/r/<sub>/search.json?q=<q>&restrict_sr=on&sort=relevance&limit=25'"
  echo "python3 ~/.local/bin/agent-chrome.py fetch 'https://www.reddit.com/r/<sub>/comments/<id>/.json?limit=500'   # full comment tree"
  echo '```'
  echo ""
  echo "A ❌ row is a maintenance lead, not permission to silently skip the source later."
  echo "The real research retrieval must still report its own MATERIAL / EMPTY / FAILED result."
  echo ""
  echo "| Status | Check | HTTP | Note |"
  echo "|--------|-------|------|------|"
  printf '%s\n' "${browser[@]:-}" | sed '/^$/d; s/^/| /; s/ | /| /g; s/$/ |/'
  echo ""
  echo "Full E2E suite: \`bash qa/agent-chrome-qa.sh\` (14 assertions)"
  echo ""
  echo "## 🔑 Keyed APIs (real-key probe)"
  echo ""
  if [[ ${#emptykeys[@]} -gt 0 ]]; then
    echo "> ⚠️ **keys.env 有 ${#emptykeys[@]} 個 key 聲明咗但係空**（\`FOO=\` 後面冇嘢）："
    echo "> \`${emptykeys[*]}\`"
    echo ">"
    echo "> 空 key 唔會報錯 — 佢會照樣帶住空 credential 出 request，收到 401 睇落似「key 過期」，"
    echo "> 其實係根本冇 key。填返或者刪走。"
    echo ""
  fi
  echo "用 keys.env 真 key 打。✅ = key verified working；🔑 = 未有 key；❌ = key 唔 work。"
  echo ""
  echo "| Status | API | HTTP | Note |"
  echo "|--------|-----|------|------|"
  if [[ ${#keyed[@]} -eq 0 ]]; then
    echo "| ⏭️ | keyed inventory | — | not run in $MODE mode |"
  else
    printf '%s\n' "${keyed[@]}" | sed '/^$/d; s/^/| /; s/ | /| /g; s/$/ |/'
  fi
  echo ""
  echo "## Zero-key free APIs"
  echo ""
  echo "| Status | Source | HTTP | Note |"
  echo "|--------|--------|------|------|"
  if [[ ${#results[@]} -eq 0 ]]; then
    echo "| ⏭️ | broad inventory | — | not run in $MODE mode |"
  else
    printf '%s\n' "${results[@]}" | sed 's/^/| /; s/ | /| /g; s/$/ |/'
  fi
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
  if [[ ${#mcp_results[@]} -eq 0 ]]; then
    if [[ "$MODE" == "full" ]]; then
      echo "| ⚠️ | live MCP quota probes | — | no supported MCP configuration found in the current HOME |"
    else
      echo "| ⏭️ | live MCP quota probes | — | not run in $MODE mode |"
    fi
  else
    printf '%s\n' "${mcp_results[@]}" | sed '/^$/d; s/^/| /; s/ | /| /g; s/$/ |/'
  fi
  echo ""
  echo "## MCP servers — WHICH ONES YOU ACTUALLY GET DEPENDS ON CWD"
  echo ""
  echo "\`.mcp.json\` is **project-scoped**. A server listed under \`cwd=~/.claude ONLY\`"
  echo "does **not** exist for a session started in \`~\`. Before telling an agent to call"
  echo "\`mcp__foo__bar\`, check the row for the cwd it will actually run in."
  echo ""
  echo "| Loads when | Config file | Servers |"
  echo "|------------|-------------|---------|"
  printf '%s\n' "${mcp_scope[@]:-}" | sed 's/^/| /; s/ | /| /g; s/$/ |/'
  echo ""
  echo "> Rule of thumb: anything not in the **user-global** row is unavailable to a"
  echo "> default session. Prefer Bash (curl / agent-chrome.py) — it is cwd-independent"
  echo "> and costs zero resident RAM."
} > "$REPORT_TMP"
mv "$REPORT_TMP" "$REPORT"
RUN_FINISHED=1

echo ""
echo "Report written to $REPORT"
echo "Broad inventory: PASS=$PASS WARN=$WARN FAIL=$FAIL"
echo "Local/community routes: PASS=$BPASS WARN=$BWARN FAIL=$BFAIL"
echo "Configured keyed/MCP failures: KEYED=$KFAIL MCP=$MFAIL"

if (( FAIL > 0 || BFAIL > 0 || KFAIL > 0 || MFAIL > 0 )); then
  exit 1
fi
