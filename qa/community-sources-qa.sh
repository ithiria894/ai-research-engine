#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SOCIAL="$ROOT/social-research.py"
REGISTRY="$ROOT/community-sources.json"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

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

capture() {
  local name=$1 output=$2 error=$3
  shift 3
  if "$@" >"$output" 2>"$error"; then
    return 0
  fi
  printf 'FAIL %s\n' "$name" >&2
  sed -n '1,120p' "$error" >&2
  exit 1
}

check "Python syntax" python3 -m py_compile "$SOCIAL"
check "Registry is valid JSON" jq -e . "$REGISTRY"
check "Registry has unique source ids" jq -e '
  (.sources | length) > 0 and
  ([.sources[].id] | length) == ([.sources[].id] | unique | length)
' "$REGISTRY"
check "Registry stores no credential values" jq -e '
  all(.sources[]; (.access | has("password") | not) and (.access | has("token") | not) and (.access | has("cookie") | not))
' "$REGISTRY"
check "Registered sources store gopass references only" jq -e '
  (.sources[] | select(.id == "the-student-room") | .access |
    .registration_status == "registered_and_activated_2026-10-13" and
    .credential_ref == "gopass://research-engine/community/the-student-room") and
  (.sources[] | select(.id == "blind") | .access |
    .registration_status == "registered_and_verified_2026-10-13" and
    .credential_ref == "gopass://research-engine/community/blind")
' "$REGISTRY"

capture "Phonebook command" "$TMP/sources.json" "$TMP/sources.log" \
  python3 "$SOCIAL" source-list
registry_count=$(jq '.sources | length' "$REGISTRY")
check "Phonebook exposes all sources without routing" jq -e --argjson expected "$registry_count" '
  .type == "source-capability-phonebook" and .count == $expected and
  ([.sources[].id] | index("reddit") != null) and
  ([.sources[].id] | index("onepoint3acres") != null)
' "$TMP/sources.json"

capture "Single-source phonebook command" "$TMP/one-source.json" "$TMP/one-source.log" \
  python3 "$SOCIAL" source-list --source college-confidential
check "Phonebook can inspect one access recipe" jq -e '
  .count == 1 and .sources[0].access.account == "not_required"
' "$TMP/one-source.json"

capture "Unknown-source phonebook command" "$TMP/missing-source.json" "$TMP/missing-source.log" \
  python3 "$SOCIAL" source-list --source does-not-exist
check "Unknown phonebook id is EMPTY, not FAILED" jq -e '
  .status == "empty" and .count == 0
' "$TMP/missing-source.json"

python3 "$SOCIAL" collegeconf-search 'Eli Whitney Students Program' --limit 3 \
  >"$TMP/cc-search.json" 2>"$TMP/cc-search.log"
check "College Confidential public search API" jq -e '
  .status == "ok" and .route == "public-discourse-json" and .count >= 1
' "$TMP/cc-search.json"

python3 "$SOCIAL" collegeconf-thread \
  'https://talk.collegeconfidential.com/t/yale-eli-whitney-program-2025/3678521' \
  --max-posts 25 >"$TMP/cc-thread.json" 2>"$TMP/cc-thread.log"
check "College Confidential URL parser ignores year in slug" jq -e '
  .topic_id == 3678521 and .loaded_posts == 25 and .posts[0].text != ""
' "$TMP/cc-thread.json"

python3 "$SOCIAL" bctransfer-institutions --query UBCV --limit 1 \
  >"$TMP/bc-institutions.json" 2>"$TMP/bc-institutions.log"
check "BC Transfer Guide institution API" jq -e '
  .status == "ok" and .route == "official-public-api" and
  .data[0].code == "UBCV" and .data[0].id == 27
' "$TMP/bc-institutions.json"

python3 "$SOCIAL" bctransfer-subjects 27 --sending false \
  >"$TMP/bc-subjects.json" 2>"$TMP/bc-subjects.log"
check "BC Transfer Guide subject API" jq -e '
  .status == "ok" and any(.data[]; .code == "CPSC_V" and .title == "Computer Science")
' "$TMP/bc-subjects.json"

if curl -fsS --max-time 2 http://127.0.0.1:9223/json/version >/dev/null; then
  python3 "$SOCIAL" studentroom-thread 7507123 --max-posts 3 \
    >"$TMP/tsr-thread.json" 2>"$TMP/tsr-thread.log"
  check "The Student Room public thread via Agent Chrome" jq -e '
    .status == "ok" and .route == "public-thread-via-agent-chrome" and
    .thread_id == 7507123 and .loaded_posts == 3 and .posts[0].text != ""
  ' "$TMP/tsr-thread.json"
else
  printf 'SKIP The Student Room route (Agent Chrome is not running)\n'
fi

printf 'PASS total=%d\n' "$pass"
