#!/usr/bin/env bash
# E2E QA for ~/.local/bin/agent-chrome.py — the browser-session fetch path that the
# deep-research skill depends on for Reddit and other login-gated / 403-ing sites.
#
# Written from the perspective of a research agent that just wants data:
# "I ran the command. Did I get real content, or did it silently hand me nothing?"
#
# Run:  bash ~/MyGithub/ai-research-engine/qa/agent-chrome-qa.sh
# Exit: 0 = all pass, 1 = at least one failure (details printed).

set -uo pipefail
AC="python3 $HOME/.local/bin/agent-chrome.py"
PASS=0; FAIL=0
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31m✗\033[0m %s\n     └─ %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

head_ "T0 — Chrome reachable"
if $AC list >"$TMP/list" 2>"$TMP/list.err"; then
  ok "list works ($(wc -l <"$TMP/list") tabs)"
else
  bad "list failed" "$(cat "$TMP/list.err")"
  echo "Chrome is not up — remaining tests cannot run."; exit 1
fi

head_ "T1 — backwards compatibility (existing callers must not break)"
$AC --help  >/dev/null 2>&1 && ok "--help"            || bad "--help" "non-zero exit"
$AC list    >/dev/null 2>&1 && ok "list"               || bad "list" "non-zero exit"

head_ "T2 — THE REGRESSION: async JS must not silently return {}"
# This is the exact defect: Runtime.evaluate without awaitPromise resolved to {}
# for every `await fetch(...)`, so agents concluded "browser route unavailable".
out=$($AC eval active 'Promise.resolve("PROMISE_RESOLVED")' 2>&1)
if [[ "$out" == "PROMISE_RESOLVED" ]]; then
  ok "awaited promise returns its value (got: $out)"
else
  bad "awaited promise" "expected PROMISE_RESOLVED, got: $out"
fi

head_ "T3 — Reddit search through the logged-in session (the headline use case)"
# Since 2026-10-30 Reddit answers /search.json with "blocked by network security"
# (403) even inside the logged-in session; the shreddit search partial still works.
SOCIAL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/social-research.py"
if python3 "$SOCIAL" reddit-search quantization --subreddit LocalLLaMA --limit 10 \
     >"$TMP/search.json" 2>"$TMP/search.err"; then
  n=$(jq -r '.count' "$TMP/search.json" 2>/dev/null || echo 0)
  lex=$(jq -r '.lexical_match_count' "$TMP/search.json" 2>/dev/null || echo 0)
  nulls=$(jq '[.items[] | select(.id == null or .title == null or .score == null or .permalink == null)] | length' "$TMP/search.json")
  if [[ "${n:-0}" -ge 10 && "${lex:-0}" -ge 1 && "$nulls" == "0" ]]; then
    ok "reddit-search returned $n posts over $(jq -r .pages_fetched "$TMP/search.json") pages, $lex literal matches, 0 null core fields"
  else
    bad "reddit-search result incomplete" "count=$n lexical=$lex null_core_fields=$nulls"
  fi
else
  bad "reddit-search" "$(tail -3 "$TMP/search.err")"
fi

if python3 "$SOCIAL" reddit-search quantization --subreddit LocalLLaMA --type comments --limit 5 \
     >"$TMP/csearch.json" 2>"$TMP/csearch.err"; then
  nb=$(jq '[.items[] | select(.body == null or .author == null)] | length' "$TMP/csearch.json")
  [[ "$(jq -r .count "$TMP/csearch.json")" -ge 1 && "$nb" == "0" ]] \
    && ok "comment search: $(jq -r .count "$TMP/csearch.json") comments with author + body" \
    || bad "comment search incomplete" "$(head -c 200 "$TMP/csearch.json")"
else
  bad "comment search" "$(tail -3 "$TMP/csearch.err")"
fi

head_ "T3b — a no-match query must NOT look like results"
python3 "$SOCIAL" reddit-search zqxjvkwpqz9187xq --subreddit LocalLLaMA --limit 5 >"$TMP/nomatch.json" 2>/dev/null
st=$(jq -r .status "$TMP/nomatch.json" 2>/dev/null)
[[ "$st" == "empty" || "$st" == "no_lexical_match" ]] \
  && ok "nonsense query reports status=$st (Reddit's padded results are flagged, not counted)" \
  || bad "nonsense query" "status=$st — padded semantic results would be read as real hits"

head_ "T4 — CONTROL: legacy search.json is blocked (re-evaluate the route if this flips)"
if $AC fetch 'https://www.reddit.com/r/LocalLLaMA/search.json?q=quantization&restrict_sr=on&limit=5' >/dev/null 2>&1; then
  ok "NOTE: search.json works again in the browser session — reddit-search may be simplified"
else
  ok "search.json still blocked in-session — reddit-search (shreddit) route is required"
fi
code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 \
  'https://www.reddit.com/r/LocalLLaMA/search.json?q=quantization&limit=5')
ok "plain curl search.json: HTTP $code"

head_ "T5 — full comment tree (depth is the whole point)"
pid=$(jq -r '.items[0].id' "$TMP/search.json" 2>/dev/null | sed 's/^t3_//')
sub=$(jq -r '.items[0].subreddit' "$TMP/search.json" 2>/dev/null)
if [[ -n "${pid:-}" && "$pid" != "null" ]]; then
  if $AC fetch "https://www.reddit.com/r/$sub/comments/$pid/.json?limit=200" \
       --out "$TMP/tree.json" 2>"$TMP/tree.err"; then
    c=$(jq -r '.[1].data.children | length' "$TMP/tree.json" 2>/dev/null || echo 0)
    bytes=$(wc -c <"$TMP/tree.json")
    t_search=$(jq -r '.items[0].title' "$TMP/search.json"); t_tree=$(jq -r '.[0].data.children[0].data.title' "$TMP/tree.json")
    if [[ "${c:-0}" -ge 1 && "$t_search" == "$t_tree" ]]; then
      ok "comment tree: $c top-level comments, $bytes bytes; title matches search result"
    else
      bad "comment tree empty or mismatched" "comments=$c search_title=$t_search tree_title=$t_tree"
    fi
  else
    bad "comment tree fetch" "$(cat "$TMP/tree.err")"
  fi
else
  bad "comment tree" "no post id from T3 to drill into"
fi

head_ "T5b — XHS note detail must never report an unreadable note as ok"
# 2026-10-30 regression: a missing note redirected to /explore and an empty placeholder
# entry came back as status ok (exit 0). It must now exit non-zero with no stdout.
python3 "$SOCIAL" xhs-note 000000000000000000000000 faketoken --route browser >"$TMP/xhs.out" 2>"$TMP/xhs.err"
xc=$?
if [[ "$xc" != "0" && ! -s "$TMP/xhs.out" ]]; then
  ok "missing note exits $xc with no data ($(tail -1 "$TMP/xhs.err" | cut -c1-70))"
else
  bad "missing note looked like data" "exit=$xc stdout=$(head -c 120 "$TMP/xhs.out")"
fi
python3 "$SOCIAL" xhs-note abc ' ' >/dev/null 2>&1 && bad "blank xsec_token accepted" "exit 0" \
  || ok "blank xsec_token rejected"

head_ "T6 — failures must be LOUD (exit != 0), never a silent empty result"
if $AC fetch 'https://www.reddit.com/r/thissubdoesnotexist_qa12345/about.json' >/dev/null 2>"$TMP/404.err"; then
  bad "HTTP 404 handling" "exited 0 on a 404 — agents will treat this as 'no data found'"
else
  ok "HTTP error exits non-zero ($(head -c 90 "$TMP/404.err" | tr '\n' ' '))"
fi

if $AC eval active 'throw new Error("QA_BOOM")' >/dev/null 2>"$TMP/js.err"; then
  bad "JS exception handling" "exited 0 despite a thrown error"
else
  grep -q "QA_BOOM" "$TMP/js.err" && ok "JS exception surfaced + exit != 0" \
                                  || bad "JS exception" "exit != 0 but message lost: $(cat "$TMP/js.err")"
fi

head_ "T7 — cross-origin fetch fails loudly (must not look like 'no results')"
# reddit tab fetching example.com: CORS should block it and we must SAY so.
opened_reddit=0
if ! $AC list | grep -qi reddit; then
  $AC open 'https://www.reddit.com/' >/dev/null 2>&1
  opened_reddit=1
fi
if $AC eval reddit '(async()=>{try{const r=await fetch("https://example.com/");return "UNEXPECTED_OK_"+r.status}catch(e){return "CORS_BLOCKED"}})()' 2>&1 | grep -qE 'CORS_BLOCKED|UNEXPECTED_OK'; then
  ok "cross-origin behaviour is observable (not a silent {})"
else
  bad "cross-origin" "no observable result"
fi
[[ "$opened_reddit" == 1 ]] && $AC close reddit >/dev/null 2>&1

head_ "T8 — js from file and stdin (avoids shell-quoting hell for agents)"
echo 'JSON.stringify({from:"file"})' > "$TMP/x.js"
[[ "$($AC eval active "@$TMP/x.js" 2>&1)" == '{"from":"file"}' ]] && ok "eval @file" || bad "eval @file" "unexpected output"
[[ "$(echo 'JSON.stringify({from:"stdin"})' | $AC eval active - 2>&1)" == '{"from":"stdin"}' ]] && ok "eval - (stdin)" || bad "eval - (stdin)" "unexpected output"

head_ "T9 — login-check reports honestly"
lc=$($AC login-check 'https://www.reddit.com/' 2>&1); rc=$?
case "$lc" in
  in*)      ok "reddit: LOGGED IN — $lc" ;;
  out*)     ok "reddit: logged OUT, correctly reported (exit $rc) — $lc" ;;
  unknown*) ok "reddit: unknown, honestly reported — $lc" ;;
  *)        bad "login-check" "unparseable: $lc" ;;
esac

head_ "T10 — tab hygiene: reuse, don't spawn a tab per call"
before=$($AC list | wc -l)
$AC fetch 'https://www.reddit.com/r/LocalLLaMA/about.json' >/dev/null 2>&1
$AC fetch 'https://www.reddit.com/r/programming/about.json' >/dev/null 2>&1
after=$($AC list | wc -l)
if [[ "$after" -le $((before + 1)) ]]; then
  ok "tab count $before -> $after (reuses the origin tab)"
else
  bad "tab hygiene" "tab count grew $before -> $after; agents will flood the browser"
fi

head_ "T11 — open_tab keeps the whole URL (& # %20 %26 + must survive /json/new)"
# 2026-10-30: /json/new truncated at a raw "&", so "&limit=2" or XHS "&xsec_source=" vanished silently.
ot=$(python3 - <<'EOF' 2>&1
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("ac", pathlib.Path.home() / ".local/bin/agent-chrome.py")
ac = importlib.util.module_from_spec(spec); spec.loader.exec_module(ac)
u = "https://example.com/p?q=a%20b&v=x%26y&w=c+d&limit=2#frag"
t = ac.open_tab(u, wait=False); got = t.info["url"]; t.close(); ac.http_text("/json/close/" + t.info["id"])
print("SAME" if got == u else "GOT " + got)
EOF
)
if [[ "$ot" == "SAME" ]]; then
  ok "URL with & # %20 %26 + opened byte-for-byte"
else
  bad "open_tab URL" "$ot"
fi

printf '\n\033[1mRESULT: %d passed, %d failed\033[0m\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
