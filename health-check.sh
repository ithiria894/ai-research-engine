#!/usr/bin/env bash
# Research Engine Health Check + Repair Triage
# Tests: (1) zero-key free APIs, (2) keyed APIs with REAL keys from keys.env,
# (3) MCP liveness with real keys (quota-death detection), (4) CLIs.
# Writes a timestamped report that, for every failure, TELLS you how to fix it
# (⚠️ ACTION NEEDED section), so research agents skip dead tools instead of
# silently fetching nothing.
#
# Usage: bash health-check.sh
# Keys:  ~/.config/research-engine/keys.env (sourced if present)
# Output: health-check-report.md (in this dir)

set -uo pipefail
REPORT="$(dirname "$0")/health-check-report.md"
TIMEOUT=25          # per-try ceiling; crt.sh / S2 are slow, give them room
CONNECT_TIMEOUT=10
PASS=0; FAIL=0; WARN=0
CLAUDE_CFG="$HOME/.claude.json"

# Load obtained API keys so keyed APIs get a REAL probe (not just "needs key").
KEYS_FILE="$HOME/.config/research-engine/keys.env"
if [[ -f "$KEYS_FILE" ]]; then set -a; source "$KEYS_FILE" 2>/dev/null; set +a; fi

# Each test: name | method | url | extra-curl-args | expect-substring (optional)
# We check HTTP 2xx AND a non-empty plausible body.
results=()
keyed=()       # real-key probe rows
actions=()     # ⚠️ ACTION NEEDED triage: each = "icon|what|how-to-fix"

# Record a repair action (shown at top of report so the check TELLS you the fix).
act(){ actions+=("$1"); }

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
check "Wikimedia Pageviews"     "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/2026/05/01"

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

# ── Keyed-API real-key probe (Round 14) ──────────────────────────────
# CONNECTED ≠ USABLE for key-gated APIs too. Now that we hold real keys
# (keys.env), hit each with its actual key so the report shows ✅ verified
# instead of a dormant "needs key". Empty key → ➖ + an ACTION to go get it.
kcheck(){  # name | keyvar | success-grep | curl-args...
  local name="$1" kv="$2" ok="$3"; shift 3
  local key="${!kv:-}" tmp code
  if [[ -z "$key" ]]; then
    keyed+=("🔑 | $name | — | no key set")
    act "🔑|$name 未有 key|申請 free key 填入 ~/.config/research-engine/keys.env（見 engine「🔑 Key Activation Checklist」）"
    return
  fi
  tmp=$(mktemp)
  code=$(curl -s --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" --retry 2 --retry-delay 2 \
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
echo "Probing keyed APIs with real keys..."
kcheck "FRED"          FRED_API_KEY          "observations" "https://api.stlouisfed.org/fred/series/observations?series_id=GDP&api_key=${FRED_API_KEY:-}&file_type=json&limit=1"
kcheck "US Census"     CENSUS_API_KEY        "NAME"         "https://api.census.gov/data/2021/acs/acs5?get=NAME&for=state:06&key=${CENSUS_API_KEY:-}"
kcheck "Open PageRank" OPENPAGERANK_API_KEY  "page_rank"    "https://openpagerank.com/api/v1.0/getPageRank?domains%5B%5D=google.com" -H "API-OPR: ${OPENPAGERANK_API_KEY:-}"
kcheck "FMP"           FMP_API_KEY           "symbol"       "https://financialmodelingprep.com/stable/quote?symbol=AAPL&apikey=${FMP_API_KEY:-}"
kcheck "OpenStates"    OPENSTATES_API_KEY    "results"      "https://v3.openstates.org/jurisdictions?per_page=1" -H "X-API-Key: ${OPENSTATES_API_KEY:-}"
kcheck "OpenSanctions" OPENSANCTIONS_API_KEY "results"      "https://api.opensanctions.org/search/default?q=test&limit=1" -H "Authorization: ApiKey ${OPENSANCTIONS_API_KEY:-}"
kcheck "Congress.gov"  CONGRESS_API_KEY      "bills"        "https://api.congress.gov/v3/bill?api_key=${CONGRESS_API_KEY:-}&format=json&limit=1"
kcheck "govinfo"       GOVINFO_API_KEY       "collection"   "https://api.govinfo.gov/collections?api_key=${GOVINFO_API_KEY:-}"
kcheck "OpenFEC"       OPENFEC_API_KEY       "results"      "https://api.open.fec.gov/v1/candidates/?api_key=${OPENFEC_API_KEY:-}&per_page=1"
kcheck "Finnhub"       FINNHUB_API_KEY       "c"            "https://finnhub.io/api/v1/quote?symbol=AAPL&token=${FINNHUB_API_KEY:-}"

# ── Browser session (agent Chrome) — the 403-bypass path ─────────────
# Reddit / Quora / LinkedIn / 小紅書 all 403 or login-wall plain curl. The ONLY
# reliable path is running the request inside the logged-in agent Chrome. This
# section exists because that path was invisible to the health check for months
# while it was silently broken — agents "found nothing" and nobody could tell.
browser=()
bact(){ browser+=("$1"); }
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
    pr=$(timeout 40 python3 "$AC" eval active 'Promise.resolve("AWAIT_OK")' 2>&1 | tail -1)
    if [[ "$pr" == "AWAIT_OK" ]]; then
      bact "✅ | CDP awaitPromise | — | async JS resolves (no silent {})"
    else
      bact "❌ | CDP awaitPromise | — | async JS returned '$pr' — every fetch will look empty"
      act "❌|agent-chrome.py eval 唔 await promise|所有 browser fetch 會靜靜哋回 {}。加返 awaitPromise:True 落 Runtime.evaluate"
    fi

    # End-to-end: real Reddit search through the session, and the curl control.
    tmpb=$(mktemp)
    if timeout 90 python3 "$AC" fetch \
        'https://www.reddit.com/r/LocalLLaMA/search.json?q=llm&restrict_sr=on&sort=top&limit=3' \
        --out "$tmpb" >/dev/null 2>&1; then
      n=$(jq -r '.data.children | length' "$tmpb" 2>/dev/null || echo 0)
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
      lc=$(timeout 60 python3 "$AC" login-check "$site" 2>&1 | tail -1)
      case "$lc" in
        in*)  bact "✅ | login: $site | — | ${lc#in	}";;
        out*) bact "❌ | login: $site | — | LOGGED OUT — ${lc#out	}"
              act "❌|Reddit 未登入|喺 agent Chrome (port $CDP_PORT) 手動登入一次，session 會 persist";;
        *)    bact "⚠️ | login: $site | — | $lc";;
      esac
    done
  fi
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
  echo "python3 ~/.local/bin/agent-chrome.py fetch 'https://www.reddit.com/r/<sub>/search.json?q=<q>&restrict_sr=on&sort=top&limit=25'"
  echo "python3 ~/.local/bin/agent-chrome.py fetch 'https://www.reddit.com/r/<sub>/comments/<id>/.json?limit=500'   # full comment tree"
  echo '```'
  echo ""
  echo "If any row below is ❌, an agent doing forum research will come back with"
  echo "\"found nothing\" — which is a DEAD TOOL, not evidence of absence. Say so."
  echo ""
  echo "| Status | Check | HTTP | Note |"
  echo "|--------|-------|------|------|"
  printf '%s\n' "${browser[@]:-}" | sed '/^$/d; s/^/| /; s/ | /| /g; s/$/ |/'
  echo ""
  echo "Full E2E suite: \`bash qa/agent-chrome-qa.sh\` (14 assertions)"
  echo ""
  echo "## 🔑 Keyed APIs (real-key probe)"
  echo ""
  echo "用 keys.env 真 key 打。✅ = key verified working；🔑 = 未有 key；❌ = key 唔 work。"
  echo ""
  echo "| Status | API | HTTP | Note |"
  echo "|--------|-----|------|------|"
  printf '%s\n' "${keyed[@]:-}" | sed '/^$/d; s/^/| /; s/ | /| /g; s/$/ |/'
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
} > "$REPORT"

echo ""
echo "Report written to $REPORT"
echo "Summary: PASS=$PASS WARN=$WARN FAIL=$FAIL"
