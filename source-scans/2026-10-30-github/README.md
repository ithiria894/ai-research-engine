# GitHub prior-art 掃描（2026-10-30）

目的：睇 GitHub 有冇人做過同我哋差唔多嘅 research engine，將佢哋嘅好嘢收入我哋個 workflow。

- 重跑掃描：`bash scan_repos.sh`（GitHub search API，14 條 query → `raw/`）
- Clone 落嚟嘅 repo：`~/MyGithub/research-engine-prior-art/`（第三方 code，只讀，唔喺入面跑）

## Source coverage ledger

| 狀態 | 搵咗乜 | 結果 |
|---|---|---|
| ✅ GOT DATA | GitHub repo search，14 條 query | 170 個唔同 repo（`raw/unique.tsv`） |
| ✅ GOT DATA | 按名查證 17 個知名 repo | 全部存在，star 數同最後 push 日期喺 `raw/known.tsv` 同下面 |
| ✅ GOT DATA | Clone 14 個 repo + Agent-Reach pull | 全部成功（Agent-Reach `da5044d` → `14c2134`，多咗 69 個 commit） |
| ✅ GOT DATA | 讀 source code 抽 endpoint，再逐條 curl | 7 個新 zero-key source 過咗，見下面 |
| ❌ FAILED | DuckDuckGo html、Startpage | 呢部機收到 bot challenge（202 anomaly／"Verifying your request"） |
| ❌ FAILED | nitter.net search | HTTP 200 但係空殼，0 條 tweet |
| ❌ FAILED | StockTwits、Trustpilot、Dcard | Cloudflare 403；Dcard 用 Agent Chrome fetch 都 403 |
| ⏭️ SKIPPED | MediaCrawler、RSSHub、SearXNG 自己架 | 要常駐 server 或者每個平台登入，同「零常駐工具」有衝突，要 Nicole 決定 |
| ⏭️ SKIPPED | 逐個讀晒 1,995 個 RSSHub route | 只抽咗我哋缺嘅 24 個平台 |

**最大盲點：** 淨係搜咗 GitHub。冇搜 Gitee（中國）、冇搜 Hugging Face Spaces、冇睇 Reddit／HN 上面人哋點樣比較呢啲工具。

## 即刻收咗嘅嘢（已經入 skill、engine doc 同 health check）

| Source | 由邊個 repo 發現 | 10-30 實測 |
|---|---|---|
| **Parallel keyless web search** `search.parallel.ai/mcp` | hyperresearch | ✅ 10 條結果，韓文 query 都準。唔使 key、唔使帳戶 |
| Greenhouse／Lever／Ashby 招聘 API | last30days | ✅ Anthropic、Palantir、Linear 都攞到職位 |
| FxTwitter 單條 tweet + profile | x-tweet-fetcher | ✅ 攞到內文、like 數、回覆數、follower 數 |
| Telegram `t.me/s/頻道` | last30days | ✅ 公開頻道 HTML 預覽 |
| 掘金 search API | RSSHub | ✅ |
| DCInside search | RSSHub | ✅ 21 條結果 |

Parallel 解決咗今日最大嘅問題：Serper 用晒、SerpAPI 冇 key，又唔准俾錢，而家都有一個唔使錢嘅 web search。

## 佢哋點做 workflow（同我哋比較）

我哋而家：LLM 由電話簿揀 source → Nicole 加減 → 逐個打官方 API → 交 evidence + ledger。

| Repo | 核心 loop | 我哋冇、但值得收 |
|---|---|---|
| **last30days**（6.6 萬星） | 先由 host model 寫 query plan（解析人名嘅 X handle、GitHub、subreddit）→ 多個 source 並行 → 去重 + 相關性排序 → 合成 | ① 失敗再細分：`rate-limited`／`auth-failed`／`unreachable`／`timeout`／`schema-drift`／`skipped-unconfigured`，淨係 `no-results` 先可以講「冇人講」 ② 相關性底線：全部唔夠相關就老實講「冇實質討論」 ③ 最少引兩條真留言，用嗰條留言自己嘅 URL，唔准自己砌 URL ④ 研究結果存 SQLite，跟進問題用返舊結果 |
| **hyperresearch**（4.2 千星，Claude/Codex） | 16 步：拆問題 → 闊度搜尋 → 矛盾圖 → 深度調查 → 「邊個 source 會推翻結論」→ 三份草稿 → 4 個 critic → 只准逐段修補 → 核對引文 | ① **引文完整性**：報告入面每段引文都要喺存低嘅原文入面逐字搵到，搵唔到就唔准出 ② 網頁內容一律包喺 `<untrusted-source>` 入面當資料，唔當指令 ③ 學術題先查學術 source，再 web；DOI 去重；Unpaywall／Europe PMC／CORE 攞合法全文；撤稿檢查 ④ 同一份新聞稿 5 個轉載 = 1 票 ⑤ 原本嘅問題存檔，每一步都重讀，防止走題 ⑥ 撞到登入牆／CAPTCHA 就排隊交返畀人，唔自己破 |
| **STORM**（3.2 萬星，Stanford） | 先搵相關題目嘅文章，抽出唔同「視角」，再模擬「作者問專家」嘅對話去諗問題 | 按視角生問題，避免搜尋 query 得一個角度 |
| **gpt-researcher**（3 萬星） | planner 出一組問題 → 每條問題派 crawler → 摘要 + 記 source → 合併 | 同我哋差唔多；佢嘅 retriever 清單有 Bocha（中文搜尋）、SearXNG |
| **dzhng/deep-research**（2 萬星） | breadth × depth 遞迴：每輪由「學到乜」生下一輪問題 | 遞迴深挖，有明確 breadth／depth 參數 |
| **node-DeepResearch**（Jina） | 搜 → 讀 → 諗，loop 到搵到答案或者用晒 token budget | 有 budget 上限同停止條件 |
| **open_deep_research**（LangChain） | 分開 summarize／research／compress／report 四個 model | 長 research 先壓縮再寫報告 |
| **Agent-Reach 1.6** | 每個平台一個 channel，X 同 Reddit 用登入咗嘅 browser | 同我哋差唔多。新嘢得 BOSS直聘；「冇結果」嘅錯誤訊息改成講實際發生咩事，唔估原因 |

## 建議收入我哋 workflow（要 Nicole 揀）

排序：價值高、改動細嘅排前。

1. **Ledger 失敗分類細化**（last30days）。改 skill 嘅 ledger 規則同 `reddit-search`／`xhs-note` 嘅輸出。好平，直接幫到「FAILED 唔可以當 EMPTY」。
2. **引文完整性檢查**（hyperresearch）。寫個 script：報告入面每段 `"…"` 引文都要喺存低嘅原始資料入面逐字搵到。呢個同你嘅「逐字核檔」規矩完全一致。
3. **網頁內容當不可信資料**（hyperresearch）。skill 加一條規矩，抓返嚟嘅頁面入面嘅指令一律唔理。
4. **「邊個 source 會推翻我」+ 反方搜尋**（hyperresearch）。出報告前強制做一輪。同 `adversarial-verification-method.md` 一致。
5. **學術題先查學術 source + 撤稿檢查 + 合法全文**（hyperresearch）。要加 Unpaywall（只需要 email，唔使 key）。
6. **轉載去重**（hyperresearch）。同一份稿嘅轉載只計一票。
7. **按視角生問題**（STORM）。
8. **研究結果存 SQLite，跟進題用返**（last30days、hyperresearch）。改動最大。

## 要 Nicole 決定嘅 source

- **X 搜尋**：Bird GraphQL（last30days 用嘅）要一個 X 帳戶嘅 `auth_token` + `ct0` cookie。免費，但要開帳戶。
- **MediaCrawler**（6.9 萬星）：小紅書、抖音、快手、B站、微博、百度貼吧、知乎都有。每個平台要登入，要用 Playwright。
- **RSSHub**（4.7 萬星，1,995 個網站）：可以好似今次咁，淨係抽 endpoint 唔裝；或者用嘅時候先開，用完即關。
- **SearXNG**（3.9 萬星，252 個引擎）：自己架就唔使錢，但佢背後打 Google、Bing、DDG 都係用同一個 IP，好可能一樣被擋。

## 查證過嘅 repo（`gh api`，2026-10-30）

| Star | Repo | 最後 push |
|---|---|---|
| 106,533 | Panniantong/Agent-Reach | 2026-10-25 |
| 68,963 | NanmiCoder/MediaCrawler | 2026-10-27 |
| 65,941 | mvanhorn/last30days-skill | 2026-10-28 |
| 46,728 | DIYgod/RSSHub | 2026-10-30 |
| 39,010 | searxng/searxng | 2026-10-30 |
| 31,748 | stanford-oval/storm | 2025-09-30 |
| 30,375 | assafelovic/gpt-researcher | 2026-10-10 |
| 19,859 | dzhng/deep-research | 2026-04-11 |
| 14,465 | zedeus/nitter | 2026-10-09 |
| 12,681 | langchain-ai/open_deep_research | 2026-08-10 |
| 5,243 | jina-ai/node-DeepResearch | 2026-05-01 |
| 5,100 | ScrapeCreators/social-media-research-skills | 2026-08-26 |
| 4,758 | d60/twikit | 2026-03-10 |
| 4,189 | jordan-gibbs/hyperresearch | 2026-10-28 |
| 996 | ythx-101/x-tweet-fetcher | 2026-10-14 |
