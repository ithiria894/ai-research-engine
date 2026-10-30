#!/usr/bin/env python3
"""One-shot social research routes; no MCP process and no cookie export.

Commands:
  social-research.py source-list [--source ID]
  social-research.py scrapecreators PATH [KEY=VALUE ...]
  social-research.py tikhub PATH [KEY=VALUE ...]
  social-research.py xhs-search QUERY [--route auto|tikhub|browser]
                                [--page N] [--sort VALUE] [--note-type VALUE]
  social-research.py xhs-note NOTE_ID XSEC_TOKEN [--route auto|tikhub|browser] [--comment-limit N]
  social-research.py onepoint-search QUERY [--limit N]
  social-research.py onepoint-thread THREAD_ID_OR_URL
  social-research.py grapevine-search QUERY [--limit N]
  social-research.py grapevine-thread POST_ID_OR_URL [--max-comments N]
  social-research.py collegeconf-search QUERY [--limit N]
  social-research.py collegeconf-thread THREAD_ID_OR_URL [--max-posts N]
  social-research.py studentroom-thread THREAD_ID_OR_URL [--max-posts N]
  social-research.py reddit-search QUERY [--subreddit SUB] [--type posts|comments]
                                [--sort relevance|top|new|comments|hot] [--t all|year|...] [--limit N]
  social-research.py bctransfer-institutions [--query TEXT] [--limit N]
  social-research.py bctransfer-subjects INSTITUTION_ID [--sending true|false]

Credentials are read from the process environment, then from
~/.config/research-engine/keys.env. Credential values are never printed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


KEYS_FILE = Path.home() / ".config/research-engine/keys.env"
AGENT_CHROME = Path.home() / ".local/bin/agent-chrome.py"
SOURCE_REGISTRY = Path(__file__).with_name("community-sources.json")
SCRAPECREATORS_BASE = "https://api.scrapecreators.com"
TIKHUB_BASE = "https://api.tikhub.io"
COLLEGE_CONFIDENTIAL_BASE = "https://talk.collegeconfidential.com"
BC_TRANSFER_API = "https://api.bctransferguide.ca/tcs/custom/ui/v1.9/agreementws"


def log_event(event: str, **details: object) -> None:
    """Write auditable route decisions to stderr without credentials."""
    record = {"event": event, **details}
    print("social-research-log " + json.dumps(record, ensure_ascii=False), file=sys.stderr)


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


def public_json_get(url: str) -> object:
    """Fetch a public JSON endpoint with a stable user agent and clear errors."""
    log_event("external_call", route="public_json", url=url)
    request = urllib.request.Request(url, headers={"User-Agent": "research-engine/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", "replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        log_event("external_error", route="public_json", url=url, http_status=exc.code)
        if body:
            print(body[:2000], file=sys.stderr)
        die(f"HTTP {exc.code} from {urllib.parse.urlsplit(url).netloc}")
    except OSError as exc:
        log_event("external_error", route="public_json", url=url, error=str(exc))
        die(f"request failed: {exc}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        log_event("schema_error", route="public_json", url=url, http_status=status)
        die(f"expected JSON from {url}: {exc}")
    log_event("external_result", route="public_json", url=url, http_status=status)
    return data


def html_text(value: str | None) -> str:
    """Turn forum HTML fragments into readable plain text."""
    if not value:
        return ""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        die("BeautifulSoup is required: install beautifulsoup4")
    return BeautifulSoup(value, "lxml").get_text("\n", strip=True)


def source_list(source_id: str | None) -> None:
    """Print the community-source phonebook; it does not route the query."""
    log_event("entry", command="source-list", source_id=source_id)
    try:
        registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    except OSError as exc:
        die(f"cannot read source registry {SOURCE_REGISTRY}: {exc}")
    except json.JSONDecodeError as exc:
        die(f"invalid source registry {SOURCE_REGISTRY}: {exc}")

    sources = registry.get("sources", [])
    if source_id:
        sources = [source for source in sources if source.get("id") == source_id]
    payload = {
        "status": "ok" if sources else "empty",
        "type": "source-capability-phonebook",
        "routing_policy": registry.get("routing_policy"),
        "note": (
            "This registry never selects or excludes sources. The LLM reads the full question, "
            "proposes sources to the user, and the user can add or remove any source."
        ),
        "count": len(sources),
        "sources": sources,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def collegeconf_search(query: str, limit: int) -> None:
    """Search College Confidential through its public Discourse JSON API."""
    log_event("entry", command="collegeconf-search", query=query, limit=limit)
    url = COLLEGE_CONFIDENTIAL_BASE + "/search.json?" + urllib.parse.urlencode({"q": query})
    payload = public_json_get(url)
    if not isinstance(payload, dict):
        die("unexpected College Confidential search schema")
    topics = {item.get("id"): item for item in payload.get("topics", [])}
    results = []
    for post in payload.get("posts", []):
        topic = topics.get(post.get("topic_id"), {})
        topic_id = post.get("topic_id")
        results.append(
            {
                "topic_id": topic_id,
                "title": topic.get("title"),
                "slug": topic.get("slug"),
                "url": (
                    f"{COLLEGE_CONFIDENTIAL_BASE}/t/{topic.get('slug')}/{topic_id}"
                    if topic_id and topic.get("slug")
                    else None
                ),
                "posts_count": topic.get("posts_count"),
                "reply_count": topic.get("reply_count"),
                "created_at": topic.get("created_at"),
                "last_posted_at": topic.get("last_posted_at"),
                "matched_post_number": post.get("post_number"),
                "matched_username": post.get("username"),
                "matched_at": post.get("created_at"),
                "blurb": html_text(post.get("blurb")),
            }
        )
        if len(results) >= limit:
            break
    print(
        json.dumps(
            {
                "status": "ok" if results else "empty",
                "route": "public-discourse-json",
                "endpoint": url,
                "query": query,
                "count": len(results),
                "more_results": bool(payload.get("grouped_search_result", {}).get("more_posts")),
                "data": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def collegeconf_thread(value: str, max_posts: int) -> None:
    """Fetch a complete or bounded College Confidential Discourse thread."""
    raw = value.strip()
    topic_ids = [raw] if raw.isdigit() else re.findall(r"/(\d+)(?:\.json)?(?:[/?#]|$)", raw)
    if not topic_ids:
        die("THREAD_ID_OR_URL must contain a numeric College Confidential topic id")
    topic_id = topic_ids[-1]
    log_event("entry", command="collegeconf-thread", topic_id=topic_id, max_posts=max_posts)
    url = f"{COLLEGE_CONFIDENTIAL_BASE}/t/{topic_id}.json"
    payload = public_json_get(url)
    if not isinstance(payload, dict) or not isinstance(payload.get("post_stream"), dict):
        die("unexpected College Confidential topic schema")
    stream = payload["post_stream"].get("stream", [])[:max_posts]
    initial = payload["post_stream"].get("posts", [])
    posts_by_id = {post.get("id"): post for post in initial}
    missing = [post_id for post_id in stream if post_id not in posts_by_id]
    for offset in range(0, len(missing), 20):
        chunk = missing[offset : offset + 20]
        query = urllib.parse.urlencode([("post_ids[]", str(post_id)) for post_id in chunk])
        page_url = f"{COLLEGE_CONFIDENTIAL_BASE}/t/{topic_id}/posts.json?{query}"
        page = public_json_get(page_url)
        if not isinstance(page, dict):
            die("unexpected College Confidential posts schema")
        for post in page.get("post_stream", {}).get("posts", []):
            posts_by_id[post.get("id")] = post
        if offset + 20 < len(missing):
            time.sleep(0.3)
    posts = []
    for post_id in stream:
        post = posts_by_id.get(post_id)
        if not post:
            continue
        posts.append(
            {
                "id": post.get("id"),
                "post_number": post.get("post_number"),
                "username": post.get("username"),
                "created_at": post.get("created_at"),
                "reply_to_post_number": post.get("reply_to_post_number"),
                "like_count": next(
                    (
                        action.get("count", 0)
                        for action in post.get("actions_summary", [])
                        if action.get("id") == 2
                    ),
                    0,
                ),
                "text": html_text(post.get("cooked")),
                "url": post.get("post_url"),
            }
        )
    print(
        json.dumps(
            {
                "status": "ok",
                "route": "public-discourse-json",
                "url": f"{COLLEGE_CONFIDENTIAL_BASE}/t/{payload.get('slug')}/{topic_id}",
                "topic_id": int(topic_id),
                "title": payload.get("title"),
                "views": payload.get("views"),
                "posts_total": len(payload["post_stream"].get("stream", [])),
                "loaded_posts": len(posts),
                "truncated": len(posts) < len(payload["post_stream"].get("stream", [])),
                "posts": posts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def studentroom_thread(value: str, max_posts: int) -> None:
    """Fetch and parse a public Student Room thread through Agent Chrome."""
    raw = value.strip()
    match = re.search(r"(?:[?&]t=)(\d+)", raw)
    thread_id = raw if raw.isdigit() else (match.group(1) if match else None)
    if not thread_id:
        die("THREAD_ID_OR_URL must contain a numeric The Student Room thread id")
    url = f"https://www.thestudentroom.co.uk/showthread.php?t={thread_id}"
    log_event("entry", command="studentroom-thread", thread_id=thread_id, max_posts=max_posts)
    if not AGENT_CHROME.exists():
        die(f"agent Chrome helper is missing: {AGENT_CHROME}")
    log_event("external_call", route="agent_chrome_fetch", url=url)
    process = subprocess.run(
        [str(AGENT_CHROME), "fetch", url],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if process.returncode != 0:
        error = process.stderr.strip() or process.stdout.strip() or "unknown browser error"
        log_event("external_error", route="agent_chrome_fetch", url=url, exit_code=process.returncode)
        die(f"The Student Room browser fetch failed: {error[:2000]}")
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        die("BeautifulSoup is required: install beautifulsoup4")
    soup = BeautifulSoup(process.stdout, "lxml")
    nodes = soup.select(".thread-post")
    posts = []
    for index, node in enumerate(nodes[:max_posts], start=1):
        author_node = node.select_one('[data-testid="username"], a[href*="member.php"]')
        content_node = node.select_one('[data-testid="post-content"][itemprop="text"]')
        date_node = node.select_one('[itemprop="datePublished"]')
        container = node.select_one('[id^="post-content"]') or node.select_one('[id^="post"]')
        post_id = None
        if container:
            id_match = re.search(r"(\d+)", container.get("id", ""))
            post_id = int(id_match.group(1)) if id_match else None
        posts.append(
            {
                "position": index,
                "post_id": post_id,
                "author": author_node.get_text(" ", strip=True) if author_node else None,
                "published_at": date_node.get("content") if date_node else None,
                "text": content_node.get_text("\n", strip=True) if content_node else None,
            }
        )
    title_node = soup.select_one("h1[itemprop=headline], h1")
    log_event("external_result", route="agent_chrome_fetch", url=url, posts=len(posts))
    print(
        json.dumps(
            {
                "status": "ok" if posts else "empty",
                "route": "public-thread-via-agent-chrome",
                "url": url,
                "thread_id": int(thread_id),
                "title": title_node.get_text(" ", strip=True) if title_node else None,
                "loaded_posts": len(posts),
                "visible_posts_on_page": len(nodes),
                "truncated": len(nodes) > len(posts),
                "posts": posts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


REDDIT_BASE = "https://www.reddit.com"


def reddit_page(url: str) -> str:
    """Fetch one Reddit page through the logged-in Agent Chrome session."""
    if not AGENT_CHROME.exists():
        die(f"agent Chrome helper is missing: {AGENT_CHROME}")
    log_event("external_call", route="agent_chrome_fetch", url=url)
    process = subprocess.run(
        [str(AGENT_CHROME), "fetch", url],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if process.returncode != 0:
        error = process.stderr.strip() or process.stdout.strip() or "unknown browser error"
        log_event("external_error", route="agent_chrome_fetch", url=url, exit_code=process.returncode)
        if "blocked by network security" in process.stdout:
            die("Reddit returned its 'blocked by network security' page; check login with: "
                "agent-chrome.py login-check https://www.reddit.com/")
        die(f"Reddit browser fetch failed: {error[-2000:]}")
    return process.stdout


def reddit_search(query: str, subreddit: str | None, kind: str, sort: str, period: str, limit: int) -> None:
    """Search Reddit posts or comments via the shreddit search partial.

    The legacy /search.json endpoint answers 403 even inside the logged-in
    session (verified 2026-10-30), while the HTML partial the web UI itself
    loads still works, so we parse that.
    """
    log_event("entry", command="reddit-search", query=query, subreddit=subreddit, type=kind,
              sort=sort, t=period, limit=limit)
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        die("BeautifulSoup is required: install beautifulsoup4")
    scope = f"/r/{subreddit}" if subreddit else ""
    params = {"q": query, "type": kind, "sort": sort}
    if period != "all":
        params["t"] = period
    url = f"{REDDIT_BASE}/svc/shreddit{scope}/search/?" + urllib.parse.urlencode(params)
    terms = [t for t in re.split(r"\s+", query.replace('"', " ").lower()) if t]
    items: list[dict[str, object]] = []
    seen: set[str] = set()
    pages = 0
    next_url: str | None = url
    while next_url and len(items) < limit:
        page = reddit_page(next_url)
        pages += 1
        soup = BeautifulSoup(page, "lxml")
        before = len(items)
        if kind == "posts":
            units = soup.select('[data-testid="search-sdui-post"]')
        else:
            units = soup.select('[data-testid="search-sdui-comment-unit"]')
        for unit in units:
            holder = unit if unit.has_attr("data-faceplate-tracking-context") else unit.find_parent(
                attrs={"data-faceplate-tracking-context": True})
            try:
                context = json.loads(holder["data-faceplate-tracking-context"]) if holder else {}
            except (KeyError, json.JSONDecodeError):
                log_event("schema_error", route="reddit_search", detail="tracking context unreadable")
                context = {}
            post = context.get("post", {})
            if kind == "posts":
                item_id = post.get("id")
                title_link = unit.select_one('a[data-testid="post-title"]')
                numbers = [n.get("number") for n in unit.select("faceplate-number")]
                stamp = unit.select_one("faceplate-timeago")
                item = {
                    "id": item_id,
                    "title": post.get("title"),
                    "subreddit": context.get("subreddit", {}).get("name"),
                    "author": context.get("profile", {}).get("name"),
                    "score": int(numbers[0]) if len(numbers) > 0 and numbers[0] else None,
                    "num_comments": int(numbers[1]) if len(numbers) > 1 and numbers[1] else None,
                    "created_at": stamp.get("ts") if stamp else None,
                    "permalink": REDDIT_BASE + title_link["href"] if title_link and title_link.get("href") else None,
                }
            else:
                comment = context.get("comment", {})
                item_id = comment.get("id")
                content = unit.select_one('[data-testid="search-comment-content"]')
                body = content.select_one('[id$="-post-rtjson-content"]') if content else None
                score = content.select_one("faceplate-number") if content else None
                stamp = content.select_one("faceplate-timeago") if content else None
                counters = unit.select_one('[data-testid="search-counter-row"]')
                post_numbers = [n.get("number") for n in counters.select("faceplate-number")] if counters else []
                text = content.get_text(" ", strip=True) if content else ""
                bare_id = (item_id or "").removeprefix("t1_")
                link = next((a["href"] for a in unit.select("a[href]") if bare_id and a["href"].rstrip("/").endswith(bare_id)), None)
                item = {
                    "id": item_id,
                    "post_id": comment.get("post_id") or post.get("id"),
                    "post_title": post.get("title"),
                    "subreddit": context.get("subreddit", {}).get("name"),
                    "author": text.split(" · ", 1)[0] if " · " in text else None,
                    "body": body.get_text("\n", strip=True) if body else None,
                    "score": int(score["number"]) if score and score.get("number") else None,
                    "created_at": stamp.get("ts") if stamp else None,
                    "post_score": int(post_numbers[0]) if len(post_numbers) > 0 and post_numbers[0] else None,
                    "post_num_comments": int(post_numbers[1]) if len(post_numbers) > 1 and post_numbers[1] else None,
                    "permalink": REDDIT_BASE + link if link else None,
                }
            if not item_id or item_id in seen:
                continue
            # Reddit pads weak or no-match queries with loosely related posts, so
            # record whether the query words literally appear instead of trusting rank.
            haystack = " ".join(str(item.get(k) or "") for k in ("title", "post_title", "body")).lower()
            item["query_terms_in_text"] = all(term in haystack for term in terms)
            seen.add(item_id)
            items.append(item)
            if len(items) >= limit:
                break
        cursor = re.search(r'src="(/svc/shreddit/[^"]*search/[^"]*cursor=[^"]*)"', page)
        next_url = REDDIT_BASE + cursor.group(1).replace("&amp;", "&") if cursor else None
        log_event("page_result", route="reddit_search", page=pages, units=len(units),
                  new_items=len(items) - before, has_next=bool(next_url))
        if len(items) == before:
            # A page that adds nothing would loop forever on a repeated cursor.
            log_event("decision", route="reddit_search", reason="page added no new items; stop paging")
            break
    lexical = sum(1 for item in items if item["query_terms_in_text"])
    if not items:
        status = "empty"
    elif lexical == 0:
        status = "no_lexical_match"
    else:
        status = "ok"
    log_event("decision", route="reddit_search", status=status, items=len(items), lexical_matches=lexical)
    print(
        json.dumps(
            {
                "status": status,
                "route": "reddit-shreddit-search-via-agent-chrome",
                "query": query,
                "subreddit": subreddit,
                "type": kind,
                "sort": sort,
                "t": period,
                "pages_fetched": pages,
                "count": len(items),
                "lexical_match_count": lexical,
                "has_more": bool(next_url) and len(items) >= limit,
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def bctransfer_institutions(query: str | None, country_id: int, internal_only: bool, limit: int) -> None:
    """List institutions from the BC Transfer Guide's official public API."""
    log_event(
        "entry",
        command="bctransfer-institutions",
        query=query,
        country_id=country_id,
        internal_only=internal_only,
        limit=limit,
    )
    params = urllib.parse.urlencode(
        {"countryId": country_id, "internalOnly": str(internal_only).lower()}
    )
    url = f"{BC_TRANSFER_API}/GetFromInstitutions?{params}"
    payload = public_json_get(url)
    if not isinstance(payload, list):
        die("unexpected BC Transfer Guide institution schema")
    if query:
        needle = query.casefold()
        payload = [
            item
            for item in payload
            if needle in str(item.get("title", "")).casefold()
            or needle in str(item.get("code", "")).casefold()
        ]
    selected = payload[:limit]
    print(
        json.dumps(
            {
                "status": "ok" if selected else "empty",
                "route": "official-public-api",
                "endpoint": url,
                "query": query,
                "count": len(selected),
                "data": selected,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def bctransfer_subjects(institution_id: int, sending: bool) -> None:
    """List subjects for one institution from the BC Transfer Guide API."""
    log_event(
        "entry",
        command="bctransfer-subjects",
        institution_id=institution_id,
        sending=sending,
    )
    params = urllib.parse.urlencode(
        {"institutionID": institution_id, "sending": str(sending).lower()}
    )
    url = f"{BC_TRANSFER_API}/GetSubjects?{params}"
    payload = public_json_get(url)
    if not isinstance(payload, list):
        die("unexpected BC Transfer Guide subject schema")
    print(
        json.dumps(
            {
                "status": "ok" if payload else "empty",
                "route": "official-public-api",
                "endpoint": url,
                "institution_id": institution_id,
                "sending": sending,
                "count": len(payload),
                "data": payload,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


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


XHS_NOTE_EXPRESSION = r"""
(() => {
  const body = document.body?.innerText || '';
  if (body.includes('登录后查看') || body.includes('登录后发现更多精彩内容'))
    return {status: 'login_required'};
  // A missing note, bad xsec_token or blocked view redirects away from /explore/<id>;
  // without this check an empty placeholder entry was reported as status ok.
  if (location.href === 'about:blank' || document.readyState === 'loading') return {status: 'loading'};
  if (!location.pathname.includes(NOTE_ID_RAW)) return {status: 'redirected', url: location.href};
  const mapBox = window.__INITIAL_STATE__?.note?.noteDetailMap;
  const map = mapBox ? (mapBox.value ?? mapBox._value ?? mapBox) : null;
  if (!map || typeof map !== 'object') return {status: 'loading'};
  const entry = map[NOTE_ID_JSON];
  if (!entry?.note?.noteId) return {status: 'loading'};
  const note = entry.note;
  const commentsBox = entry.comments;
  const comments = commentsBox ? (commentsBox.list ?? commentsBox.value?.list ?? []) : [];
  const cleanUser = u => u ? {
    user_id: u.userId || null,
    nickname: u.nickname || u.nickName || null,
    avatar: u.avatar || null
  } : null;
  const cleanComment = c => c ? {
    id: c.id || null,
    content: c.content || null,
    time: c.createTime || c.time || null,
    ip_location: c.ipLocation || null,
    like_count: c.likeCount ?? null,
    user: cleanUser(c.userInfo || c.user),
    sub_comments: (c.subComments || []).slice(0, 10).map(sc => ({
      id: sc.id || null,
      content: sc.content || null,
      time: sc.createTime || sc.time || null,
      ip_location: sc.ipLocation || null,
      like_count: sc.likeCount ?? null,
      user: cleanUser(sc.userInfo || sc.user)
    }))
  } : null;
  return {
    status: 'ok',
    url: location.href,
    note: {
      note_id: note.noteId || NOTE_ID_JSON,
      title: note.title || null,
      description: note.desc || null,
      type: note.type || null,
      time: note.time || null,
      ip_location: note.ipLocation || null,
      user: cleanUser(note.user),
      interact_info: note.interactInfo || {},
      images: (note.imageList || []).map(i => i.urlDefault || i.urlPre).filter(Boolean)
    },
    comments: comments.slice(0, COMMENT_LIMIT).map(cleanComment),
    comments_returned: Math.min(comments.length, COMMENT_LIMIT),
    comments_available_in_initial_state: comments.length,
    comments_has_more: Boolean(commentsBox?.hasMore),
    comments_cursor: commentsBox?.cursor || null
  };
})()
"""


def xhs_browser_note(note_id: str, xsec_token: str, comment_limit: int) -> None:
    """Read one XHS note body, engagement and initial comments from its rendered state.

    Moved here from xhs_mcp_server.py so Claude, Codex and the MCP wrapper all
    run the same code instead of keeping two copies.
    """
    log_event("entry", command="xhs-note", route="browser", note_id=note_id, comment_limit=comment_limit)
    ac = load_agent_chrome()
    if not ac.try_http_json("/json/version", timeout=2):
        die("Agent Chrome is not running; start it with: agent-chrome.py start", 2)
    url = (
        f"https://www.xiaohongshu.com/explore/{urllib.parse.quote(note_id, safe='')}?"
        + urllib.parse.urlencode({"xsec_token": xsec_token, "xsec_source": "pc_feed"})
    )
    expression = (XHS_NOTE_EXPRESSION
                  .replace("NOTE_ID_JSON", json.dumps(note_id))
                  .replace("NOTE_ID_RAW", json.dumps(urllib.parse.quote(note_id, safe='')))
                  .replace("COMMENT_LIMIT", str(max(0, min(comment_limit, 100)))))
    log_event("external_call", route="agent_chrome_tab", url=url.split("?")[0])
    tab = ac.open_tab(url, wait=True)
    target_id = tab.info["id"]
    try:
        deadline = time.time() + 60
        last: object = None
        while time.time() < deadline:
            last = tab.evaluate(expression)
            if isinstance(last, dict) and last.get("status") == "login_required":
                log_event("external_error", route="agent_chrome_tab", reason="login_required")
                die("XHS requires login in Agent Chrome; log in manually and rerun")
            if isinstance(last, dict) and last.get("status") == "redirected":
                log_event("external_error", route="agent_chrome_tab", reason="redirected", url=last.get("url"))
                die(f"XHS redirected away from the note (to {last.get('url')}): note deleted/private, "
                    "xsec_token expired, or login required. Re-run xhs-search for a fresh token.")
            if isinstance(last, dict) and last.get("status") == "ok":
                log_event("external_result", route="agent_chrome_tab", comments=last.get("comments_returned"))
                print(json.dumps({"route": "agent-chrome", **last}, ensure_ascii=False, indent=2))
                return
            time.sleep(0.5)
        title = tab.evaluate("document.title")
        log_event("external_error", route="agent_chrome_tab", reason="state_not_loaded", title=title)
        die(f"XHS note state did not load (title={title!r}, state={last!r})")
    finally:
        tab.close()
        ac.http_text(f"/json/close/{target_id}")


def agent_chrome_origin_eval(origin: str, expression: str) -> object:
    """Evaluate a first-party API request inside an existing browser origin.

    This is deliberately API-first: the browser supplies its own session and
    TLS context, while the site returns JSON. No cookies are exported and no
    rendered HTML is crawled. A temporary home tab is opened only when the
    origin does not already have one, then closed immediately afterwards.
    """
    ac = load_agent_chrome()
    if not ac.try_http_json("/json/version", timeout=2):
        die("Agent Chrome is not running; start it with: agent-chrome.py start", 2)
    info = ac.find_tab_for_origin(origin)
    opened = info is None
    tab = ac.open_tab(origin + "/", wait=True) if opened else ac.Tab(info)
    target_id = tab.info["id"]
    try:
        return tab.evaluate(expression)
    finally:
        tab.close()
        if opened:
            ac.http_text(f"/json/close/{target_id}")


def onepoint_auto_login(timeout: int = 45) -> bool:
    """Re-authenticate 1Point3Acres through its Google button in Agent Chrome.

    The Google credential stays inside the browser.  We only auto-select when
    Google presents a single account; CAPTCHA, MFA, or multiple-account choice
    deliberately returns False so the caller can request user interaction.
    """
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        die("Playwright is required for automatic 1Point3Acres Google sign-in")

    with sync_playwright() as playwright:
        cdp_port = os.environ.get("AGENT_CHROME_PORT", "9223")
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
        context = browser.contexts[0]
        page = next(
            (candidate for candidate in context.pages if "1point3acres.com" in candidate.url),
            None,
        )
        opened = page is None
        if page is None:
            page = context.new_page()
            page.goto("https://www.1point3acres.com/home", wait_until="domcontentloaded")

        try:
            login = page.get_by_role(
                "button", name=re.compile(r"登录\s*/\s*注册|login\s*/\s*sign\s*up|sign\s*in", re.I)
            )
            if login.count():
                login.first.click()

            google_frame = page.frame_locator(
                'iframe[src*="accounts.google.com/gsi/button"]'
            )
            google_button = google_frame.locator('[role="button"]').first
            google_button.wait_for(state="visible", timeout=10_000)

            popup = None
            try:
                with page.expect_popup(timeout=5_000) as popup_info:
                    google_button.click()
                popup = popup_info.value
            except PlaywrightTimeoutError:
                # A previously approved single-account session can finish in
                # the same page without opening an account chooser.
                pass

            if popup is not None:
                popup.wait_for_load_state("domcontentloaded", timeout=15_000)
                accounts = popup.locator("[data-identifier], [data-email]")
                account_count = accounts.count()
                if account_count == 1:
                    accounts.first.click()
                elif account_count > 1:
                    return False

            page.wait_for_function(
                """async () => {
                  const input = {"0":{"json":null,"meta":{"values":["undefined"]}}};
                  const url = 'https://trpc.1point3acres.com/trpc/user.me?batch=1&input=' +
                    encodeURIComponent(JSON.stringify(input));
                  try {
                    const r = await fetch(url, {credentials:'include'});
                    const j = await r.json();
                    return !!j?.[0]?.result?.data?.json?.uid;
                  } catch (_) { return false; }
                }""",
                timeout=timeout * 1000,
            )
            return True
        except PlaywrightTimeoutError:
            return False
        finally:
            if opened:
                page.close()


def onepoint_eval(expression: str) -> object:
    """Run a 1Point3Acres API expression, auto-relogging once if needed."""
    result = agent_chrome_origin_eval("https://www.1point3acres.com", expression)
    if isinstance(result, dict) and result.get("status") == "login_required":
        if os.environ.get("RESEARCH_ENGINE_NO_AUTO_LOGIN") == "1":
            return result
        if not onepoint_auto_login():
            die(
                "1Point3Acres Google sign-in needs user interaction "
                "(multiple accounts, CAPTCHA, MFA, or approval)"
            )
        result = agent_chrome_origin_eval("https://www.1point3acres.com", expression)
    return result


def onepoint_search(query: str, limit: int) -> None:
    """Call 1Point3Acres' own tRPC search API inside Agent Chrome."""
    expression = rf"""
    (async() => {{
      const authInput = {{"0":{{"json":null,"meta":{{"values":["undefined"]}}}}}};
      const authUrl = 'https://trpc.1point3acres.com/trpc/user.me?batch=1&input=' +
        encodeURIComponent(JSON.stringify(authInput));
      const authRes = await fetch(authUrl, {{credentials:'include'}});
      const authJson = await authRes.json();
      const authenticated = !!authJson?.[0]?.result?.data?.json?.uid;
      if (!authenticated) return {{status:'login_required', authenticated:false}};

      const all = [];
      let cursor = null;
      while (all.length < {limit}) {{
        const input = {{
          query: {json.dumps(query, ensure_ascii=False)},
          type: 'hybrid', days: null, fids: null,
          sortBy: 'relevance', direction: 'forward'
        }};
        if (cursor !== null) input.cursor = cursor;
        const batch = {{"0":{{
          json: input,
          meta: {{values: {{days:['undefined'], fids:['undefined']}}}}
        }}}};
        const url = 'https://trpc.1point3acres.com/trpc/search.search?batch=1&input=' +
          encodeURIComponent(JSON.stringify(batch));
        const response = await fetch(url, {{credentials:'include'}});
        if (!response.ok) return {{status:'failed', http_status:response.status, url}};
        const payload = await response.json();
        const page = payload?.[0]?.result?.data?.json;
        if (!page || !Array.isArray(page.data)) {{
          return {{status:'failed', http_status:response.status, error:'unexpected tRPC schema'}};
        }}
        all.push(...page.data);
        if (page.cursor == null || page.cursor === cursor || page.data.length === 0) break;
        cursor = page.cursor;
        if (all.length < {limit}) await new Promise(r => setTimeout(r, 300));
      }}
      return {{
        status: all.length ? 'ok' : 'empty',
        route: 'browser-session-api',
        endpoint: 'trpc.1point3acres.com/trpc/search.search',
        authenticated,
        query: {json.dumps(query, ensure_ascii=False)},
        count: Math.min(all.length, {limit}),
        next_cursor: cursor,
        data: all.slice(0, {limit}).map(x => ({{...x,
          url:`https://www.1point3acres.com/home/thread/${{x.tid}}`
        }}))
      }};
    }})()
    """
    result = onepoint_eval(expression)
    if isinstance(result, dict) and result.get("status") == "login_required":
        die("1Point3Acres remained logged out after the automatic Google sign-in retry")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def onepoint_thread(value: str, max_replies: int) -> None:
    """Fetch top-level replies plus a bounded number of their nested replies.

    ``max_replies`` caps top-level replies. Nested replies are fetched only for
    those selected parents and have a second aggregate cap of ``max_replies``.
    """
    raw = value.strip()
    match = re.search(r"(?:thread-|/home/thread/)(\d+)(?:[/?#-]|$)", raw)
    thread_id = raw if raw.isdigit() else (match.group(1) if match else None)
    if not thread_id:
        die("THREAD_ID_OR_URL must contain a numeric 1Point3Acres thread id")
    expression = rf"""
    (async() => {{
      const authInput = {{"0":{{"json":null,"meta":{{"values":["undefined"]}}}}}};
      const authUrl = 'https://trpc.1point3acres.com/trpc/user.me?batch=1&input=' +
        encodeURIComponent(JSON.stringify(authInput));
      const authRes = await fetch(authUrl, {{credentials:'include'}});
      const authJson = await authRes.json();
      const authenticated = !!authJson?.[0]?.result?.data?.json?.uid;
      if (!authenticated) return {{status:'login_required', authenticated:false}};

      const api = 'https://api.1point3acres.com';
      const threadUrl = `${{api}}/api/v3/threads/{thread_id}`;
      const threadRes = await fetch(threadUrl, {{credentials:'include'}});
      if (!threadRes.ok) return {{status:'failed', http_status:threadRes.status, url:threadUrl}};
      const threadJson = await threadRes.json();
      if (threadJson.errno !== 0 || !threadJson.thread) {{
        return {{status:'failed', http_status:threadRes.status, error:threadJson.msg || 'missing thread'}};
      }}

      const top = [];
      let page = 1;
      let topTotal = null;
      while (top.length < {max_replies}) {{
        const url = `${{api}}/api/threads/{thread_id}/nested-posts?pg=${{page}}&ps=20&order=time_asc&sub_limit=5&with_total=1`;
        const response = await fetch(url, {{credentials:'include'}});
        if (!response.ok) return {{status:'failed', http_status:response.status, url}};
        const payload = await response.json();
        if (payload.errno !== 0 || !Array.isArray(payload.posts)) {{
          return {{status:'failed', http_status:response.status, error:payload.msg || 'missing posts'}};
        }}
        topTotal = payload.total;
        top.push(...payload.posts);
        if (!payload.posts.length || top.length >= payload.total) break;
        page += 1;
        await new Promise(r => setTimeout(r, 300));
      }}

      const selectedTop = top.slice(0, {max_replies});
      let fetchedReplies = 0;
      for (const post of selectedTop) {{
        const nestedCount = Number(post.replies?.count || 0);
        const preloaded = Array.isArray(post.replies?.data) ? post.replies.data : [];
        const kept = preloaded.slice(0, Math.max(0, {max_replies} - fetchedReplies));
        post.replies = {{count:nestedCount, data:kept}};
        fetchedReplies += kept.length;
        if (nestedCount <= kept.length || fetchedReplies >= {max_replies}) continue;
        const wanted = Math.min(nestedCount - kept.length, {max_replies} - fetchedReplies);
        const url = `${{api}}/api/posts/${{post.pid}}/nested-posts?ps=${{wanted}}&skip=${{kept.length}}`;
        const response = await fetch(url, {{credentials:'include'}});
        if (!response.ok) return {{status:'failed', http_status:response.status, url}};
        const payload = await response.json();
        if (payload.errno !== 0 || !Array.isArray(payload.posts)) {{
          return {{status:'failed', http_status:response.status, error:payload.msg || 'missing nested posts'}};
        }}
        const remaining = {max_replies} - fetchedReplies;
        const additional = payload.posts.slice(0, remaining);
        post.replies.data.push(...additional);
        fetchedReplies += additional.length;
        await new Promise(r => setTimeout(r, 300));
      }}

      const loadedReplyCount = selectedTop.reduce(
        (n, p) => n + 1 + (p.replies?.data?.length || 0), 0
      );
      return {{
        status:'ok',
        route:'browser-session-api',
        endpoints:[
          'api.1point3acres.com/api/v3/threads/:tid',
          'api.1point3acres.com/api/threads/:tid/nested-posts',
          'api.1point3acres.com/api/posts/:pid/nested-posts'
        ],
        authenticated,
        url:'https://www.1point3acres.com/home/thread/{thread_id}',
        thread:threadJson.thread,
        top_level_total:topTotal,
        loaded_reply_count:loadedReplyCount,
        posts:selectedTop
      }};
    }})()
    """
    result = onepoint_eval(expression)
    if isinstance(result, dict) and result.get("status") == "login_required":
        die("1Point3Acres remained logged out after the automatic Google sign-in retry")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def grapevine_search(query: str, limit: int) -> None:
    """Search Grapevine through its own public API from the site origin."""
    expression = rf"""
    (async() => {{
      const api = 'https://apis.gvine.app/api/v1/unauthorized/search/post/';
      const all = [];
      let offset = 0;
      let total = null;
      while (all.length < {limit}) {{
        const pageSize = Math.min(10, {limit} - all.length);
        const params = new URLSearchParams({{
          limit:String(pageSize), offset:String(offset),
          query:{json.dumps(query, ensure_ascii=False)}
        }});
        const url = `${{api}}?${{params}}`;
        const response = await fetch(url, {{
          credentials:'include', headers:{{'X-Platform':'web'}}
        }});
        if (!response.ok) return {{status:'failed', http_status:response.status, url}};
        const payload = await response.json();
        const page = payload?.data;
        if (payload?.status !== 'SUCCESS' || !Array.isArray(page?.results)) {{
          return {{status:'failed', http_status:response.status, error:'unexpected Grapevine schema'}};
        }}
        total = Number(page.count ?? total);
        all.push(...page.results);
        offset += page.results.length;
        if (!page.results.length || page.results.length < pageSize || (total !== null && offset >= total)) break;
        await new Promise(r => setTimeout(r, 300));
      }}
      return {{
        status:all.length ? 'ok' : 'empty',
        route:'browser-session-api',
        endpoint:'apis.gvine.app/api/v1/unauthorized/search/post/',
        query:{json.dumps(query, ensure_ascii=False)},
        count:all.length,
        total_count:total,
        data:all
      }};
    }})()
    """
    result = agent_chrome_origin_eval("https://www.grapevine.in", expression)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def grapevine_thread(value: str, max_comments: int) -> None:
    """Fetch one Grapevine post and its comments through first-party APIs."""
    match = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        value,
    )
    if not match:
        die("POST_ID_OR_URL must contain a Grapevine UUID")
    post_id = match.group(1)
    expression = rf"""
    (async() => {{
      const base = 'https://apis.gvine.app/api/v1/unauthorized/';
      const options = {{credentials:'include', headers:{{'X-Platform':'web'}}}};
      const postUrl = `${{base}}feed/?limit=1&offset=0&post_id={post_id}`;
      const postResponse = await fetch(postUrl, options);
      if (!postResponse.ok) return {{status:'failed', http_status:postResponse.status, url:postUrl}};
      const postPayload = await postResponse.json();
      const post = postPayload?.data?.results?.[0];
      if (postPayload?.status !== 'SUCCESS' || !post) {{
        return {{status:'failed', http_status:postResponse.status, error:'post not found'}};
      }}

      const comments = [];
      let offset = 0;
      while (comments.length < {max_comments}) {{
        const pageSize = Math.min(20, {max_comments} - comments.length);
        const url = `${{base}}post/comments/?limit=${{pageSize}}&offset=${{offset}}&post_id={post_id}`;
        const response = await fetch(url, options);
        if (!response.ok) return {{status:'failed', http_status:response.status, url}};
        const payload = await response.json();
        const page = payload?.data?.results;
        if (payload?.status !== 'SUCCESS' || !Array.isArray(page)) {{
          return {{status:'failed', http_status:response.status, error:'unexpected comments schema'}};
        }}
        comments.push(...page);
        offset += page.length;
        if (!page.length || page.length < pageSize || offset >= Number(post.comments_count || 0)) break;
        await new Promise(r => setTimeout(r, 300));
      }}
      return {{
        status:'ok', route:'browser-session-api',
        endpoints:[
          'apis.gvine.app/api/v1/unauthorized/feed/',
          'apis.gvine.app/api/v1/unauthorized/post/comments/'
        ],
        url:post.share_link, post,
        loaded_comment_count:comments.length,
        comments
      }};
    }})()
    """
    result = agent_chrome_origin_eval("https://www.grapevine.in", expression)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("source-list")
    p.add_argument("--source")

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

    p = sub.add_parser("xhs-note")
    p.add_argument("note_id")
    p.add_argument("xsec_token")
    p.add_argument("--route", choices=("auto", "tikhub", "browser"), default="auto")
    p.add_argument("--comment-limit", type=int, default=20)

    p = sub.add_parser("onepoint-search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=25)

    p = sub.add_parser("onepoint-thread")
    p.add_argument("thread")
    p.add_argument("--max-replies", type=int, default=100)

    p = sub.add_parser("grapevine-search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=25)

    p = sub.add_parser("grapevine-thread")
    p.add_argument("post")
    p.add_argument("--max-comments", type=int, default=100)

    p = sub.add_parser("collegeconf-search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=25)

    p = sub.add_parser("collegeconf-thread")
    p.add_argument("thread")
    p.add_argument("--max-posts", type=int, default=200)

    p = sub.add_parser("studentroom-thread")
    p.add_argument("thread")
    p.add_argument("--max-posts", type=int, default=100)

    p = sub.add_parser("reddit-search")
    p.add_argument("query")
    p.add_argument("--subreddit")
    p.add_argument("--type", dest="kind", choices=("posts", "comments"), default="posts")
    p.add_argument("--sort", choices=("relevance", "top", "new", "comments", "hot"), default="relevance")
    p.add_argument("--t", dest="period", choices=("all", "year", "month", "week", "day", "hour"), default="all")
    p.add_argument("--limit", type=int, default=25)

    p = sub.add_parser("bctransfer-institutions")
    p.add_argument("--query")
    p.add_argument("--country-id", type=int, default=40)
    p.add_argument("--internal-only", choices=("true", "false"), default="true")
    p.add_argument("--limit", type=int, default=100)

    p = sub.add_parser("bctransfer-subjects")
    p.add_argument("institution_id", type=int)
    p.add_argument("--sending", choices=("true", "false"), default="true")

    args = parser.parse_args()
    log_event("command_start", command=args.command)
    if args.command == "source-list":
        source_list(args.source)
    elif args.command == "scrapecreators":
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
    elif args.command == "xhs-note":
        note_id, token = args.note_id.strip(), args.xsec_token.strip()
        if not note_id or not token:
            die("note_id and xsec_token are required (both come from xhs-search results)")
        use_tikhub = args.route == "tikhub" or (args.route == "auto" and load_key("TIKHUB_API_KEY"))
        log_event("decision", command="xhs-note", route="tikhub" if use_tikhub else "browser")
        if use_tikhub:
            api_get(TIKHUB_BASE, "/api/v1/xiaohongshu/web_v3/fetch_note_detail", "TIKHUB_API_KEY",
                    "Authorization", {"note_id": note_id, "xsec_token": token})
        else:
            xhs_browser_note(note_id, token, args.comment_limit)
    elif args.command == "onepoint-search":
        if not 1 <= args.limit <= 100:
            die("--limit must be between 1 and 100")
        onepoint_search(args.query, args.limit)
    elif args.command == "onepoint-thread":
        if not 1 <= args.max_replies <= 500:
            die("--max-replies must be between 1 and 500")
        onepoint_thread(args.thread, args.max_replies)
    elif args.command == "grapevine-search":
        if not 1 <= args.limit <= 100:
            die("--limit must be between 1 and 100")
        grapevine_search(args.query, args.limit)
    elif args.command == "grapevine-thread":
        if not 1 <= args.max_comments <= 500:
            die("--max-comments must be between 1 and 500")
        grapevine_thread(args.post, args.max_comments)
    elif args.command == "collegeconf-search":
        if not 1 <= args.limit <= 100:
            die("--limit must be between 1 and 100")
        collegeconf_search(args.query, args.limit)
    elif args.command == "collegeconf-thread":
        if not 1 <= args.max_posts <= 1000:
            die("--max-posts must be between 1 and 1000")
        collegeconf_thread(args.thread, args.max_posts)
    elif args.command == "studentroom-thread":
        if not 1 <= args.max_posts <= 500:
            die("--max-posts must be between 1 and 500")
        studentroom_thread(args.thread, args.max_posts)
    elif args.command == "reddit-search":
        if not 1 <= args.limit <= 250:
            die("--limit must be between 1 and 250")
        subreddit = args.subreddit.removeprefix("r/") if args.subreddit else None
        if subreddit is not None and not re.fullmatch(r"[A-Za-z0-9_]{2,21}", subreddit):
            die(f"--subreddit is not a valid subreddit name: {args.subreddit!r}")
        reddit_search(args.query, subreddit, args.kind, args.sort, args.period, args.limit)
    elif args.command == "bctransfer-institutions":
        if not 1 <= args.limit <= 1000:
            die("--limit must be between 1 and 1000")
        bctransfer_institutions(
            args.query,
            args.country_id,
            args.internal_only == "true",
            args.limit,
        )
    elif args.command == "bctransfer-subjects":
        bctransfer_subjects(args.institution_id, args.sending == "true")


if __name__ == "__main__":
    main()
