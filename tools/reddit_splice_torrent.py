#!/usr/bin/env python3
"""將 torrent 嘅 <sub>_comments.zst／_submissions.zst 接駁落 reddit_archive.py 嘅存檔（2026-11-20）。

Why: reddit_archive.py 經 Arctic Shift API 由頭逐頁落，大 sub（例如 DataHoarder）要成兩日，仲成日 422。
     torrent（reddit_torrent.py）有齊 2005–2023-12 嘅完整檔，幾分鐘落完。呢個工具將 torrent 入面
     「存檔最新一行之後、CUTOFF 之前」嘅行，寫成同一格式嘅 part 檔，之後重開 reddit_archive.py dump，
     佢會由最新一行（即 CUTOFF 附近）接住用 API 落 2024 之後。

Usage: reddit_splice_torrent.py <torrent.zst> <archive kind dir> --kind comments|posts
                                [--after TS] [--cutoff 2024-01-01] [--start-index N] [--out DIR]
  --after       存檔最新一行嘅 created_utc（唔畀就讀 <archive kind dir> 最後一個非空 part）
  --start-index 新 part 檔由幾號開始（預設 = 現有 part 數；如果最後一個係未壓縮 .jsonl，就接佢之後）
  --out         寫去另一個 folder（例如喺手提整好再 scp 去 Waifu）；預設寫入 <archive kind dir>
輸出：part-NNNNN.jsonl.zst（每份最多 250 MB 未壓縮，同 reddit_archive.py 一樣），欄位同 reddit_archive.py FIELDS 一樣。
"""
import argparse
import calendar
import json
import subprocess
import sys
import time
from pathlib import Path

FIELDS = {  # 同 reddit_archive.py 一致
    "posts": "id,author,created_utc,subreddit,title,selftext,score,num_comments,link_flair_text,url,over_18,distinguished",
    "comments": "id,author,created_utc,subreddit,body,link_id,parent_id,score,distinguished",
}
CHUNK_BYTES = 250_000_000


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a), file=sys.stderr, flush=True)


def archive_state(d: Path):
    ps = sorted(p for p in d.glob("part-*") if p.suffix in (".jsonl", ".zst"))
    for p in reversed(ps):
        txt = subprocess.run(["zstd", "-dcq", str(p)], capture_output=True, text=True, check=True).stdout if p.suffix == ".zst" else p.read_text()
        rows = [json.loads(l) for l in txt.splitlines() if l.strip()]
        if rows:
            last = max(int(r["created_utc"]) for r in rows)
            seen = {r["id"] for r in rows if int(r["created_utc"]) >= last - 1}
            return last, seen, len(ps)
    return 0, set(), len(ps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("torrent"); ap.add_argument("archive_dir")
    ap.add_argument("--kind", required=True, choices=FIELDS)
    ap.add_argument("--after", type=int); ap.add_argument("--cutoff", default="2024-01-01")
    ap.add_argument("--start-index", type=int); ap.add_argument("--out")
    a = ap.parse_args()
    d = Path(a.archive_dir)
    last, seen, n_parts = archive_state(d) if d.exists() else (0, set(), 0)
    if a.after is not None:
        last = a.after
    cutoff = calendar.timegm(time.strptime(a.cutoff, "%Y-%m-%d"))
    idx = a.start_index if a.start_index is not None else n_parts
    out = Path(a.out) if a.out else d
    out.mkdir(parents=True, exist_ok=True)
    keep = FIELDS[a.kind].split(",")
    log(f"START {a.torrent} kind={a.kind} after={last} ({time.strftime('%Y-%m-%d %H:%M', time.gmtime(last))}) "
        f"cutoff={a.cutoff} start-index={idx} out={out}")
    proc = subprocess.Popen(["zstd", "-dcq", "--long=31", a.torrent], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    cur, fh, size, n, n_total, n_bad, newest = None, None, 0, 0, 0, 0, 0

    def close():
        if fh:
            fh.close()
            subprocess.run(["zstd", "-q", "-19", "-f", "--rm", "-o", str(cur) + ".zst", str(cur)], check=True)
            log(f"  wrote {cur.name}.zst rows={n:,}")

    for line in proc.stdout:
        n_total += 1
        try:
            r = json.loads(line)
            ts = int(r["created_utc"])
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            n_bad += 1
            continue
        if ts < last - 1 or ts >= cutoff or r.get("id") in seen:
            continue
        row = {k: r.get(k) for k in keep}
        row["created_utc"] = ts
        if a.kind == "comments" and row.get("link_id") and not str(row["link_id"]).startswith("t3_"):
            row["link_id"] = "t3_" + str(row["link_id"])
        s = json.dumps(row, ensure_ascii=False) + "\n"
        if fh is None or size + len(s) > CHUNK_BYTES:
            close()
            cur = out / f"part-{idx:05d}.jsonl"; idx += 1
            fh, size, n = cur.open("w"), 0, 0
        fh.write(s); size += len(s); n += 1
        newest = max(newest, ts)
        if n_total % 2_000_000 == 0:
            log(f"  scanned {n_total:,} lines, newest kept {time.strftime('%Y-%m-%d', time.gmtime(newest)) if newest else '-'}")
    close()
    rc = proc.wait()
    if rc != 0:
        log(f"FAILED zstd exit {rc}"); sys.exit(rc)
    log(f"DONE scanned={n_total:,} bad={n_bad:,} newest kept={time.strftime('%Y-%m-%d %H:%M', time.gmtime(newest)) if newest else '-'}")


if __name__ == "__main__":
    main()
