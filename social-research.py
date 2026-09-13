#!/usr/bin/env python3
"""One-shot social research routes; no MCP process and no cookie export.

Commands:
  social-research.py scrapecreators PATH [KEY=VALUE ...]
  social-research.py tikhub PATH [KEY=VALUE ...]
  social-research.py xhs-search QUERY [--route auto|tikhub|browser]
                                [--page N] [--sort VALUE] [--note-type VALUE]

Credentials are read from the process environment, then from
~/.config/research-engine/keys.env. Credential values are never printed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


KEYS_FILE = Path.home() / ".config/research-engine/keys.env"
AGENT_CHROME = Path.home() / ".local/bin/agent-chrome.py"
SCRAPECREATORS_BASE = "https://api.scrapecreators.com"
TIKHUB_BASE = "https://api.tikhub.io"


def die(message: str, code: int = 1) -> "NoReturn":
    print(f"social-research: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_key(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    try:
        lines = KEYS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, candidate = line.partition("=")
        if sep and key.strip() == name:
            candidate = candidate.strip()
            if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in "\"'":
                candidate = candidate[1:-1]
            return candidate or None
    return None


def parse_params(items: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            die(f"parameter must be KEY=VALUE, got {item!r}")
        params[key] = value
    return params


def api_get(base: str, path: str, key_name: str, header: str, params: dict[str, object]) -> None:
    if not path.startswith("/") or "://" in path or ".." in path:
        die("PATH must be an absolute API path on the selected provider")
    if base == SCRAPECREATORS_BASE and not path.startswith("/v1/") and not path.startswith("/v2/"):
        die("ScrapeCreators PATH must start with /v1/ or /v2/")
    if base == TIKHUB_BASE and not path.startswith("/api/v1/"):
        die("TikHub PATH must start with /api/v1/")
    key = load_key(key_name)
    if not key:
        die(f"{key_name} is not configured in the environment or {KEYS_FILE}")
    query = urllib.parse.urlencode(params)
    url = base + path + ("?" + query if query else "")
    credential = f"Bearer {key}" if base == TIKHUB_BASE else key
    request = urllib.request.Request(
        url,
        headers={header: credential, "User-Agent": "research-engine/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(body, file=sys.stderr)
        die(f"HTTP {exc.code} from {base}")
    except OSError as exc:
        die(f"request failed: {exc}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(body)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def load_agent_chrome():
    if not AGENT_CHROME.exists():
        die(f"agent Chrome helper is missing: {AGENT_CHROME}")
    spec = importlib.util.spec_from_file_location("agent_chrome_local", AGENT_CHROME)
    if spec is None or spec.loader is None:
        die("could not load agent-chrome.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def xhs_browser_search(query: str) -> None:
    """Reuse Agent Chrome's own session and XHS's rendered initial state.

    This is the useful part extracted from xpzouying/xiaohongshu-mcp: navigate
    the normal search page, wait for window.__INITIAL_STATE__.search.feeds, and
    return a compact result. It does not launch another browser or persist a
    copied cookie jar.
    """
    ac = load_agent_chrome()
    if not ac.try_http_json("/json/version", timeout=2):
        die("Agent Chrome is not running; start it with: agent-chrome.py start", 2)
    url = "https://www.xiaohongshu.com/search_result?" + urllib.parse.urlencode(
        {"keyword": query, "source": "web_explore_feed"}
    )
    tab = ac.open_tab(url, wait=True)
    target_id = tab.info["id"]
    try:
        deadline = time.time() + 60
        result = None
        expression = r"""
        (() => {
          const box = window.__INITIAL_STATE__?.search?.feeds;
          const feeds = box ? (box.value ?? box._value) : null;
          const body = document.body?.innerText || '';
          if (body.includes('登录后查看搜索结果') || body.includes('登录后发现更多精彩内容')) {
            return {status: 'login_required', feeds: []};
          }
          if (!Array.isArray(feeds)) return {status: 'loading', feeds: []};
          const notes = feeds.filter(x => x?.modelType === 'note').map(x => {
            const n = x.noteCard || {};
            const u = n.user || {};
            const m = n.interactInfo || {};
            const cover = n.cover || {};
            return {
              id: x.id || null,
              xsec_token: x.xsecToken || null,
              title: n.displayTitle || null,
              type: n.type || null,
              user: {user_id: u.userId || null, nickname: u.nickname || u.nickName || null},
              liked_count: m.likedCount ?? null,
              comment_count: m.commentCount ?? null,
              collected_count: m.collectedCount ?? null,
              cover: cover.urlDefault || cover.url || null,
              url: x.id && x.xsecToken
                ? `https://www.xiaohongshu.com/explore/${x.id}?xsec_token=${encodeURIComponent(x.xsecToken)}&xsec_source=pc_feed`
                : null
            };
          });
          if (notes.length) return {status: 'ok', feeds: notes};
          if (/没有找到|暂无相关|换个词试试/.test(body)) return {status: 'empty', feeds: []};
          return {status: 'loading', feeds: []};
        })()
        """
        while time.time() < deadline:
            state = tab.evaluate(expression)
            if isinstance(state, dict) and state.get("status") == "login_required":
                die("XHS requires login in Agent Chrome; log in manually and rerun")
            if isinstance(state, dict) and state.get("status") in ("ok", "empty"):
                result = state.get("feeds")
                break
            time.sleep(0.5)
        if not isinstance(result, list):
            title = tab.evaluate("document.title")
            body = tab.evaluate("document.body ? document.body.innerText.slice(0, 300) : ''")
            die(f"XHS search state did not load (title={title!r}, body={body!r})")
        print(json.dumps({"route": "agent-chrome", "query": query, "count": len(result), "data": result}, ensure_ascii=False, indent=2))
    finally:
        tab.close()
        ac.http_text(f"/json/close/{target_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("scrapecreators", "tikhub"):
        p = sub.add_parser(name)
        p.add_argument("path")
        p.add_argument("params", nargs="*")

    p = sub.add_parser("xhs-search")
    p.add_argument("query")
    p.add_argument("--route", choices=("auto", "tikhub", "browser"), default="auto")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--sort", default="general")
    p.add_argument("--note-type", default="不限")

    args = parser.parse_args()
    if args.command == "scrapecreators":
        api_get(SCRAPECREATORS_BASE, args.path, "SCRAPECREATORS_API_KEY", "x-api-key", parse_params(args.params))
    elif args.command == "tikhub":
        api_get(TIKHUB_BASE, args.path, "TIKHUB_API_KEY", "Authorization", parse_params(args.params))
    elif args.command == "xhs-search":
        use_tikhub = args.route == "tikhub" or (args.route == "auto" and load_key("TIKHUB_API_KEY"))
        if use_tikhub:
            # Keep the convenience route explicit so its fixed XHS path and defaults
            # remain easy to audit; authentication matches the generic TikHub client.
            key = load_key("TIKHUB_API_KEY")
            if not key:
                die(f"TIKHUB_API_KEY is not configured in the environment or {KEYS_FILE}")
            query = urllib.parse.urlencode({
                "keyword": args.query,
                "page": args.page,
                "sort_type": args.sort,
                "note_type": args.note_type,
                "time_filter": "不限",
            })
            request = urllib.request.Request(
                TIKHUB_BASE + "/api/v1/xiaohongshu/app_v2/search_notes?" + query,
                headers={"Authorization": f"Bearer {key}", "User-Agent": "research-engine/1.0"},
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    data = json.load(response)
            except urllib.error.HTTPError as exc:
                print(exc.read().decode("utf-8", "replace"), file=sys.stderr)
                die(f"HTTP {exc.code} from {TIKHUB_BASE}")
            except OSError as exc:
                die(f"request failed: {exc}")
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            xhs_browser_search(args.query)


if __name__ == "__main__":
    main()
