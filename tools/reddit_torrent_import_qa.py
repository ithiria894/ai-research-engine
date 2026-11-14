#!/usr/bin/env python3
"""QA for reddit_torrent_import.py — compare a torrent-imported sub against the API archive of the same sub.

Usage: reddit_torrent_import_qa.py --imported ROOT_A --api ROOT_B SUB [SUB ...]
For each sub and kind, restricted to rows created before 2024-01-01 (the torrent's end):
  - row counts, ids in both / only API / only torrent
  - field check on shared ids: created_utc, author, title|body identical? (score is expected to differ)
  - the imported parts must be valid zstd JSONL with exactly reddit_archive.FIELDS keys
Exit code 1 if a structural check fails (bad keys, unreadable part, DONE missing).
"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import reddit_archive as ra

CUT = 1704067200  # 2024-01-01 00:00 UTC

def rows(d):
    out = {}
    for p in sorted(d.glob("part-*.zst")):
        txt = subprocess.run(["zstd", "-dcq", str(p)], capture_output=True, text=True, check=True).stdout
        for l in txt.splitlines():
            if l.strip():
                r = json.loads(l); out[r["id"]] = r
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--imported", required=True); ap.add_argument("--api", required=True)
    ap.add_argument("subs", nargs="+"); a = ap.parse_args()
    fail = False
    for s in a.subs:
        for kind, text in (("posts", "title"), ("comments", "body")):
            di, da = Path(a.imported) / s / kind, Path(a.api) / s / kind
            if not (di / "DONE").exists():
                print(f"FAIL {s} {kind}: imported DONE missing"); fail = True; continue
            ri, rapi = rows(di), rows(da)
            keys = set(ra.FIELDS[kind].split(","))
            badkeys = sum(1 for r in ri.values() if set(r) != keys)
            if badkeys:
                print(f"FAIL {s} {kind}: {badkeys} imported rows with wrong keys"); fail = True
            ri = {k: v for k, v in ri.items() if v["created_utc"] < CUT}
            rapi = {k: v for k, v in rapi.items() if v["created_utc"] < CUT}
            both = ri.keys() & rapi.keys()
            diff = {f: sum(1 for k in both if ri[k].get(f) != rapi[k].get(f)) for f in ("created_utc", "author", text)}
            print(f"{s:10} {kind:8} torrent={len(ri):>8,} api={len(rapi):>8,} both={len(both):>8,} "
                  f"only_api={len(rapi.keys()-ri.keys()):>6,} only_torrent={len(ri.keys()-rapi.keys()):>6,} "
                  f"differs_on_shared: {diff}")
    sys.exit(1 if fail else 0)

if __name__ == "__main__":
    main()
