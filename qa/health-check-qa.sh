#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HEALTH="$ROOT/health-check.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
REPORT="$TMP/health-check-report.md"
export HEALTH_CHECK_REPORT="$REPORT"

pass=0
check() {
  local name=$1
  shift
  if "$@" >/dev/null; then
    printf 'PASS %s\n' "$name"
    pass=$((pass + 1))
  else
    printf 'FAIL %s\n' "$name" >&2
    exit 1
  fi
}

check "Shell syntax" bash -n "$HEALTH"
"$HEALTH" --help >"$TMP/help"
check "Help documents targeted and maintenance modes" grep -q -- '--source ID' "$TMP/help"
check "Help warns that full mode can spend quota" grep -q -- 'consume limited API/MCP quota' "$TMP/help"

printf 'SENTINEL\n' >"$REPORT"
if "$HEALTH" --source does-not-exist >"$TMP/unknown.out" 2>"$TMP/unknown.err"; then
  printf 'FAIL Unknown source should return non-zero\n' >&2
  exit 1
fi
check "Unknown source is named" grep -q 'unknown source id: does-not-exist' "$TMP/unknown.err"
check "Argument errors preserve the last valid report" grep -q '^SENTINEL$' "$REPORT"

if SOCIAL="$TMP/missing-social-research.py" "$HEALTH" --source college-confidential \
    >"$TMP/missing.out" 2>"$TMP/missing.err"; then
  printf 'FAIL Missing selected adapter should return non-zero\n' >&2
  exit 1
fi
check "Missing adapter is reported explicitly" grep -q 'College Confidential adapter.*MISSING' "$REPORT"
check "Failed completed check remains a completed report" grep -q '^> Mode: quick$' "$REPORT"

start=$SECONDS
"$HEALTH" --source college-confidential >"$TMP/selected.out" 2>"$TMP/selected.err"
elapsed=$((SECONDS - start))
check "Selected-source mode is recorded" grep -q '^> Selected sources: college-confidential$' "$REPORT"
check "Selected public route returns data" grep -q 'College Confidential public Discourse API.*search result' "$REPORT"
check "Selected-source check stays bounded" test "$elapsed" -le 45

start=$SECONDS
"$HEALTH" >"$TMP/quick.out" 2>"$TMP/quick.err"
elapsed=$((SECONDS - start))
check "Quick mode is recorded" grep -q '^> Mode: quick$' "$REPORT"
check "Quick mode skips broad inventory" grep -q 'broad inventory.*not run in quick mode' "$REPORT"
check "Quick mode skips keyed quota probes" grep -q 'keyed inventory.*not run in quick mode' "$REPORT"
check "Quick check stays bounded" test "$elapsed" -le 30

printf 'PASS total=%d\n' "$pass"
