#!/usr/bin/env python3
"""Import per-subreddit torrent dumps into the API archive layout, then let the API pipeline catch up — 2026-11-13.

Why: one archive, one format. Subs we have never downloaded get their 2005–2023 history from the torrent
(reddit_torrent.py, top-40k per-subreddit files) instead of years of Arctic Shift API pages; the API pipeline
(reddit_archive.py) then only fetches what is newer than the torrent (2024-01 onwards).

Rules
- Only fills a <sub>/<kind> that has NO stored data yet (no DONE, no non-empty part). Existing API data is never
  touched; the raw torrent file stays in ~/data/reddit-torrents as a second source.
- Same row shape as the API pipeline: only the fields in reddit_archive.FIELDS, created_utc as int, ids deduped,
  same part size limits, same zstd compression (reddit_archive.compress).
- Holds the same per-sub .lock as reddit_archive.py, so the pipeline SKIPs a sub while it is being imported.
- Waits until the torrent file is fully downloaded (<infohash>.completed.tsv written by reddit_torrent.py).

Usage  : reddit_torrent_import.py --subs-file F [--subs-file G ...] [SUB ...] [--catch-up] [--wait]
           --catch-up : after importing, run the API pipeline for that sub (fetches 2024-01 → now)
           --wait     : keep waiting for torrent files that are still downloading (else skip them for now)
         --root DIR / --torrent-root DIR : override locations (used by the QA test)
"""
import argparse, fcntl, json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import reddit_archive as ra

IH = "56aa49f9653ba545f48df2e33679f014d2829c10"  # top 40k subreddits 2005-06 – 2023-12
TKIND = {"posts": "submissions", "comments": "comments"}
TEXT = ("title", "selftext", "body")

def unescape(s):
    """Torrent text is HTML-escaped (&amp; &lt; &gt;); the API pipeline stores it unescaped. QA 2026-11-13:
    every text difference on shared ids (scoliosis, ubco) was exactly this escaping."""
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&") if isinstance(s, str) else s

def has_data(d):
    return (d / "DONE").exists() or any(p.stat().st_size > 0 for p in d.glob("part-*"))

def torrent_files(troot):
    """lowercase sub -> {tkind: (relative path, bytes)} from the torrent file list."""
    out = {}
    for line in (troot / f"{IH}.files.tsv").read_text().splitlines()[1:]:
        _, b, p = line.split("\t")
        name = p.rsplit("/", 1)[-1]
        for tk in ("comments", "submissions"):
            if name.endswith(f"_{tk}.zst"):
                out.setdefault(name[: -len(f"_{tk}.zst")].lower(), {})[tk] = (p, int(b))
    return out

def completed(troot):
    f = troot / f"{IH}.completed.tsv"
    return {l.split("\t")[1] for l in f.read_text().splitlines() if "\t" in l} if f.exists() else set()

def import_one(sub, kind, src, src_bytes):
    d = ra.ROOT / sub / kind; d.mkdir(parents=True, exist_ok=True)
    fields = ra.FIELDS[kind].split(",")
    ra.log(f"IMPORT r/{sub} {kind} from torrent {src.name} ({src_bytes/1e6:.1f} MB compressed)")
    p = subprocess.Popen(["zstd", "-dcq", "--long=31", str(src)], stdout=subprocess.PIPE, text=True)
    seen, idx, n_part, total, dup, bad, back, last_ts, max_ts = set(), 0, 0, 0, 0, 0, 0, 0, 0
    cur = d / f"part-{idx:05d}.jsonl"; f = cur.open("w")
    for line in p.stdout:
        try:
            o = json.loads(line)
            row = {k: o.get(k) for k in fields}
            row["created_utc"] = int(float(row["created_utc"]))
            for k in TEXT:
                if k in row:
                    row[k] = unescape(row[k])
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            bad += 1; continue
        if row["id"] in seen:
            dup += 1; continue
        seen.add(row["id"])
        if row["created_utc"] < last_ts:
            back += 1
        last_ts = row["created_utc"]; max_ts = max(max_ts, last_ts)
        f.write(json.dumps(row, ensure_ascii=False) + "\n"); n_part += 1; total += 1
        if n_part >= ra.CHUNK or f.tell() >= ra.CHUNK_BYTES:
            f.close(); ra.compress(cur); idx += 1; n_part = 0
            cur = d / f"part-{idx:05d}.jsonl"; f = cur.open("w")
        if total % 1_000_000 == 0:
            ra.log(f"  r/{sub} {kind} imported {total:,} up to {time.strftime('%Y-%m-%d', time.gmtime(max_ts))}")
    f.close()
    rc = p.wait()
    if rc != 0:
        ra.log(f"IMPORT r/{sub} {kind} FAILED: zstd exit {rc} after {total:,} rows — partial parts left for inspection, no DONE written")
        return False
    if n_part:
        ra.compress(cur)
    else:
        cur.unlink()
    (d / "DONE").write_text(f"last_created_utc={max_ts} updated={time.strftime('%Y-%m-%d %H:%M:%S')} added={total} source=torrent:{IH}\n")
    ra.log(f"IMPORT r/{sub} {kind} DONE rows={total:,} dup_ids={dup} bad_lines={bad} out_of_order={back} "
           f"newest={time.strftime('%Y-%m-%d %H:%M', time.gmtime(max_ts))} parts={idx + (1 if n_part else 0)}")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subs", nargs="*"); ap.add_argument("--subs-file", action="append", default=[])
    ap.add_argument("--catch-up", action="store_true"); ap.add_argument("--wait", action="store_true")
    ap.add_argument("--root"); ap.add_argument("--torrent-root")
    a = ap.parse_args()
    if a.root:
        ra.ROOT = Path(a.root)
    ra.ROOT.mkdir(parents=True, exist_ok=True)
    troot = Path(a.torrent_root) if a.torrent_root else Path.home() / "data" / "reddit-torrents"
    subs = list(a.subs)
    for fp in a.subs_file:
        subs += [l.split("#")[0].strip() for l in Path(fp).read_text().splitlines() if l.split("#")[0].strip()]
    subs = list(dict.fromkeys(subs))
    tf = torrent_files(troot)
    ra.log(f"IMPORT RUN subs={len(subs)} root={ra.ROOT} torrent_root={troot} catch_up={a.catch_up} wait={a.wait}")
    queue = []
    for s in subs:
        if s.lower() not in tf:
            ra.log(f"  r/{s}: not in torrent {IH[:8]} — left to the API pipeline"); continue
        need = [k for k in ("posts", "comments") if not has_data(ra.ROOT / s / k)]
        if not need:
            ra.log(f"  r/{s}: archive already has posts+comments — skip"); continue
        queue.append((s, need))
    ra.log(f"IMPORT queue: {len(queue)} subs: " + " ".join(s for s, _ in queue))
    # take every queued sub's lock up front and keep it until that sub is finished, so the API pipeline
    # SKIPs it instead of starting the same history from 2005 while the torrent file is still downloading
    locks, held = {}, []
    for s, need in queue:
        (ra.ROOT / s).mkdir(parents=True, exist_ok=True)
        lockf = (ra.ROOT / s / ".lock").open("w")
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locks[s] = lockf; held.append((s, need))
        except BlockingIOError:
            ra.log(f"  r/{s}: an archiver process is already downloading it via API — leave it to that run")
            lockf.close()
    queue = held
    ra.log(f"IMPORT holding locks for {len(queue)} subs")
    def release(s):
        lf = locks.pop(s); fcntl.flock(lf, fcntl.LOCK_UN); lf.close()
    try:
        while queue:
            done_paths, pending = completed(troot), []
            for s, need in queue:
                left = []
                for k in need:
                    rel, b = tf[s.lower()].get(TKIND[k], (None, 0))
                    if rel is None:
                        ra.log(f"  r/{s} {k}: torrent has no {TKIND[k]} file — left to the API pipeline"); continue
                    if rel not in done_paths:
                        left.append(k); continue
                    import_one(s, k, troot / rel, b)
                if left:
                    pending.append((s, left)); continue
                if a.catch_up:
                    for k in ("posts", "comments"):
                        ra.log(f"  r/{s} {k}: catch-up via API after torrent import")
                        try:
                            ra.dump(s, k)
                        except Exception as e:
                            ra.log(f"FAILED catch-up r/{s} {k}: {e!r}")
                release(s)
            queue = pending
            if queue:
                ra.log(f"IMPORT waiting for torrent files of {len(queue)} subs: " + " ".join(s for s, _ in queue))
                if not a.wait:
                    ra.log("IMPORT stop: rerun later or use --wait"); break
                time.sleep(300)
    finally:
        for s in list(locks):
            release(s)
    ra.log("IMPORT RUN finished")

if __name__ == "__main__":
    main()
