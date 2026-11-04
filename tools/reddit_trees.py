#!/usr/bin/env python3
"""Fetch full posts + complete comment trees for given Reddit post IDs from Arctic Shift (2026-11-03).
Does not touch reddit.com. Pairs with reddit_browser_search.py (which finds the IDs).

Usage: reddit_trees.py --out DIR id1 id2 ...      |   reddit_trees.py --out DIR --from-posts-json DIR/posts.json
Output: DIR/posts/<id>.json (post), DIR/trees/<id>.json (raw tree), DIR/readable/<id>.md (post + every comment,
        indented by depth, with score/author/date), DIR/trees-ledger.csv (GOT_DATA / EMPTY / FAILED per id)
"""
import argparse, csv, json, sys, time, urllib.parse, urllib.request
from pathlib import Path

API = "https://arctic-shift.photon-reddit.com/api"
UA = {"User-Agent": "personal-research-archiver/1.0 (single sequential client)"}

def log(*a): print(time.strftime("%H:%M:%S"), "[trees]", *a, file=sys.stderr, flush=True)

def get(path, params, tries=8):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    for t in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                d = json.load(r)
            if d.get("data") is not None:
                return d["data"]
            log("api-error", d.get("error"), "try", t)
        except Exception as e:
            log("http-error", repr(e)[:150], "try", t)
        time.sleep(5 * (t + 1))
    return None

def flatten(nodes, out, depth=0):
    for n in nodes or []:
        if n.get("kind") != "t1":
            continue
        d = n["data"]; out.append((depth, d))
        rep = d.get("replies")
        if isinstance(rep, dict):
            flatten(rep.get("data", {}).get("children"), out, depth + 1)
    return out

def day(ts): return time.strftime("%Y-%m-%d", time.gmtime(ts or 0))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*"); ap.add_argument("--out", required=True); ap.add_argument("--from-posts-json")
    a = ap.parse_args()
    ids = list(a.ids)
    if a.from_posts_json:
        ids += list(json.loads(Path(a.from_posts_json).read_text()).keys())
    ids = list(dict.fromkeys(ids))
    out = Path(a.out)
    for sub in ("posts", "trees", "readable"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    rows = []
    # post bodies in batches of 100 (API limit 500)
    need = [i for i in ids if not (out / "posts" / f"{i}.json").exists()]
    for k in range(0, len(need), 100):
        batch = get("posts/ids", {"ids": ",".join(need[k:k + 100])}) or []
        for p in batch:
            (out / "posts" / f"{p['id']}.json").write_text(json.dumps(p, ensure_ascii=False))
        time.sleep(1)
    for i in ids:
        tf = out / "trees" / f"{i}.json"
        if not tf.exists():
            d = get("comments/tree", {"link_id": f"t3_{i}", "limit": 9999})
            if d is None:
                rows.append([i, "FAILED", 0]); continue
            tf.write_text(json.dumps(d, ensure_ascii=False)); time.sleep(1)
        cs = flatten(json.loads(tf.read_text()), [])
        pf = out / "posts" / f"{i}.json"
        p = json.loads(pf.read_text()) if pf.exists() else {}
        lines = [f"# {p.get('title', '(post body not available)')}",
                 f"r/{p.get('subreddit')} · u/{p.get('author')} · {day(p.get('created_utc'))} · score {p.get('score')} · "
                 f"{len(cs)} comments · https://www.reddit.com/comments/{i}/", ""]
        if p.get("selftext"):
            lines += [p["selftext"], ""]
        lines.append("---")
        for depth, c in cs:
            body = (c.get("body") or "").replace("\n", "\n" + "  " * depth + "  ")
            lines.append(f"{'  ' * depth}- **u/{c.get('author')}** ({c.get('score')}, {day(c.get('created_utc'))}): {body}")
        (out / "readable" / f"{i}.md").write_text("\n".join(lines) + "\n")
        rows.append([i, "GOT_DATA" if (cs or p) else "EMPTY", len(cs)])
    with open(out / "trees-ledger.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["post_id", "status", "comments"]); w.writerows(rows)
    log("done", len(ids), "ids;", sum(r[1] == "GOT_DATA" for r in rows), "GOT_DATA;", sum(r[1] == "FAILED" for r in rows), "FAILED")

if __name__ == "__main__":
    main()
