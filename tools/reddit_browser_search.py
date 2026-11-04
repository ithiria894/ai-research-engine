#!/usr/bin/env python3
"""Search Reddit through the logged-in agent Chrome at HUMAN pace (2026-11-03).

Nicole: 「總之小心啲做，唔好畀人 ban account 啦……我哋可以用人體嘅速度去 scroll 㗎嘛，慢慢唔緊要㗎喎。」

- Uses the endpoint the Reddit web UI itself loads: /svc/shreddit/search/?q=...  (sitewide) or
  /svc/shreddit/r/<sub>/search/?q=...  (one sub). /search.json is 403-blocked even in the browser.
- One request at a time, random 30-45 s gap (like a person reading a page), follows `cursor=` pages.
- Any non-200 (incl. 429): pause 15 min and retry once; a second failure STOPS the whole run.
- Only finds post IDs + titles. Fetch full comment trees with reddit_trees.py (Arctic Shift, no reddit.com).

Usage: reddit_browser_search.py --out DIR [--sub SUB] [--pages 10] "query one" "query two" ...
       reddit_browser_search.py --out DIR --queries-file q.txt
Output: DIR/pages/*.html (raw), DIR/ledger.csv, DIR/posts.json {id: {title, subreddit, queries[]}}
"""
import argparse, csv, html, json, random, re, subprocess, sys, time, urllib.parse
from pathlib import Path

MIN_GAP, MAX_GAP, COOLDOWN = 30, 45, 15 * 60  # 2026-11-04: 15-25 s hit "Failed to fetch" twice in an hour -> slower

def log(*a):
    print(time.strftime("%H:%M:%S"), "[reddit-browser]", *a, file=sys.stderr, flush=True)

class Stop(Exception):
    pass

def fetch(url, dest, state):
    for attempt in (1, 2):
        gap = random.uniform(MIN_GAP, MAX_GAP)
        wait = gap - (time.time() - state["last"])
        if wait > 0:
            time.sleep(wait)
        r = subprocess.run(["agent-chrome.py", "fetch", url, "--out", str(dest)], capture_output=True, text=True, timeout=120)
        state["last"] = time.time()
        if r.returncode == 2:  # Chrome not running
            log("Chrome unreachable -> agent-chrome.py start")
            subprocess.run(["agent-chrome.py", "start"], capture_output=True, timeout=180)
            continue
        if r.returncode == 0:
            return
        dest.unlink(missing_ok=True)
        log("FAIL", r.stderr.strip()[-200:])
        if attempt == 1:
            log(f"cooling down {COOLDOWN // 60} min before one retry")
            time.sleep(COOLDOWN)
    raise Stop(f"second failure on {url} — stopping the run to protect the account")

def parse(page):
    posts = {}
    for ctx in re.findall(r'data-faceplate-tracking-context="([^"]+)"', page):
        try:
            d = json.loads(html.unescape(ctx))
        except Exception:
            continue
        p = d.get("post") or {}
        if p.get("id", "").startswith("t3_") and p.get("title"):
            posts[p["id"][3:]] = {"title": p["title"], "subreddit": (d.get("subreddit") or {}).get("name")}
    nxt = re.findall(r'(/svc/shreddit/[^"\s]*search/\?[^"\s]*cursor=[^"\s]+)', page)
    return posts, (html.unescape(nxt[0]) if nxt else None)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queries", nargs="*"); ap.add_argument("--queries-file")
    ap.add_argument("--out", required=True); ap.add_argument("--sub"); ap.add_argument("--pages", type=int, default=10)
    a = ap.parse_args()
    qs = list(a.queries)
    if a.queries_file:
        qs += [l.strip() for l in Path(a.queries_file).read_text().splitlines() if l.strip() and not l.startswith("#")]
    out = Path(a.out); (out / "pages").mkdir(parents=True, exist_ok=True)
    pj = out / "posts.json"
    allposts = json.loads(pj.read_text()) if pj.exists() else {}
    ledger_rows, state = [], {"last": 0.0}
    base = f"https://www.reddit.com/svc/shreddit/r/{a.sub}/search/" if a.sub else "https://www.reddit.com/svc/shreddit/search/"
    try:
        for q in qs:
            url = base + "?q=" + urllib.parse.quote_plus(q)
            got, status = 0, "EMPTY"
            for pg in range(a.pages):
                dest = out / "pages" / f"{a.sub or 'ALL'}__{re.sub(r'[^A-Za-z0-9]+', '_', q)[:60]}__p{pg}.html"
                if not dest.exists():
                    fetch(url, dest, state)
                posts, nxt = parse(dest.read_text(errors="ignore"))
                for pid, p in posts.items():
                    e = allposts.setdefault(pid, {**p, "queries": []})
                    if q not in e["queries"]:
                        e["queries"].append(q)
                got += len(posts); status = "GOT_DATA" if got else status
                if not nxt or not posts:
                    break
                url = "https://www.reddit.com" + nxt
            log(f"{q!r}: {status} {got} hits")
            ledger_rows.append([a.sub or "ALL", q, status, got, ""])
    except Stop as e:
        log("STOPPED:", e)
        ledger_rows.append([a.sub or "ALL", "-", "FAILED", 0, str(e)])
    finally:
        pj.write_text(json.dumps(allposts, ensure_ascii=False, indent=0))
        new = not (out / "ledger.csv").exists()
        with open(out / "ledger.csv", "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["scope", "query", "status", "post_hits", "error"])
            w.writerows(ledger_rows)
        log("unique posts so far", len(allposts))

if __name__ == "__main__":
    main()
