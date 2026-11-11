#!/usr/bin/env python3
"""QA for forward_snapshot.py against a throw-away root (real ~/data/forward-snapshots untouched).
Hits the network lightly: Polymarket 1 page per board (3 requests) + 1 deliberate 404.
Run: python3 tools/forward_snapshot_qa.py"""
import csv, fcntl, json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import forward_snapshot as fs

tmp = Path(tempfile.mkdtemp(prefix="fsnap-qa-"))
fs.ROOT, fs.LEDGER = tmp, tmp / "LEDGER.tsv"
fs.MAP, fs.DATES = tmp / "youtube/channel_map.tsv", tmp / "youtube_upload_dates/upload_dates.tsv"
fs.PM_PAGES, fs.PM_PAUSE = 1, 1.0
fs.setup_logging("qa")
day = fs.utcnow().strftime("%Y-%m-%d")
ledger = lambda: list(csv.DictReader(fs.LEDGER.open(), delimiter="\t")) if fs.LEDGER.exists() else []
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name, detail)


# 1. low disk -> one FAILED row per selected source, nothing fetched
fs.MIN_FREE_GB = 10**6
rc = fs.cmd_run(["polymarket", "etoro"], False)
rows = ledger()
check("low disk: exit!=0, 2 FAILED rows, no source dirs", rc == 1 and [r["status"] for r in rows] == ["FAILED", "FAILED"]
      and "disk free" in rows[0]["error"] and not (tmp / "polymarket").exists(), rows)
fs.MIN_FREE_GB = 20

# 2. upstream error -> FAILED (never EMPTY), error text kept
real = fs.PM_BASE
fs.PM_BASE = "https://data-api.polymarket.com/v2/no-such-endpoint-qa"
fs.cmd_run(["polymarket"], False)
r = ledger()[-1]
check("404 upstream -> FAILED with http=404 in error", r["status"] == "FAILED" and "http=404" in r["error"], r["error"][:120])

# 3. retry after FAILED: earlier attempt dir kept (renamed), new run OK
fs.PM_BASE = real
fs.cmd_run(["polymarket"], False)
r = ledger()[-1]
attempts = list((tmp / "polymarket").glob(f"{day}.attempt-*"))
man = json.loads((tmp / "polymarket" / day / "MANIFEST.json").read_text())
check("retry -> OK, earlier attempt kept", r["status"] == "OK" and len(attempts) == 1 and man["status"] == "OK", (r["status"], attempts))
check("manifest lists 3 files with sha256", len(man["files"]) == 3 and all(len(f["raw_sha256"]) == 64 for f in man["files"]))
check("ledger manifest_sha256 matches file", r["manifest_sha256"] == fs.hashlib.sha256((tmp / "polymarket" / day / "MANIFEST.json").read_bytes()).hexdigest())

# 4. same-day rerun -> skipped, no new ledger row
n = len(ledger()); fs.cmd_run(["polymarket"], False)
check("same-day rerun adds no ledger row", len(ledger()) == n)

# 5. youtube_upload_dates with no lists snapshot -> FAILED, not EMPTY
fs.MAP.parent.mkdir(parents=True, exist_ok=True); fs.MAP.write_text("\t".join(fs.MAP_COLS) + "\n")
fs.cmd_run(["youtube_upload_dates"], False)
r = ledger()[-1]
check("upload_dates without lists -> FAILED", r["source"] == "youtube_upload_dates" and r["status"] == "FAILED", r["error"][:100])

# 6. empty channel map -> youtube_lists EMPTY (real zero, fetch never attempted)
fs.cmd_run(["youtube_lists"], False)
r = ledger()[-1]
check("youtube_lists with 0 channels -> EMPTY", r["source"] == "youtube_lists" and r["status"] == "EMPTY", r["status"])

# 7. concurrent run blocked by lock
lk = (tmp / ".lock").open("w"); fcntl.flock(lk, fcntl.LOCK_EX)
n = len(ledger()); rc = fs.cmd_run(["polymarket"], True)
check("second concurrent run refused (rc=1, no ledger row)", rc == 1 and len(ledger()) == n)
fcntl.flock(lk, fcntl.LOCK_UN)

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed; qa root {tmp}")
sys.exit(1 if bad else 0)
