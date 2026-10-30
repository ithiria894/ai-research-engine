#!/usr/bin/env bash
# QA for tools/opensanctions.py — local OpenSanctions lookup built from the public bulk CSV.
# Written as a researcher would use it: "I searched a name. Did I get the real record,
# and when something is wrong, does it say why instead of quietly returning nothing?"
#
# Live tests use the installed data ($OPENSANCTIONS_DIR or the default dir).
# Failure-path tests use small offline fixtures in a temp dir.
#
# Run:  bash qa/opensanctions-qa.sh      Exit: 0 = all pass, 1 = a failure

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OS="python3 $ROOT/tools/opensanctions.py"
PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; echo "     └─ $2"; FAIL=$((FAIL+1)); }

echo "T1 first-time user: no data yet"
out=$(OPENSANCTIONS_DIR="$TMP/none" $OS search putin 2>&1 >/dev/null); rc=$?
[[ $rc -ne 0 && "$out" == *"[unconfigured]"* ]] && ok "exit $rc with [unconfigured] and the update hint" || bad "no-data path" "rc=$rc $out"

echo "T2 live search on installed data"
if $OS status >/dev/null 2>&1; then
  r=$($OS search "Vladimir Putin" --schema Person --limit 3 2>/dev/null)
  first=$(jq -r '.results[0].name' <<<"$r"); ver=$(jq -r '.data_version' <<<"$r")
  [[ "$first" == "Vladimir Putin" && -n "$ver" && "$ver" != null ]] && ok "exact name ranked first, data_version $ver" || bad "known person" "first=$first ver=$ver"
  n=$($OS search "李家超" 2>/dev/null | jq -r '.count')
  [[ "${n:-0}" -ge 1 ]] && ok "CJK alias search ($n hit)" || bad "CJK search" "count=$n"
  n=$($OS search "IMO9422964" 2>/dev/null | jq -r '.count')
  [[ "${n:-0}" -ge 1 ]] && ok "identifier search ($n hit)" || bad "identifier search" "count=$n"
  s=$($OS search "zzqqxxnonexistent" 2>/dev/null | jq -r '.status')
  [[ "$s" == "empty" ]] && ok "no match reports status empty (exit 0)" || bad "empty result" "status=$s"
  a=$($OS search "Yatai" --limit 50 2>/dev/null | jq -r '.count'); b=$($OS search "Yatai" --country mm --limit 50 2>/dev/null | jq -r '.count')
  [[ "${b:-0}" -ge 1 && "${b:-0}" -le "${a:-0}" ]] && ok "country filter narrows ($a -> $b)" || bad "country filter" "all=$a mm=$b"
else
  bad "live data" "no installed data; run: tools/opensanctions.py update"
fi

echo "T3 bad input"
out=$($OS search x --limit 0 2>&1); [[ "$out" == *"--limit must be"* ]] && ok "--limit 0 rejected" || bad "--limit 0" "$out"
out=$($OS search "   " 2>&1);    [[ "$out" == *"must not be empty"* ]] && ok "blank query rejected" || bad "blank query" "$out"

echo "T4 offline: index a small fixture, then search it"
python3 - "$ROOT" "$TMP" <<'EOF' && ok "fixture indexed and searchable (incl. 2-char term)" || bad "fixture index" "see above"
import importlib.util, pathlib, sqlite3, sys
root, tmp = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("os_", root / "tools/opensanctions.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
csv_path = tmp / "t.csv"
csv_path.write_text('"' + '","'.join(m.COLUMNS) + '"\n' + '"id1","Person","Alice Example","Ali Ex","","hk","","P123","","","","","Test list","","",""\n', encoding="utf-8")
m.build_index(csv_path, tmp / "t.sqlite")
con = sqlite3.connect(tmp / "t.sqlite")
assert con.execute("SELECT count(*) FROM names WHERE names MATCH '\"Example\"'").fetchone()[0] == 1
assert con.execute("SELECT count(*) FROM targets WHERE instr(lower(aliases), 'ex') > 0").fetchone()[0] == 1
EOF

echo "T5 offline: changed CSV header is schema-drift, not a silent bad index"
out=$(python3 - "$ROOT" "$TMP" 2>&1 <<'EOF'
import importlib.util, pathlib, sys
root, tmp = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("os_", root / "tools/opensanctions.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
p = tmp / "bad.csv"; p.write_text('"id","name"\n"x","y"\n', encoding="utf-8")
m.build_index(p, tmp / "bad.sqlite")
EOF
); [[ "$out" == *"[schema-drift]"* && ! -e "$TMP/bad.sqlite" ]] && ok "header change -> [schema-drift], no db left behind" || bad "header drift" "$out"

echo "T6 offline: download with wrong checksum is refused and leaves no file"
echo "hello" > "$TMP/src.txt"
out=$(python3 - "$ROOT" "$TMP" 2>&1 <<'EOF'
import importlib.util, pathlib, sys
root, tmp = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("os_", root / "tools/opensanctions.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.download((tmp / "src.txt").as_uri(), tmp / "dl.csv", 6, "0" * 40)
EOF
); [[ "$out" == *"checksum mismatch"* && ! -e "$TMP/dl.csv" && ! -e "$TMP/dl.csv.part" ]] && ok "bad checksum -> refused, no partial file" || bad "checksum" "$out"

echo; echo "RESULT: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
