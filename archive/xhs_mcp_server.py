#!/usr/bin/env python3
"""Read-only Xiaohongshu research tools for Codex.

The free route reuses the dedicated Agent Chrome session on port 9223.  When a
funded TIKHUB_API_KEY exists, the existing social-research client can use the
structured TikHub endpoints instead.  Credentials and browser cookies are
never returned by these tools.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


ROOT = Path(__file__).resolve().parent
SOCIAL_RESEARCH = ROOT / "social-research.py"
AGENT_CHROME = Path.home() / ".local/bin/agent-chrome.py"
KEYS_FILE = Path.home() / ".config/research-engine/keys.env"
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

mcp = FastMCP(
    "xiaohongshu",
    instructions=(
        "Read-only Xiaohongshu research. Search broadly with several Chinese "
        "query variants, then open relevant notes before treating titles as evidence."
    ),
    log_level="WARNING",
)


def _load_key(name: str) -> str | None:
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
        key, sep, value = line.partition("=")
        if sep and key.strip() == name:
            value = value.strip().strip("\"'")
            return value or None
    return None


def _chrome_ready() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:9223/json/version", timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


def _run_social(*args: str, timeout: int = 100) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(SOCIAL_RESEARCH), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise RuntimeError(detail)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Xiaohongshu route returned invalid JSON") from exc


def _load_agent_chrome():
    if not AGENT_CHROME.exists():
        raise RuntimeError(f"Agent Chrome helper is missing: {AGENT_CHROME}")
    spec = importlib.util.spec_from_file_location("agent_chrome_xhs", AGENT_CHROME)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Agent Chrome helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _browser_note(note_id: str, xsec_token: str, comment_limit: int) -> dict[str, Any]:
    if not _chrome_ready():
        raise RuntimeError("Agent Chrome is not running; start it with: agent-chrome.py start")
    ac = _load_agent_chrome()
    url = (
        f"https://www.xiaohongshu.com/explore/{urllib.parse.quote(note_id, safe='')}?"
        + urllib.parse.urlencode({"xsec_token": xsec_token, "xsec_source": "pc_feed"})
    )
    tab = ac.open_tab(url, wait=True)
    target_id = tab.info["id"]
    safe_id = json.dumps(note_id)
    safe_limit = max(0, min(comment_limit, 100))
    expression = f"""
    (() => {{
      const body = document.body?.innerText || '';
      if (body.includes('登录后查看') || body.includes('登录后发现更多精彩内容'))
        return {{status: 'login_required'}};
      const mapBox = window.__INITIAL_STATE__?.note?.noteDetailMap;
      const map = mapBox ? (mapBox.value ?? mapBox._value ?? mapBox) : null;
      if (!map || typeof map !== 'object') return {{status: 'loading'}};
      const entry = map[{safe_id}] || Object.values(map)[0];
      if (!entry?.note) return {{status: 'loading'}};
      const note = entry.note;
      const commentsBox = entry.comments;
      const comments = commentsBox ? (commentsBox.list ?? commentsBox.value?.list ?? []) : [];
      const cleanUser = u => u ? {{
        user_id: u.userId || null,
        nickname: u.nickname || u.nickName || null,
        avatar: u.avatar || null
      }} : null;
      const cleanComment = c => c ? {{
        id: c.id || null,
        content: c.content || null,
        time: c.createTime || c.time || null,
        ip_location: c.ipLocation || null,
        like_count: c.likeCount ?? null,
        user: cleanUser(c.userInfo || c.user),
        sub_comments: (c.subComments || []).slice(0, 10).map(sc => ({{
          id: sc.id || null,
          content: sc.content || null,
          time: sc.createTime || sc.time || null,
          ip_location: sc.ipLocation || null,
          like_count: sc.likeCount ?? null,
          user: cleanUser(sc.userInfo || sc.user)
        }}))
      }} : null;
      return {{
        status: 'ok',
        url: location.href,
        note: {{
          note_id: note.noteId || {safe_id},
          title: note.title || null,
          description: note.desc || null,
          type: note.type || null,
          time: note.time || null,
          ip_location: note.ipLocation || null,
          user: cleanUser(note.user),
          interact_info: note.interactInfo || {{}},
          images: (note.imageList || []).map(i => i.urlDefault || i.urlPre).filter(Boolean)
        }},
        comments: comments.slice(0, {safe_limit}).map(cleanComment),
        comments_returned: Math.min(comments.length, {safe_limit}),
        comments_available_in_initial_state: comments.length,
        comments_has_more: Boolean(commentsBox?.hasMore),
        comments_cursor: commentsBox?.cursor || null
      }};
    }})()
    """
    try:
        deadline = time.time() + 60
        last: Any = None
        while time.time() < deadline:
            last = tab.evaluate(expression)
            if isinstance(last, dict) and last.get("status") == "login_required":
                raise RuntimeError("Xiaohongshu login is required in Agent Chrome")
            if isinstance(last, dict) and last.get("status") == "ok":
                return last
            time.sleep(0.5)
        title = tab.evaluate("document.title")
        raise RuntimeError(f"Xiaohongshu note state did not load (title={title!r}, state={last!r})")
    finally:
        tab.close()
        ac.http_text(f"/json/close/{target_id}")


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def xhs_status(verify_login: bool = False) -> dict[str, Any]:
    """Check local Xiaohongshu routes without exposing credentials or cookies.

    Set verify_login=true to perform a harmless live search through Agent Chrome.
    """
    result: dict[str, Any] = {
        "agent_chrome_ready": _chrome_ready(),
        "tikhub_key_configured": bool(_load_key("TIKHUB_API_KEY")),
        "free_route": "agent-chrome",
        "paid_route": "tikhub",
    }
    if verify_login:
        try:
            probe = _run_social("xhs-search", "咖啡", "--route", "browser")
            result["xiaohongshu_logged_in"] = True
            result["probe_result_count"] = probe.get("count", 0)
        except Exception as exc:
            result["xiaohongshu_logged_in"] = False
            result["probe_error"] = str(exc)
    return result


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def search_xiaohongshu(
    query: str,
    route: str = "auto",
    page: int = 1,
    sort: str = "general",
    note_type: str = "不限",
) -> dict[str, Any]:
    """Search Xiaohongshu notes by a Chinese query.

    route may be auto, browser, or tikhub. The browser route is free and uses
    the logged-in Agent Chrome profile. TikHub requires a funded API key.
    """
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    if route not in {"auto", "browser", "tikhub"}:
        raise ValueError("route must be auto, browser, or tikhub")
    if page < 1:
        raise ValueError("page must be at least 1")
    return _run_social(
        "xhs-search",
        query,
        "--route",
        route,
        "--page",
        str(page),
        "--sort",
        sort,
        "--note-type",
        note_type,
    )


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def get_xiaohongshu_note(
    note_id: str,
    xsec_token: str,
    route: str = "auto",
    comment_limit: int = 20,
) -> dict[str, Any]:
    """Get a Xiaohongshu note body, engagement data, images, and initial comments."""
    note_id = note_id.strip()
    xsec_token = xsec_token.strip()
    if not note_id or not xsec_token:
        raise ValueError("note_id and xsec_token are required")
    if route not in {"auto", "browser", "tikhub"}:
        raise ValueError("route must be auto, browser, or tikhub")
    # Same code path as the CLI (social-research.py xhs-note), so Claude and Codex
    # never drift apart; _browser_note below is kept only as a reference copy.
    return _run_social(
        "xhs-note", note_id, xsec_token, "--route", route, "--comment-limit", str(comment_limit)
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
