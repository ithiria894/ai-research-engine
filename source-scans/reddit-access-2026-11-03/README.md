# Reddit 大規模讀取方法調查（2026-11-03）

起因：apply-university 醫科後路調查要大量讀 Reddit，`search.json` 喺已登入嘅 agent Chrome 入面都係 403。Nicole：「之後我哋因為好大量要使用 Reddit 㗎啦」。

搜集係一個 Opus collector agent 做（只搜集、唔判斷）；分析同結論由 main agent 寫（見最底）。原始文件喺 `raw/`（Arctic Shift API docs、download_links、Reddit 官方公告 JSON、developers.reddit.com 註冊頁、PRAW changelog）。

## ⚠️ 時間炸彈（官方公告原文）

| 日期 | 會發生乜 | 來源 |
|---|---|---|
| 2025-11-11 | 官方 Data API 唔再自助申請，新 OAuth token 要審批 | r/redditdev 1oug31u（admin u/redtaboo） |
| 2026-10-31 | 「New requests for public API access will no longer be accepted.」 | r/redditdev 1wubcvf（admin，2026-09-30） |
| **2026-11-13** | 「we'll stop supporting RSS feeds on November 13, 2026… there is no replacement.」 | r/modnews 1wubgvt |
| 2027-01-12 | 「API access starts to close for apps and users that haven't registered」 | 1wubcvf／developers.reddit.com/app-registration |
| 2027-03 | 「Public access will close for all remaining apps and users.」 | 同上 |
| 已發生 | Old Reddit 要登入；之後再收窄到「used Old Reddit in the last six months」 | r/modnews 1wubgvt |
| 2026-07-24 | Watchful1 應 Reddit 要求落咗 Academic Torrents 頁：「Upon reddit's request, I am taking down my academic torrents pages」 | r/pushshift 1v50ved |

## Source ledger（collector 實測）

| Source／endpoint | 狀態 |
|---|---|
| Arctic Shift docs（GitHub README、api/README.md、download_links.md） | ✅ 3 份 |
| Arctic Shift `posts/search` 帶 `fields=…permalink` | ❌ 400 `'permalink' is not a valid field` |
| Arctic Shift `posts/search` 用 subreddit＋日期翻頁 | ✅ |
| Arctic Shift post 關鍵字搜尋（`query=`／`title=`） | ❌ 5/5 都係 422「Timeout. Maybe slow down a bit」 |
| Arctic Shift `comments/search` 帶 `body=` | ✅ 1/1 |
| Arctic Shift `comments/tree?link_id=t3_…&limit=9999` | ✅ 一次攞到 365 個留言，用咗 1.0s |
| Arctic Shift `posts/ids` | ✅ |
| PullPush API | ❌ 521；首頁 Cloudflare 403 |
| api.pushshift.io | ❌ 403 Not authenticated（淨係畀 mod 用） |
| www.reddit.com `.json`（純 curl） | ❌ 403 block page |
| old.reddit.com `.json`／`.rss` | ❌ 302 跳去 login |
| www.reddit.com subreddit `.rss`／帖子 `.rss` | ✅ 200（**2026-11-13 停**） |
| `search.rss` | ❌ 429 |
| `/svc/shreddit/r/<sub>/search/?q=`（純 curl，冇 cookie） | ✅ 每頁 7 篇，有 cursor；header `x-ratelimit-remaining` 由 158 開始倒數 |
| 帖子 HTML（純 curl） | ❌ 200，但係 JS proof-of-work 挑戰，0 個留言 |
| gql.reddit.com | ❌ 404 |
| Academic Torrents 2026-09 monthly dump | ✅ 74.36 GB |
| Academic Torrents 2005-06→2024-12 全集 | ✅ 頁面仲喺度，3.12 TB |
| Academic Torrents 2005-06→2025-12 全集、top-40k subreddits | ❌ 404（Arctic Shift download_links 有 magnet，大約 3.8 TB） |
| Google CSE／Brave／Serper 定價頁 | ✅ |

## 各方法要點

**官方 API／PRAW：** 自 2025-11 起要審批；2026-10-31 起唔再收新申請；2027-03 全面關閉。PRAW 8.0.3（2026-08-12）都要 OAuth，所以受同一限制。條款 §2.8 禁止偽裝 user agent 或 OAuth 身份；§3.2 規定唔可以保留超出已批用途嘅資料。第三方報告指由 2026-10-20 起，`/comments/<id>` 帶 bearer token 都會 403（未核實）。

**Arctic Shift**（`arctic-shift.photon-reddit.com`）：
- 有效 `fields`（docs 原文）：posts 同 comments 共用 `author, author_fullname, author_flair_text, created_utc, distinguished, id, retrieved_on, subreddit, subreddit_id, score`；posts 另有 `crosspost_parent, link_flair_text, num_comments, over_18, post_hint, selftext, spoiler, title, url`；comments 另有 `body, link_id, parent_id`。
- 關鍵字搜尋：維護者講「computationally very heavy… will continue to be unreliable」（issue #58）。
- 422 嘅處理：「wait a short moment and try again」（issue #66）。
- Rate limit 係動態；遇到 429 就睇 `X-RateLimit-Reset`；「If you want to process massive amounts of data, use the monthly dumps instead.」
- 完整度：「comment data will not be 100% complete」（2026-10-17），「90%+」，留言延遲 1–2 日。
- 2027-03 之後點：維護者「Not sure yet」（issue #76）。

**shreddit `svc` 搜尋：** Reddit 新版 UI 自己用嘅 endpoint，冇官方文件；純 curl 都用得，但有 rate-limit header。

**搜尋引擎做搜尋層：** Google CSE 唔再收新客，2027-01-01 停；Brave 每 1k 次 US$5（每月送 US$5）；Serper 送 2,500 次免費，之後每 1k 次大約 US$1，最平去到 US$0.30。

**自架／scraper：** redarc（吃 Pushshift dump，2024 之後冇再更新）；yars 用 `.json`，已經被封；URS 用 PRAW；reddrix 用 Camoufox 瀏覽器；omkarcloud 用 Android app 匿名 OAuth（等於冒充 Reddit app 嘅身份，collector 冇試）。

## 盲點（collector 自己講）

只搜英文來源；Reddit help center 入唔到（403／Cloudflare）；冇試已登入 session 或者已批 token；所有 Reddit 測試都係同一個 IP。

## 分析（main agent，2026-11-03）

**而家實際用得嘅組合：**
1. **搜尋：** 已登入嘅 agent Chrome，打 `/svc/shreddit/r/<sub>/search/?q=…`，跟住 `cursor` 揭頁（`apply-university/analysis/medical-path/fetch_reddit_browser_search.py`）。
2. **留言：** 喺同一個 browser session 打 `/comments/<id>/.json?limit=500`，已實測 200；或者用 Arctic Shift `comments/tree`，唔使掂 Reddit。
3. **成個 subreddit 下載：** Arctic Shift 用 `sort=asc` 加 `after=` 翻頁，`fields` 唔好放 `permalink`（`fetch_reddit_archive.py`）。

**要 Nicole 決定：** Reddit 嘅公開渠道 2027-03 之前會逐個關閉。如果之後要長期大量用 Reddit，「自己擁有一份」就要趁而家做：
- **(a)** 揀定一批 subreddit，用 Arctic Shift 下載晒帖同留言，零成本。
- **(b)** 落 3.8 TB 全集 magnet，要買一隻大約 4 TB 嘅硬碟，一次過大約 US$100。

另外要留意，(b) 嘅資料來源同 Reddit 條款之間有灰色地帶。
