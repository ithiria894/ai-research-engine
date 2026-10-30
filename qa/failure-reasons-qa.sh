#!/usr/bin/env bash
# QA: every social-research.py failure names a ledger reason (spec section 1), so an agent
# can record FAILED/<reason> instead of guessing, and never mistake a failure for EMPTY.
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SR="$ROOT/social-research.py"
PASS=0; FAIL=0
ok()  { printf '  ✓ %s\n' "$1"; PASS=$((PASS+1)); }
bad() { printf '  ✗ %s\n     └─ %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }

echo "T1 HTTP/network mapping"
out=$(python3 - "$SR" <<'EOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("sr", sys.argv[1]); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cases = {429: "rate-limited", 401: "auth-failed", 402: "quota-exhausted", 403: "blocked", 408: "timeout",
         504: "timeout", 500: "unreachable", 503: "unreachable", 404: "error"}
bad = [f"{c}->{m.http_reason(c)} (want {w})" for c, w in cases.items() if m.http_reason(c) != w]
if m.os_reason(TimeoutError("x")) != "timeout": bad.append("TimeoutError")
if m.os_reason(OSError("Connection refused")) != "unreachable": bad.append("OSError")
print("OK" if not bad else "; ".join(bad))
EOF
)
[[ "$out" == "OK" ]] && ok "status codes and exceptions map to ledger reasons" || bad "mapping" "$out"

echo "T2 real failures carry [reason] on stderr"
reason_of() { "$@" 2>&1 >/dev/null | grep -oP '^social-research: \[\K[a-z-]+(?=\])' | head -1; }
r=$(reason_of python3 "$SR" xhs-note abc tok --route tikhub)
[[ "$r" == "unconfigured" ]] && ok "missing TikHub key -> unconfigured" || bad "tikhub key" "got '$r'"
r=$(reason_of python3 "$SR" reddit-search x --subreddit 'a/../b')
[[ "$r" == "error" ]] && ok "bad argument -> error" || bad "bad arg" "got '$r'"
if curl -fsS --max-time 2 http://127.0.0.1:9223/json/version >/dev/null; then
  r=$(reason_of python3 "$SR" xhs-note 000000000000000000000000 faketoken --route browser)
  [[ "$r" == "blocked" || "$r" == "need-login" ]] && ok "unreadable XHS note -> $r" || bad "xhs note" "got '$r'"
else
  printf '  - SKIP XHS note (Agent Chrome not running)\n'
fi
r=$(AGENT_CHROME_DUMMY=1 python3 - "$SR" 2>&1 <<'EOF'
import importlib.util, sys, pathlib
spec = importlib.util.spec_from_file_location("sr", sys.argv[1]); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.AGENT_CHROME = pathlib.Path("/nonexistent/agent-chrome.py")
m.reddit_page("https://www.reddit.com/")
EOF
)
grep -q '\[unconfigured\]' <<<"$r" && ok "missing browser helper -> unconfigured" || bad "helper missing" "$r"

echo; echo "RESULT: $PASS passed, $FAIL failed"
[[ $FAIL == 0 ]]
