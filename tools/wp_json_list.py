#!/usr/bin/env python3
"""列出任何 WordPress 網站嘅全部 pages／posts／media（wp-json REST API，自動分頁）。

2026-11-14 BCHRT 實戰：判詞頁係 parent=78431 嘅子頁，PDF 喺 media library。
唔使逐頁爬 HTML、唔使估 AJAX：WordPress 預設開放 /wp-json/wp/v2/。

用法：
  python3 -I wp_json_list.py https://www.bchrt.bc.ca types                       # 有咩 post type
  python3 -I wp_json_list.py https://www.bchrt.bc.ca pages --parent 78431         # 某頁嘅全部子頁
  python3 -I wp_json_list.py https://www.bchrt.bc.ca pages --search "bchrt"       # 搜尋
  python3 -I wp_json_list.py https://www.bchrt.bc.ca media --mime application/pdf # 全部 PDF
  加 --out x.json 存原始 listing；stdout 每行一個 JSON（id, date, modified, link/source_url, title, parent）

點揾 parent id：開目標頁 HTML，搵 `wp-json/wp/v2/pages/<id>`（<link rel="alternate">）。
分頁：response header X-WP-Total（總數）、X-WP-TotalPages；per_page 最大 100。
任何一頁失敗會 exit 2，唔會當「冇嘢」（FAILED ≠ EMPTY）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) research-engine/wp_json_list"


def get(url: str) -> tuple[int, bytes, dict]:
    print(f"[wp_json_list] GET {url}", file=sys.stderr, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b"", {}
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"[wp_json_list] network error: {e}", file=sys.stderr)
        return 0, b"", {}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("site")
    p.add_argument("kind", choices=["types", "pages", "posts", "media"])
    p.add_argument("--parent", type=int)
    p.add_argument("--search")
    p.add_argument("--mime")
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--out")
    a = p.parse_args()
    base = a.site.rstrip("/") + "/wp-json/wp/v2/"
    if a.kind == "types":
        st, body, _ = get(base + "types")
        if st != 200:
            print(f"[wp_json_list] FAILED status={st}", file=sys.stderr)
            return 2
        for k, v in json.loads(body).items():
            print(json.dumps({"type": k, "rest_base": v.get("rest_base"), "name": v.get("name")}))
        return 0
    q = {"per_page": 100, "_fields": "id,date,modified,link,source_url,title,parent,slug,mime_type"}
    if a.parent is not None:
        q["parent"] = a.parent
    if a.search:
        q["search"] = a.search
    if a.mime:
        q["mime_type"] = a.mime
    items, n, pages = [], 1, 1
    while n <= pages:
        q["page"] = n
        st, body, hdr = get(base + a.kind + "?" + urllib.parse.urlencode(q))
        if st != 200:
            print(f"[wp_json_list] FAILED page {n} status={st} — not treated as empty", file=sys.stderr)
            return 2
        pages = int(hdr.get("x-wp-totalpages") or 1)
        batch = json.loads(body)
        print(f"[wp_json_list] page {n}/{pages}: {len(batch)} items (X-WP-Total={hdr.get('x-wp-total')})", file=sys.stderr)
        items += batch
        n += 1
        time.sleep(a.delay)
    for it in items:
        it["title"] = (it.get("title") or {}).get("rendered")
        print(json.dumps(it, ensure_ascii=False))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=0)
    print(f"[wp_json_list] done: {len(items)} items", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
