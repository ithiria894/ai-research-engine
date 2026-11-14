#!/home/nicole/venvs/scrapling/bin/python
"""用 Scrapling 攞網頁正文：普通 fetch 被擋（403／Cloudflare challenge／JS 頁）時嘅後備。
2026-11-13 實測：nopecha.com/demo/cloudflare、scrapingcourse.com/cloudflare-challenge 普通請求 403，StealthyFetcher 兩個都 200 過到（15s／112s）。
用法：
  scrapling_fetch.py URL                 # 先試普通 Fetcher，唔得自動轉 StealthyFetcher
  scrapling_fetch.py URL --stealth       # 直接用隱身瀏覽器（Cloudflare）
  scrapling_fetch.py URL --html          # 輸出 HTML 而唔係純文字
環境：~/venvs/scrapling（scrapling[fetchers]；瀏覽器：python -m patchright install chromium）。
唔好用 `scrapling mcp`（Nicole 規則：唔裝 MCP）。"""
import argparse, sys, time


def log(msg: str) -> None:
    print(f"[scrapling_fetch {time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('url'); ap.add_argument('--stealth', action='store_true')
    ap.add_argument('--html', action='store_true'); ap.add_argument('--timeout', type=int, default=90)
    a = ap.parse_args()
    from scrapling.fetchers import Fetcher, StealthyFetcher  # 0.5.1：冇 DynamicFetcher，JS 頁都用 StealthyFetcher
    page = None
    if not a.stealth:
        try:
            page = Fetcher.get(a.url, timeout=min(a.timeout, 30))
            log(f"plain status={page.status} bytes={len(page.html_content)}")
            if page.status >= 400 or 'challenge' in page.html_content[:5000].lower():
                log('plain blocked → StealthyFetcher'); page = None
        except Exception as e:
            log(f"plain error {e!r} → StealthyFetcher")
    if page is None:
        t = time.time()
        page = StealthyFetcher.fetch(a.url, headless=True, solve_cloudflare=True, timeout=a.timeout * 1000)
        log(f"stealth status={page.status} {time.time()-t:.0f}s")
    sys.stdout.write(page.html_content if a.html else page.get_all_text())
    return 0 if page.status < 400 else 2


if __name__ == '__main__':
    sys.exit(main())
