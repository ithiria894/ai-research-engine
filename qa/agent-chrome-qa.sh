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
out=$($AC eval reddit 'Promise.resolve("PROMISE_RESOLVED")' 2>&1)
if [[ "$out" == "PROMISE_RESOLVED" ]]; then
  ok "awaited promise returns its value (got: $out)"
else
  bad "awaited promise" "expected PROMISE_RESOLVED, got: $out"
fi

head_ "T3 — Reddit search through the logged-in session (the headline use case)"
if $AC fetch 'https://www.reddit.com/r/LocalLLaMA/search.json?q=quantization&restrict_sr=on&sort=top&limit=5' \
     --out "$TMP/search.json" 2>"$TMP/search.err"; then
  n=$(jq -r '.data.children | length' "$TMP/search.json" 2>/dev/null || echo 0)
  if [[ "${n:-0}" -ge 1 ]]; then
    ok "search.json returned $n posts (first: $(jq -r '.data.children[0].data.title' "$TMP/search.json" | cut -c1-50))"
  else
    bad "search.json parsed but empty" "$(head -c 200 "$TMP/search.json")"
  fi
else
  bad "search.json fetch" "$(cat "$TMP/search.err")"
fi

head_ "T4 — CONTROL: the same URL via plain curl must still fail"
# If this ever starts passing, the browser route is no longer load-bearing — good to know.
code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 \
  'https://www.reddit.com/r/LocalLLaMA/search.json?q=quantization&limit=5')
if [[ "$code" == "403" || "$code" == "429" || "$code" == "000" ]]; then
  ok "plain curl blocked (HTTP $code) — browser route is genuinely required"
else
  ok "plain curl now returns HTTP $code — NOTE: re-evaluate whether browser is still needed"
fi

head_ "T5 — full comment tree (depth is the whole point)"
pid=$(jq -r '.data.children[0].data.id' "$TMP/search.json" 2>/dev/null)
sub=$(jq -r '.data.children[0].data.subreddit' "$TMP/search.json" 2>/dev/null)
if [[ -n "${pid:-}" && "$pid" != "null" ]]; then
  if $AC fetch "https://www.reddit.com/r/$sub/comments/$pid/.json?limit=200" \
       --out "$TMP/tree.json" 2>"$TMP/tree.err"; then
    c=$(jq -r '.[1].data.children | length' "$TMP/tree.json" 2>/dev/null || echo 0)
    bytes=$(wc -c <"$TMP/tree.json")
    if [[ "${c:-0}" -ge 1 ]]; then
      ok "comment tree: $c top-level comments, $bytes bytes"
    else
      bad "comment tree empty" "$(head -c 200 "$TMP/tree.json")"
    fi
  else
    bad "comment tree fetch" "$(cat "$TMP/tree.err")"
  fi
else
  bad "comment tree" "no post id from T3 to drill into"
fi

head_ "T6 — failures must be LOUD (exit != 0), never a silent empty result"
if $AC fetch 'https://www.reddit.com/r/thissubdoesnotexist_qa12345/about.json' >/dev/null 2>"$TMP/404.err"; then
  bad "HTTP 404 handling" "exited 0 on a 404 — agents will treat this as 'no data found'"
else
  ok "HTTP error exits non-zero ($(head -c 90 "$TMP/404.err" | tr '\n' ' '))"
fi

if $AC eval reddit 'throw new Error("QA_BOOM")' >/dev/null 2>"$TMP/js.err"; then
  bad "JS exception handling" "exited 0 despite a thrown error"
else
  grep -q "QA_BOOM" "$TMP/js.err" && ok "JS exception surfaced + exit != 0" \
                                  || bad "JS exception" "exit != 0 but message lost: $(cat "$TMP/js.err")"
fi

head_ "T7 — cross-origin fetch fails loudly (must not look like 'no results')"
# reddit tab fetching example.com: CORS should block it and we must SAY so.
if $AC eval reddit '(async()=>{try{const r=await fetch("https://example.com/");return "UNEXPECTED_OK_"+r.status}catch(e){return "CORS_BLOCKED"}})()' 2>&1 | grep -qE 'CORS_BLOCKED|UNEXPECTED_OK'; then
  ok "cross-origin behaviour is observable (not a silent {})"
else
  bad "cross-origin" "no observable result"
fi

head_ "T8 — js from file and stdin (avoids shell-quoting hell for agents)"
echo 'JSON.stringify({from:"file"})' > "$TMP/x.js"
[[ "$($AC eval reddit "@$TMP/x.js" 2>&1)" == '{"from":"file"}' ]] && ok "eval @file" || bad "eval @file" "unexpected output"
[[ "$(echo 'JSON.stringify({from:"stdin"})' | $AC eval reddit - 2>&1)" == '{"from":"stdin"}' ]] && ok "eval - (stdin)" || bad "eval - (stdin)" "unexpected output"

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

printf '\n\033[1mRESULT: %d passed, %d failed\033[0m\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
