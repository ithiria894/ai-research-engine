#!/usr/bin/env python3
"""Own a local copy of whole subreddits (posts + comments) via Arctic Shift — 2026-11-03.

Why: Reddit is closing public access (API closes 2027-03, RSS 2026-11-13, search.json 403 even in a
logged-in browser, reddit.com 429s our browser). Arctic Shift (arctic-shift.photon-reddit.com) does
not touch reddit.com or Nicole's Reddit account. Its docs say: "If you're a normal user and only make
a couple requests per second, you have nothing to worry about" — we stay well under that, strictly
sequential, honour 429 X-RateLimit-Reset, back off on 422. Research note:
source-scans/reddit-access-2026-11-03/README.md

Layout : ~/data/reddit-archive/<sub>/<kind>/part-00000.jsonl[.zst]   (kind = posts | comments)
         each part holds CHUNK rows; finished parts are zstd-compressed in place.
Resume : re-running continues after the newest created_utc already stored (boundary rows deduped).
Usage  : reddit_archive.py dump --subs-file tools/reddit_archive_subs.txt   # all, in file order
         reddit_archive.py dump premedcanada UBC --kinds posts comments
         reddit_archive.py status
"""
import argparse, fcntl, json, shutil, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path.home() / "data" / "reddit-archive"
API = "https://arctic-shift.photon-reddit.com/api/{kind}/search"
UA = {"User-Agent": "personal-research-archiver/1.0 (single sequential client)"}
CHUNK = 200_000
CHUNK_BYTES = 250_000_000  # also cut a part at 250 MB plain, so a compressed part stays far below GitHub's 100 MB file limit
MIN_FREE_GB = 10  # stop before filling the disk (2026-11-03: 33 GB free of 465 GB)
PAUSE = 0.8  # seconds between requests, on top of response time (~1-1.7 s)
# Allowed field names from Arctic Shift api/README.md (no `permalink`: it returns HTTP 400)
FIELDS = {
    "posts": "id,author,created_utc,subreddit,title,selftext,score,num_comments,link_flair_text,url,over_18,distinguished",
    "comments": "id,author,created_utc,subreddit,body,link_id,parent_id,score,distinguished",
}

def log(*a):
    msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(msg, file=sys.stderr, flush=True)
    with (ROOT / "run.log").open("a") as f:
        f.write(msg + "\n")

def get(kind, params):
    url = API.format(kind=kind) + "?" + urllib.parse.urlencode(params)
    for t in range(12):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                d = json.load(r)
            if d.get("data") is not None:
                return d["data"]
            log("  api-error", d.get("error"), "try", t)
        except urllib.error.HTTPError as e:
            wait = 5 * (t + 1)
            if e.code == 429:
                wait = max(wait, int(e.headers.get("X-RateLimit-Reset") or 30) + 2)
            log("  http", e.code, "try", t, "sleep", wait)
            time.sleep(wait); continue
        except Exception as e:
            log("  net-error", repr(e)[:160], "try", t)
        time.sleep(5 * (t + 1))
    raise RuntimeError(f"giving up: {url}")

def parts(d):
    return sorted(p for p in d.glob("part-*") if p.suffix in (".jsonl", ".zst"))

def last_rows(p):
    """Rows of a part file (plain or .zst)."""
    if p.suffix == ".zst":
        txt = subprocess.run(["zstd", "-dcq", str(p)], capture_output=True, text=True, check=True).stdout
    else:
        txt = p.read_text()
    rows = []
    for l in txt.splitlines():
        if l.strip():
            try:
                rows.append(json.loads(l))
            except json.JSONDecodeError:  # half-written last line from a killed run
                log("  WARN skipping malformed line in", p.name, repr(l[:80]))
    if p.suffix == ".jsonl" and rows and not txt.endswith("\n"):
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))  # drop the partial tail
    return rows

def compress(p):
    # write to .zst.tmp then rename: the GitHub sync (reddit_archive_sync.sh) only ever sees complete .zst files
    tmp, final = p.with_name(p.name + ".zst.tmp"), p.with_name(p.name + ".zst")
    subprocess.run(["zstd", "-q", "-19", "-f", "-o", str(tmp), str(p)], check=True)
    tmp.rename(final); p.unlink()
    log("  compressed", p.name, "->", final.name, f"{final.stat().st_size/1e6:.1f} MB")

def dump(sub, kind):
    d = ROOT / sub / kind; d.mkdir(parents=True, exist_ok=True)
    if (d / "DONE").exists() and "--refresh" not in sys.argv:
        pass  # still resume: picks up anything newer (incremental update)
    ps = parts(d)
    last_ts, seen, n_in_part, cur = 0, set(), 0, None
    # newest stored row = last NON-EMPTY part (a fresh empty part follows every compression)
    for p in reversed(ps):
        rows = last_rows(p)
        if rows:
            last_ts = max(r["created_utc"] for r in rows)
            seen = {r["id"] for r in rows if r["created_utc"] >= last_ts - 1}
            break
    if ps and ps[-1].suffix == ".jsonl":
        cur, n_in_part = ps[-1], len(last_rows(ps[-1]))
    idx = len(ps) if cur is None else len(ps) - 1
    if cur is None:
        cur = d / f"part-{idx:05d}.jsonl"
    log(f"START r/{sub} {kind} after={last_ts} ({time.strftime('%Y-%m-%d', time.gmtime(last_ts)) if last_ts else 'beginning'}) part={cur.name}")
    f = cur.open("a"); total = 0
    try:
        while True:
            params = {"subreddit": sub, "limit": 100, "sort": "asc", "fields": FIELDS[kind]}
            if last_ts:
                params["after"] = last_ts - 1  # overlap 1 s, dedupe below (after-semantics not documented)
            rows = get(kind, params)
            new = [r for r in rows if r["id"] not in seen]
            if not rows:
                break
            if not new:
                if len(rows) < 100:
                    break
                log("  WARN full page with no new ids at", last_ts, "-> stepping +2s (possible tiny gap)")
                last_ts += 2; seen = set(); continue
            for r in new:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n_in_part += len(new); total += len(new)
            last_ts = max(r["created_utc"] for r in new)
            seen = {r["id"] for r in rows if r["created_utc"] >= last_ts - 1} | {r["id"] for r in new if r["created_utc"] >= last_ts - 1}
            if n_in_part >= CHUNK or f.tell() >= CHUNK_BYTES:
                f.close(); compress(cur); idx += 1
                cur = d / f"part-{idx:05d}.jsonl"; f = cur.open("a"); n_in_part = 0
            if total % 10_000 < len(new):
                log(f"  r/{sub} {kind} +{total:,} up to {time.strftime('%Y-%m-%d', time.gmtime(last_ts))}")
            time.sleep(PAUSE)
    finally:
        f.close()
    # compress the last part too, so every stored row lives in a .zst (only .zst files go to GitHub);
    # the next incremental run then starts a fresh part
    if cur.exists() and cur.stat().st_size > 0:
        compress(cur)
    elif cur.exists():
        cur.unlink()  # empty part we created ourselves
    (d / "DONE").write_text(f"last_created_utc={last_ts} updated={time.strftime('%Y-%m-%d %H:%M:%S')} added={total}\n")
    log(f"DONE r/{sub} {kind} added {total:,} newest={time.strftime('%Y-%m-%d %H:%M', time.gmtime(last_ts)) if last_ts else '-'}")

def status():
    for sd in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        for kind in ("posts", "comments"):
            d = sd / kind
            if not d.exists():
                continue
            size = sum(p.stat().st_size for p in d.glob("part-*"))
            done = (d / "DONE").read_text().strip() if (d / "DONE").exists() else "in progress / not finished"
            print(f"{sd.name:24} {kind:9} {len(parts(d)):3} parts {size/1e6:9.1f} MB  {done}")

def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    a1 = sp.add_parser("dump"); a1.add_argument("subs", nargs="*"); a1.add_argument("--subs-file")
    a1.add_argument("--kinds", nargs="+", default=["posts", "comments"]); a1.add_argument("--refresh", action="store_true")
    sp.add_parser("status")
    a = ap.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    if a.cmd == "status":
        return status()
    subs = list(a.subs)
    if a.subs_file:
        subs += [l.split("#")[0].strip() for l in Path(a.subs_file).read_text().splitlines() if l.split("#")[0].strip()]
    log("RUN subs:", " ".join(subs), "kinds:", a.kinds)
    for s in subs:
        # one writer per subreddit: several lines (main / cpsbc / sat) + the weekly timer may list the same sub
        (ROOT / s).mkdir(parents=True, exist_ok=True)
        lockf = (ROOT / s / ".lock").open("w")
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log(f"SKIP r/{s}: another archiver process holds its lock (it will be picked up on a later run)")
            lockf.close(); continue
        try:
            for k in a.kinds:
                free_gb = shutil.disk_usage(ROOT).free / 1e9
                if free_gb < MIN_FREE_GB:
                    log(f"STOP: only {free_gb:.1f} GB free (< {MIN_FREE_GB} GB guard) before r/{s} {k}")
                    return
                try:
                    dump(s, k)
                except Exception as e:
                    log(f"FAILED r/{s} {k}: {e!r} — continuing with next")
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN); lockf.close()

if __name__ == "__main__":
    main()
