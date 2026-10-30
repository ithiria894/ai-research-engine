#!/usr/bin/env bash
# QA for library.py (spec section 8): past runs searchable in English, Chinese and Korean;
# the DB is a rebuildable cache of run folders.
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export RESEARCH_RUNS_DIR=$(mktemp -d) RESEARCH_LIBRARY_DB=$(mktemp -u --suffix=.sqlite)
trap 'rm -rf "$RESEARCH_RUNS_DIR" "$RESEARCH_LIBRARY_DB"' EXIT
RR="python3 $ROOT/research_run.py"; LB="python3 $ROOT/library.py"
PASS=0; FAIL=0
ok()  { printf '  ✓ %s\n' "$1"; PASS=$((PASS+1)); }
bad() { printf '  ✗ %s\n     └─ %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }
hits() { $LB search "$1" 2>/dev/null | jq -r '.count'; }

$LB search anything >/dev/null 2>&1 && bad "search before index" "exit 0" || ok "search before any index explains itself and exits 1"
A=$($RR init scar-clinics --query "韓國鼻翼疤痕修復邊間診所好？" 2>/dev/null)
printf '콧볼축소 흉터 재수술 후기: 6개월 기다려야 한다' | $RR add "$A" --source naver >/dev/null 2>&1
printf '# Report\nOuter incision scars fade after twelve months for most patients.\n' > "$A/report.md"
B=$($RR init bc-transfer --query "Which BC colleges transfer CPSC credits to UBC?" 2>/dev/null)
printf '<html><body><p>Langara CPSC 1150 transfers as UBCV CPSC 1st.</p></body></html>' | $RR add "$B" --source bctg --ext html >/dev/null 2>&1

out=$($LB index 2>/dev/null); [[ $(jq .runs <<<"$out") == 2 ]] && ok "index finds both runs" || bad "index" "$out"
[[ $(hits "twelve months") -ge 1 ]] && ok "English phrase in a report" || bad "english" "$(hits 'twelve months')"
[[ $(hits "鼻翼疤痕") -ge 1 ]] && ok "Chinese (no spaces) in the original question" || bad "chinese" "$(hits 鼻翼疤痕)"
[[ $(hits "疤痕") -ge 1 ]] && ok "2-character Chinese term falls back to instr()" || bad "short chinese" "$(hits 疤痕)"
[[ $(hits "재수술") -ge 1 ]] && ok "Korean inside raw evidence" || bad "korean" "$(hits 재수술)"
[[ $(hits "Langara CPSC") -ge 1 ]] && ok "text inside HTML evidence (tags stripped)" || bad "html" "$(hits 'Langara CPSC')"
[[ $(hits "<p>") == 0 ]] && ok "HTML tags themselves are not indexed" || bad "tags indexed" "$(hits '<p>')"
[[ $(hits "quantum blockchain") == 0 ]] && ok "no match returns count 0" || bad "false hit" "$(hits 'quantum blockchain')"
$LB search "鼻翼疤痕" 2>/dev/null | jq -e '.note | test("dated context")' >/dev/null && ok "results are labelled dated context" || bad "label" "missing note"
$LB index >/dev/null 2>&1; [[ $(hits "twelve months") == 1 ]] && ok "re-index is idempotent (no duplicate hits)" || bad "idempotent" "$(hits 'twelve months')"
rm -rf "$B"; $LB index >/dev/null 2>&1; [[ $(hits "Langara CPSC") == 0 && $($LB list 2>/dev/null | jq length) == 1 ]] && ok "deleted run disappears on re-index (DB is only a cache)" || bad "rebuild" "$($LB list 2>/dev/null)"
$LB search "   " >/dev/null 2>&1 && bad "blank query accepted" "exit 0" || ok "blank query refused"

echo; echo "RESULT: $PASS passed, $FAIL failed"
[[ $FAIL == 0 ]]
