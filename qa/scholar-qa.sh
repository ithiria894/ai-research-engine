#!/usr/bin/env bash
# QA for scholar.py (spec section 5): merged scholarly search, retraction flags, legal full text.
# Live tests hit free public APIs; T0 is offline so merge logic is checked even if an API is down.
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SC="python3 $ROOT/scholar.py"
PASS=0; FAIL=0
ok()  { printf '  ✓ %s\n' "$1"; PASS=$((PASS+1)); }
bad() { printf '  ✗ %s\n     └─ %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "T0 offline merge"
out=$(python3 - "$ROOT/scholar.py" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("s", sys.argv[1]); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
merged = m.merge({
  "openalex": [{"title": "Paper A", "year": 2020, "doi": "10.1/a", "citations": 5, "is_retracted": True}],
  "crossref": [{"title": "Paper A", "year": 2020, "doi": "10.1/A", "citations": 9}],
  "arxiv":    [{"title": "Paper  B!", "year": 2021, "doi": None, "oa_url": "https://arxiv.org/pdf/1"}],
  "europe-pmc": [{"title": "paper b", "year": 2021, "doi": None}],
})
a = next(w for w in merged if w["title"] == "Paper A"); b = next(w for w in merged if w["title"] != "Paper A")
checks = [len(merged) == 2, a["sources"] == ["openalex", "crossref"], a["citations"] == 9,
          a["is_retracted"] is True, b["sources"] == ["arxiv", "europe-pmc"], b["oa_url"]]
print("OK" if all(checks) else f"FAIL {checks} {merged}")
PY
)
[[ "$out" == OK ]] && ok "DOI case-insensitive merge, title+year merge, max citations, retraction kept" || bad "merge" "$out"
python3 -c "import importlib.util,sys;s=importlib.util.spec_from_file_location('s','$ROOT/scholar.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);assert m.norm_doi('https://doi.org/10.1/X')=='10.1/x' and m.norm_doi('doi:10.2/Y')=='10.2/y'" \
  && ok "DOI normalisation strips doi.org / doi: prefixes" || bad "norm_doi" "failed"

echo "T1 live search"
$SC search "relative citation ratio" --limit 5 >"$TMP/s.json" 2>/dev/null; rc=$?
[[ $rc == 0 ]] && ok "search exits 0" || bad "search exit" "$rc"
jq -e '[.ledger[].source] | index("openalex") and index("crossref") and index("semantic-scholar") and index("arxiv") and index("europe-pmc") and index("openalex-retraction")' "$TMP/s.json" >/dev/null \
  && ok "ledger lists all five providers + retraction check" || bad "ledger providers" "$(jq -c '[.ledger[].source]' "$TMP/s.json")"
jq -e 'all(.ledger[]; (.status|IN("MATERIAL","EMPTY","FAILED","SKIPPED")) and (if .status=="FAILED" then (.reason|type)=="string" else true end))' "$TMP/s.json" >/dev/null \
  && ok "every ledger row uses the spec vocabulary; FAILED rows carry a reason" || bad "ledger vocab" "$(jq -c .ledger "$TMP/s.json")"
jq -e '.count > 0 and any(.works[]; (.sources|length) >= 2)' "$TMP/s.json" >/dev/null \
  && ok "results merged across providers ($(jq .count "$TMP/s.json") works)" || bad "merge live" "$(jq -c '.count' "$TMP/s.json")"

echo "T2 retraction"
$SC retraction "10.1016/S0140-6736(97)11096-0" "10.1371/journal.pbio.1002541" >"$TMP/r.json" 2>/dev/null
jq -e '.results["10.1016/s0140-6736(97)11096-0"] == true and .results["10.1371/journal.pbio.1002541"] == false' "$TMP/r.json" >/dev/null \
  && ok "Wakefield 1998 flagged retracted; RCR paper not" || bad "retraction" "$(jq -c .results "$TMP/r.json")"
$SC search "ileal-lymphoid-nodular hyperplasia non-specific colitis pervasive developmental disorder" --limit 5 >"$TMP/w.json" 2>/dev/null
jq -e '.retracted_count >= 1' "$TMP/w.json" >/dev/null && ok "search surfaces the retraction flag ($(jq .retracted_count "$TMP/w.json") retracted)" || bad "search retraction" "$(jq -c '[.works[] | {title: .title[:40], is_retracted}]' "$TMP/w.json")"

echo "T3 full text"
env -u RESEARCH_CONTACT_EMAIL $SC fulltext "10.1371/journal.pbio.1002541" >"$TMP/f.json" 2>/dev/null
jq -e '.fulltext.url | test("^https://")' "$TMP/f.json" >/dev/null && ok "OA paper resolves to a full-text URL via $(jq -r .fulltext.via "$TMP/f.json")" || bad "fulltext" "$(jq -c . "$TMP/f.json")"
jq -e 'any(.ledger[]; .source=="unpaywall" and .status=="SKIPPED" and .reason=="unconfigured")' "$TMP/f.json" >/dev/null \
  && ok "Unpaywall is SKIPPED/unconfigured without a contact email (no address invented)" || bad "unpaywall gate" "$(jq -c .ledger "$TMP/f.json")"
$SC search "  " >/dev/null 2>&1 && bad "empty query accepted" "exit 0" || ok "empty query refused"

echo; echo "RESULT: $PASS passed, $FAIL failed"
[[ $FAIL == 0 ]]
