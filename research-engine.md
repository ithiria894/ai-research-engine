# Research Engine — 資料搜集工具 Inventory

> 最後更新：2026-10-13（Round 44: LLM-selected source phonebook + API access routes）。
> 呢個 file 係 research 工具嘅 master list。定期更新（搵新 API、MCP、data source）。
> Skill: `/market-research` 會 reference 呢個 file。
>
> **Philosophy：** 資料搜集係所有 decision 嘅 foundation。寧願花 80% token 做 research，20% 做 execution。
> **原則：** 所有免費嘅工具一定要 apply。Token 成本唔係問題，資料質素先係。

---

## Core architecture（簡單版）

```text
一條問題
  → LLM 判斷邊啲網站／source 可能有相關或意外資訊
  → 列出建議用同暫時未用嘅 source，Nicole 可加／刪
  → 由 community-sources.json 讀 access recipe／credential reference
  → 需要時登入，再用 source 本身 first-party API search
  → 冇 usable API 先有限度 fetch page
  → 回報證據，同時列 USED／UNUSED／EMPTY／FAILED／SKIPPED
```

`community-sources.json` 係黃頁／電話簿，唔係 classifier。Cluster 只係方便 LLM 搵 source，
唔限制一條問題屬於邊類。Credential 只存在 gopass、環境變數或既有 browser session；registry
只記 reference，永遠唔存 secret。

### Health check 係分層，唔再每題盲掃全網

```bash
bash health-check.sh                                      # quick：local/registry/CLI/CDP
bash health-check.sh --source reddit --source onepoint3acres  # 真實 retrieval 失敗後重現／診斷
bash health-check.sh --community                         # 定期驗全 community registry
bash health-check.sh --full                              # 維護用全量 audit；會用 keyed/MCP quota
```

普通研究唔跑 health check，亦唔用舊 health report 做 gate；直接做 selected source 嘅真實
retrieval。攞到 relevant data = `MATERIAL`；HTTP/API 成功但冇 relevant result = `EMPTY`；
endpoint／auth／parser 壞 = `FAILED`，今次 ledger 如實報告並繼續其他 source，之後先維修。
改完 engine 跑 quick；真實 retrieval 失敗後先用 repeatable `--source` 重現／診斷；
`--community`／`--full` 隔一段時間手動維護。`--full` 唔係每個 session 嘅前置步驟，亦
唔可以喺冇需要時消耗 limited credits。
報告 atomic 寫入；途中 timeout／interrupt 會明確寫 `INTERRUPTED / FAILED`，唔會保留舊成功
報告扮今次已完成。外部 source 冇結果要分清 `EMPTY`、`FAILED` 同 `SKIPPED`。

---

## 🛑 先讀呢段 — 2026-08-11 sanity check 嘅更正（覆蓋下面所有過時 MCP 引用）

呢份 doc 好多地方叫你 call `mcp__tavily__*`、`mcp__firecrawl__*`、`mcp__context7__*`、
`dialog-mcp`。**逐個 config file 查證過（2026-08-11）：呢啲一個都冇 configure，任何 cwd 都冇。**
照住下面啲舊指示去做，agent 會 call 一個唔存在嘅 tool，攞唔到嘢，然後靜靜哋 skip 咗個 source。

### 1️⃣ `.mcp.json` 係 project-scoped — cwd 決定你有咩 MCP

| cwd | config | 有咩 |
|---|---|---|
| **任何 cwd（user-global）** | `~/.claude.json` | **得 `deja`** |
| `~`（日常預設） | `~/.mcp.json` | **空** |
| `~/.claude` 先有 | `~/.claude/.mcp.json` | gmail, playwright, canlii, paper-search, arxiv, semantic-scholar, youtube-transcript, open-websearch, paper-distill, discord, scholar-mcp, gemini-api-docs, notebooklm-api, mobile-mcp, instacart, food-price |
| `~/MyGithub` 先有 | `~/MyGithub/.mcp.json` | 空 |

落指示畀 agent 前，睇 `health-check-report.md` 個「MCP servers — WHICH ONES YOU ACTUALLY GET
DEPENDS ON CWD」表。**有 Bash 版本就用 Bash** — cwd 無關、零常駐 RAM。

### 2️⃣ Reddit 唔再經 dialog-mcp。用 agent Chrome，Bash 一行

`curl` 打 reddit.com/*.json 喺呢部機返 **403**（2026-08-11 實測，每次 health-check 都重驗）。
同一條 request 喺已登入嘅 agent Chrome 入面打就 200 + 完整 comment tree。

```bash
agent-chrome.py login-check https://www.reddit.com/     # exit 0 = 已登入（問網站自己 whoami）
agent-chrome.py fetch 'https://www.reddit.com/r/SUB/search.json?q=Q&restrict_sr=on&sort=top&limit=25'
agent-chrome.py fetch 'https://www.reddit.com/r/SUB/comments/ID/.json?limit=500'    # 完整 comment tree
# Reddit JSON search 主要係 posts；搜 comments 要開 logged-in UI，再用 DOM 抽結果
agent-chrome.py open 'https://www.reddit.com/search/?q=QUERY&type=comments'
```
其他登入牆網站先找佢本身喺 browser 內用緊嘅 JSON API、tRPC、GraphQL 或
Next/RSC payload；用 Agent Chrome 原頁面 `fetch(..., {credentials:'include'})` 取結構化資料。
**DOM extraction 只係最後退路，唔係 crawler；唔 export cookie，唔並行掃頁。**
E2E：`bash qa/agent-chrome-qa.sh`（14 assertion）。

> **Comments 搜索注意（2026-08-22 實測）**：`/search.json` 唔會完整代替
> `type=comments`；登入後 UI 可以搜到直接提及產品網址嘅 comments。產品名若同普通詞撞名
> （例如 `OpenCase`／`open case`），要用 domain 搜索、逐條 full-thread 回查，再分開
> direct experience、bare recommendation、unrelated homonym。Arctic Shift full-text timeout 要列
> `FAILED`，唔可以寫成零結果。

> **點解之前一直靜靜哋壞咗**：`agent-chrome.py` 個 `Runtime.evaluate` 冇 `awaitPromise`，
> 所以每個 `await fetch(...)` 都回 `{}`。Agent 見到空 → 以為做唔到 → skip。已修好 + 加咗
> regression test 落 health-check 同 QA suite。

### 2b️⃣ Reddit 第二路：Arctic Shift（zero-key archive/search）

`agent-chrome.py` 係 live logged-in path。Arctic Shift 係獨立 archive path：唔使 OAuth、唔使 browser、喺呢部機 2026-08-11 實測 200，近實時（~20-30 秒級）+ full nested comment tree。

```bash
# posts/search：按 subreddit 搵最新/歷史 post
curl -sS -m 60 'https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=LocalLLaMA&limit=25&sort=desc'

# comments/search：按 subreddit + body 做 comment full-text
curl -sS -m 60 'https://arctic-shift.photon-reddit.com/api/comments/search?subreddit=LocalLLaMA&body=quantization&limit=25&sort=desc'

# comments/tree：完整 nested comment tree（用 t3_ 或 bare id）
curl -sS -m 60 'https://arctic-shift.photon-reddit.com/api/comments/tree?link_id=t3_POST_ID&limit=9999'
```

注意：heavy full-text query 會偶發 `422 {"error":"Timeout. Maybe slow down a bit"}`，用 `-m 60`、慢啲重試。`posts/search` / `comments/search` limit 1-100 或 `auto`；`comments/tree` limit 1-25000。Archive 入面嘅 `post.num_comments` / `score` 可能係 ingest 時 frozen，唔好當 current counter；要用 tree 自己 count。

### 2c️⃣ 1Point3Acres + Indian communities：browser-session API first，禁止全頁 crawler

**1Point3Acres（一畝三分地）係北美華人跨領域 knowledge commons，唔係淨係 tech 求職／面經網。**
佢嘅核心價值係社群內長尾資源：選校定位、admission／transfer 個案、先修課與學分對應、
課程／教授／選課評價、syllabus、assignment、歷年題／past paper／考經，以及簽證、租屋、求職、內推同生活流程。
遇到這些題目時，它同 Reddit 一樣係 core source，有時甚至比公開網頁更高訊號。

查詢用簡體中文、大陸常用詞同精確識別字；向 Nicole 報告仍用香港廣東話，直接引文保留原文。

| 題目 | 1P3A query family（全部都要試，唔好只搜一條） |
|---|---|
| 學校／申請 | `学校名/缩写 + 选校`、`定位`、`录取`、`拒信`、`转学`、`二学位`、`转专业`、`CS`、`GPA` |
| prerequisite／transfer | `学校名 + 先修课`、`转学分`、`学分转换`、`transfer credit`、`prerequisite`、`课程匹配`、`waive` |
| 課程／教授 | `学校缩写 + 课程号`、`选课`、`教授`、`难度`、`给分`、`作业`、`syllabus`、`midterm`、`final` |
| 試卷／學習資源 | `课程号 + 真题`、`往年题`、`历年卷`、`题库`、`考经`、`回忆题`、`past paper`、`sample exam`、`practice exam` |
| 求職／面試 | `找工`、`上岸`、`海投`、`内推`、`面经`、`裁员`、`转码`、`码农`、`new grad`、`SDE` |
| 簽證／生活 | `学签`、`工签`、`PR`、`OPT`、`H1B`、`租房`、`保险`、`搬家`、`城市名` |

**每個 query family 必須獨立搜尋，再合併和去重。** 唔好將學校、課程、教授、真題、求職同簽證詞全部塞入同一條 hybrid query；實測 `UBC 选课 教授 真题 往年题` 會混入 admission、面經同公開課，稀釋真正 course-resource results。對一科課至少分開跑：`學校縮寫 + 課程號`、`課程號 + 教授`、`課程號 + 真题`、`課程號 + 往年题`、`課程號 + syllabus`、`課程號 + midterm/final`。

學校或課程研究要同時搜 full name、常用縮寫、舊新 course code 同教授名。命中後要開完整 thread、replies、
`attachment_list`、年份同課程版本；唔好只讀 title/snippet。附件已過期要列 `FAILED/UNAVAILABLE`，唔可寫成「沒有資源」。
歷年卷同課程經驗可以證明當年、當教授、當版課程嘅實際情況；現行學校要求、deadline、credit rule 同 exam policy 要再回查校方 primary source。

```bash
SR=~/MyGithub/ai-research-engine/social-research.py
python3 "$SR" onepoint-search '加拿大 找工 2026' --limit 40
python3 "$SR" onepoint-thread 1192114 --max-replies 100
python3 "$SR" grapevine-search 'software engineer layoffs' --limit 40
python3 "$SR" grapevine-thread POST_UUID_OR_URL --max-comments 100
```

Route 只在 Agent Chrome 原網站 session 內 call first-party endpoint：

- `trpc.1point3acres.com/trpc/user.me` 驗證 session；
- `trpc.1point3acres.com/trpc/search.search` 搜尋同 cursor pagination；
- `api.1point3acres.com/api/v3/threads/:tid` 取主文；
- `api.1point3acres.com/api/threads/:tid/nested-posts` 同 `api/posts/:pid/nested-posts` 取完整回覆。

Cookie/token 唔會 export。Request 串行，分頁間至少 300 ms；每次先收高相關少量 thread，再展開回覆。
Session 過期時，重用 Agent Chrome 內已登入 Google session 自動登入；只有 CAPTCHA、MFA 或 Google 要人手批准先叫 Nicole 接手。

**Indian community 唔係一個網站可以取代；要按功能組合：**

| 用途 | Core sources | 優先 access route | 重要偏差／限制 |
|---|---|---|---|
| 公司文化、工資、layoff、offer | Grapevine + Blind India + r/developersIndia | Grapevine `apis.gvine.app` 或 Next/RSC；Blind Next/RSC；Reddit browser JSON + Arctic Shift | 匿名自選樣本，難當總體統計 |
| 面試流程、DSA/LLD/HLD 題 | TakeUForward + LeetCode Discuss India + AmbitionBox | first-party structured/Next payload；web index 只做 discovery | 成功、投訴同特定公司偏差 |
| 留學選校 | Yocket + r/Indians_StudyAbroad + r/Indian_Academia | Yocket first-party/Next data + Reddit routes | Yocket 有商業顧問 incentive；學校規則要回查官方 |
| 學校、課程、試卷／學習資源 | University Updates（大學通知、syllabus、question papers）+ Education Observer（model questions、study materials、reviews）+ GATEOverflow（GATE CSE 歷屆題與社群解答）+ Doc Sansar（PYQ／notes）+ 各校 subreddit／學生社群 | 優先公開 thread／分類頁與 first-party payload；按學校、course code、exam、年份分開查詢 | 冇一個單站等同 1P3A；各站地域、考試或院校 coverage 不同，附件可過期，現行要求要回查官方 |
| MBA／管理學院 admission 與考試 | PaGaLGuY | 公開 admission/exam threads、站內 search 或 first-party payload | MBA-heavy，唔應外推到一般本科或 CS |
| 美加簽證、H-1B、OPT | RedBus2US + Reddit diaspora communities | Discourse `latest.json`、`search.json`、topic JSON | 論壇只證實個案；法律/政策結論必須用政府 primary source |

Grapevine 已有 `social-research.py` adapter：search 用
`apis.gvine.app/api/v1/unauthorized/search/post/`，主文用 `unauthorized/feed/`，回覆用
`unauthorized/post/comments/`；全部喺 Grapevine browser origin 內 fetch。Blind 若只見到
server-rendered 內容，先取 Next/RSC network payload，唔掃 DOM。
Plain curl 有 429/403 時唔做 retry crawler；保留 `FAILED`，再改用原 browser session 內嘅 first-party request。

**Bias lock：** 1P3A 偏向華人、北美、留學／專業／移民人群，但 coverage 跨學校、課程、考試、就業同生活；Grapevine/Blind 偏向印度 tech 白領。佢哋係高質感知與個案資料，唔係人口代表性樣本。

### 2d️⃣ Admissions／升學：其中一組 topic-specific sources

當問題涉及升學時，可能相關嘅細分 route 包括 non-traditional／mature／returning student、interrupted education、refugee／displaced applicant、international transfer、alternative qualifications、records unavailable、case-by-case waiver、recent academic evidence、transfer credit、full aid。呢節只係一組 source 同 query ideas；唔係全域預設，亦唔阻止 LLM 同時揀職涯、移民、研究、行業、社群或其他網站。

#### 八條獨立 evidence lanes

| Lane | 要搵嘅資料 | 優先來源 |
|---|---|---|
| 1. Eligibility | citizenship／residency、international、transfer、second-degree、years out of school、previous credits、degree status | program page、faculty calendar/catalogue、admissions FAQ、application instructions |
| 2. Academic basis | alternative qualifications、associate degree、university study、prerequisites、recent academic readiness、test要求 | department admissions、registrar、transfer guide、course catalogue、official exam provider |
| 3. Documents／exceptions | unavailable transcript、direct verification、waiver、substitute evidence、English waiver、refugee／political disruption procedures | registrar、admissions operations、refugee/students-at-risk office、written replies；論壇只作 lead |
| 4. Selection reality | applicants、admits、yield、interview timing、selection stages、class profile、repeat applicants | institutional research／Common Data Set、annual report、official podcast、student newspaper、FOI/ATI；forum cohort threads |
| 5. Comparable people | admitted／rejected profiles、non-veteran／international／refugee／older applicants、education gaps、community/research background | full forum threads、student profiles、alumni pages、LinkedIn/public CV、podcasts；身份自述標 `self-reported` |
| 6. Funding | fee waiver、need-blind／need-aware、international transfer aid、full demonstrated need、refugee scholarships、outside awards、true net cost | financial-aid office、scholarship terms、cost-of-attendance、tax/residency rules；forum 只補實際 experience |
| 7. Academic fit | major access、internal specialization、course sequence、labs／professors、research groups、credit ceiling、time to degree | department、calendar、course archive、faculty/lab pages、student reviews、1P3A／Reddit course threads |
| 8. Immigration／life | study permit/visa、Canadian PR presence、citizenship days、work authorization、health coverage、housing | government primary sources、school international office；forum 個案不可代替法律規則 |

#### Rare-program query expansion

每一間 program 都要分開查以下 query families，唔好合成一條：

1. **Exact identity：** official program name、縮寫、舊名、新名、school/faculty name。
2. **Applicant type：** `nontraditional`、`mature student`、`returning student`、`resumed undergraduate`、`adult learner`、`interrupted education`、`refugee`、`displaced student`、`protected person`、`international transfer`、`second bachelor's`、`no bachelor's`。
3. **Academic proof：** `recent academic record`、`academic readiness`、`community college`、`non-degree course`、`visiting student`、`online credit`、`preprint`、`research experience`、`academic reference`。
4. **Exception language：** `waiver`、`exception`、`alternative qualification`、`case-by-case`、`special consideration`、`discretion`、`extenuating circumstances`、`missing transcript`、`unavailable records`、`substitute documentation`。
5. **Selection stages：** year + `applicants`、`admitted`、`acceptance rate`、`interview`、`decision`、`waitlist`、`yield`、`class profile`、`second attempt`、`reapply`。
6. **Funding：** `fee waiver`、`financial aid`、`international transfer aid`、`full demonstrated need`、`need blind`、`need aware`、`refugee scholarship`。
7. **Adverse search：** `rejected`、`denied`、`ineligible`、`no aid`、`cannot waive`、`transcript required`、`international not eligible`、`credit expired`。正面個案唔可以取代 adverse authority。

#### Source ladder for rare routes

1. **Current official:** admissions/program/faculty/registrar/financial-aid/international/refugee pages、application portal instructions、calendar、official email replies。
2. **Official administrative evidence:** Common Data Set、institutional research dashboards、annual reports、meeting minutes、FOI/ATI disclosure、official podcasts/webinars。
3. **Archived official:** Wayback、舊 PDF／handbook／application、舊 staff pages；記錄 version/date，唔將舊規則當 current。
4. **Community cohort threads:** 1Point3Acres、Reddit school subs + r/TransferToTop25／r/ApplyingToCollege／r/IntltoUSA、College Confidential、The Student Room、Yocket／Indian Academia。必須讀完整 thread、日期、reply tree 同附件。
5. **People trail:** student newspaper、admitted-student/alumni profile、public LinkedIn/CV、podcast、conference／NGO bio。只報公開可核實資料，匿名自述單獨標示。

Program 太窄、直接 posts 太少時，唔可以停喺「冇資料」。要擴張去相鄰 cohort、舊 program 名、同類 non-traditional programs、student profiles、interview timeline、staff talks、school newspaper、archived pages、FOI/ATI 同 people trail。連續三輪跨 source-type expansion 都冇 materially new information，先可以寫 saturation；同時保留 `EMPTY`、`FAILED`、`SKIPPED` 分類。

每間目標學校另建 contact map：undergraduate admissions、program director、faculty admissions/dean's designate、registrar/records、transfer-credit evaluator、financial aid、international/refugee/students-at-risk office。搵到聯絡人唔代表自動寄信；任何外寄仍須完整 preview 同 Nicole 當次授權。

### 3️⃣ 每次 research 出報告都要有 SOURCE COVERAGE LEDGER

實際打過邊個 source、攞唔攞到嘢、邊個爆咗、邊個冇試過 —— 全部要列。
❌ FAILED（工具壞）同 ⬜ EMPTY（真係冇人討論）**唔可以撈埋一齊**，佢哋意思相反。
見 `~/.claude/rules/source-coverage-ledger.md`。

---

## 已安裝（✅ 即刻可用）

> ⚠️ **CONNECTED ≠ WORKING（active rule, refreshed 2026-08-11）**：MCP 喺 config 入面 ≠ 呢個 cwd 真係用得。下面 May/June 歷史表可能寫住某 MCP work；以 `health-check-report.md` 入面「MCP servers — WHICH ONES YOU ACTUALLY GET DEPENDS ON CWD」為準。default `~` session 只有 user-global tools；有 Bash/curl path 就優先用 Bash/curl。

### Deep Research

| Tool | 做咩用 | 成本 | MCP Tool |
|------|--------|------|----------|
| **Tavily Research** | 多源 synthesis + citations | 1000 credits/mo free | `mcp__tavily__tavily_research` |
| **Tavily Search** | LLM-optimized search | included | `mcp__tavily__tavily_search` |
| **Tavily Extract** | 抓指定 URL content | included | `mcp__tavily__tavily_extract` |
| **Tavily Crawl** | 抓成個 site | included | `mcp__tavily__tavily_crawl` |
| **Tavily Map** | 搵 domain 上所有 URL | included | `mcp__tavily__tavily_map` |

### Semantic & Code Search

| Tool | 做咩用 | 成本 | MCP Tool |
|------|--------|------|----------|
| **Exa Search** | Semantic search，搵 conceptually similar content | $10 free | `mcp__exa__web_search_exa` |
| **Exa Code Context** | 搵 code examples、docs | included | `mcp__exa__get_code_context_exa` |
| **Context7** | 最新 library documentation | 免費 | `mcp__context7__*` |

### Web Scraping

| Tool | 做咩用 | 成本 | MCP Tool |
|------|--------|------|----------|
| **Firecrawl Scrape/Crawl/Map/Search/Extract** | 抓網頁 → clean markdown | **1000 credits/月**（2026-05-31 verified：plan_credits 1000，月度 reset，唔再係舊 500 lifetime） | `mcp__firecrawl__*` |

### Product Validation & Competitive Intelligence（Round 1 新增）

| Tool | 做咩用 | 成本 | MCP Server |
|------|--------|------|------------|
| **idea-reality-mcp** | Scan GitHub + HN + npm + PyPI + PH，出 reality score 0-100 | 免費 | `idea-reality` |
| ~~**reddit-research-mcp (Dialog)**~~ | 💀 **2026-08-11：`dialog-mcp` 根本冇 configure 過（任何 scope 都搵唔到）。改用 `agent-chrome.py fetch` — 見頂部更正 §2** | — | — |
| ~~**free-web-search-ultimate**~~ ❌ | **死咗（npm 404，見「💀 死咗 MCP」queue）** — 改用 `open-websearch` | — | ~~`free-web-search`~~ → `open-websearch` |
| **open-websearch** ✅ | 8 引擎（Bing/Baidu/DDG/Brave/Exa/GitHub…）零 key，1335⭐ | 免費 | `open-websearch`（已裝，free-web-search 嘅替代） |

### News & Trends（Round 2 新增）

| Tool | 做咩用 | 成本 | MCP Server |
|------|--------|------|------------|
| ~~**newsmcp**~~ | 💀 **2026-06 confirmed shutdown** — 改用 GDELT + RSS curl + Serper/Google News | — | ~~`newsmcp`~~ |
| **mcp-hn** | Search HN + top stories + user profiles | 免費 | `mcp-hn` |
| **Google News & Trends** | Google News RSS + Google Trends data | 免費 | `google-trends` |
| **RSS via curl / r.jina.ai** | RSS raw XML + article readability extraction；唔使常駐 MCP | 免費 | `curl FEED_URL` / `https://r.jina.ai/URL` |

### Research Papers & Benchmarks（Round 4 新增）

> 呢個 category 係搵 WebCode 類型嘅文章：company benchmark、comparison study、"we tested X vs Y" findings。

**RSS Feeds（直接 `curl FEED_URL`；需要正文先用 `https://r.jina.ai/URL`）：**

| Feed | 內容 | URL |
|------|------|-----|
| **arXiv cs.IR** | Information Retrieval 學術 papers（search benchmark 類） | `https://export.arxiv.org/rss/cs.IR` |
| **arXiv cs.AI** | AI 學術 papers | `https://export.arxiv.org/rss/cs.AI` |
| **arXiv cs.LG** | Machine Learning papers | `https://export.arxiv.org/rss/cs.LG` |
| ~~**Papers with Code**~~ | ❌ **DEAD（verified 2026-05-31）** — PwC 被 HuggingFace 收購，`latest.rss` 302→HF papers HTML，冇 RSS。Workaround：用 HF papers MCP 或 `rsshub.app/huggingface/daily-papers`（rate-limited） | ~~`https://paperswithcode.com/latest.rss`~~ |
| ~~**Hugging Face Papers**~~ | ❌ **DEAD（verified 2026-05-31）** — HF 移除咗 `papers.rss`（404，所有 variant 都死）。Workaround：`rsshub.app/huggingface/daily-papers`（403 rate-limited）或 scrape `huggingface.co/papers/trending` | ~~`https://huggingface.co/papers.rss`~~ |
| **OpenAI News** | OpenAI research + product announcements | `https://openai.com/news/rss.xml` ✅ verified 2026-05-31 |
| ~~**LangChain Blog**~~ | ❌ **DEAD（verified 2026-05-31）** — blog 搬離 Ghost，`blog.langchain.com/rss/` 301→`www.langchain.com/blog/rss`→301→`/blog`（HTML，唔係 feed）。LangChain 似乎已撤 RSS | ~~`https://blog.langchain.com/rss/`~~ |
| **The Gradient** | Deep-dive AI research commentary | `https://thegradient.pub/rss` |
| **Simon Willison** | LLM tool findings + practical benchmarks（高 signal） | `https://simonwillison.net/atom/everything/` |
| **Import AI** | Jack Clark weekly AI research digest | `https://importai.substack.com/feed` |

**AI-Generated RSS Feeds（解決冇 RSS 嘅問題）：**
- **ai-rss-feeds** (`github.com/leontloveless/ai-rss-feeds`) — 用 AI 自動生成 CSS selector，每小時 GitHub Actions 更新
- 直接 `curl` GitHub raw XML；需要正文先用 `r.jina.ai`

| Feed | Raw URL |
|------|---------|
| Google DeepMind Blog | `https://raw.githubusercontent.com/leontloveless/ai-rss-feeds/main/feeds/deepmind-blog.xml` |
| Claude Code Releases | `https://raw.githubusercontent.com/leontloveless/ai-rss-feeds/main/feeds/claude-code-releases.xml` |
| Groq News | `https://raw.githubusercontent.com/leontloveless/ai-rss-feeds/main/feeds/groq-news.xml` |
| Stability AI News | `https://raw.githubusercontent.com/leontloveless/ai-rss-feeds/main/feeds/stability-ai.xml` |
| Cursor Blog | `https://raw.githubusercontent.com/leontloveless/ai-rss-feeds/main/feeds/cursor-blog.xml` |

**API（免費）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **Semantic Scholar** | 搵學術 papers，citation network，TLDRs，recommendations | `curl "https://api.semanticscholar.org/graph/v1/paper/search?query=...&fields=title,year,citationCount,abstract"` | 免費 100 req/5min；有 key 10 RPS |
| **OpenAlex** | 250M+ papers，institution/funder metadata，trend analysis | `curl "https://api.openalex.org/works?search=benchmark+coding+agent&sort=publication_date:desc"` | 免費 100K/day；email 做 polite pool 更快 |
| **arXiv API** | arXiv papers，category + keyword filter | `curl "https://export.arxiv.org/api/query?search_query=ti:benchmark+AND+cat:cs.IR&sortBy=submittedDate"` | 免費，無 key |
| **Crossref** | 180M records，DOI resolution，metadata enrichment | `curl "https://api.crossref.org/works?query=..."` | 免費，email 做 polite pool |
| **CORE** | 300M metadata + 40M full-text open access PDFs | 需要免費 API key (`core.ac.uk`) | 免費 |
| **Unpaywall** | 用 DOI 搵 open access PDF | `curl "https://api.unpaywall.org/v2/{doi}?email=..."` | 免費 |

**新 API（Round 7 新增 — 全部免費）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **GDELT** | 全球 event/news database，65+ 語言，real-time | `curl "https://api.gdeltproject.org/api/v2/doc/doc?query=...&mode=ArtList&format=json"` | 免費，零 key，零 limit |
| **PubMed (E-utilities)** | 36M+ biomedical papers | `curl "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=..."` | 免費，3 req/sec（有 key 10/sec） |
| **Europe PMC** | European biomedical literature | `curl "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=..."` | 免費，零 key |
| **bioRxiv API** | Biology preprints，最新 research | `curl "https://api.biorxiv.org/details/biorxiv/2026-03-01/2026-03-28"` | 免費，零 key |
| **DBLP** | CS papers + proceedings database | `curl "https://dblp.org/search/publ/api?q=...&format=json"` | 免費，零 key |
| **DOAJ** | Directory of Open Access Journals | `curl "https://doaj.org/api/search/articles/..."` | 免費，零 key |
| **Zenodo** | Research data + papers（CERN 旗下） | `curl "https://zenodo.org/api/records?q=..."` | 免費，零 key |
| **The News API** | 40,000+ sources，50+ countries | `curl "https://api.thenewsapi.com/v1/news/all?api_token=...&search=..."` | Free tier（有 limit） |
| **NewsDataHub** | 200K+ daily articles，6,500+ sources | `curl "https://api.newsdatahub.com/v1/news?apikey=...&q=..."` | 50 req/day free |
| **ScrapeCreators** | Facebook+Instagram+Reddit+TikTok 等公開 social data | `curl "https://api.scrapecreators.com/..." -H "x-api-key: $SCRAPECREATORS_API_KEY"` | 100 initial free credits；cached results free；**不支援小紅書** |
| **HN Firebase** | Full HN data，所有 stories/comments/users | `curl "https://hacker-news.firebaseio.com/v0/topstories.json"` | 免費，零 key，零 limit |

**新 API（Round 9 新增 — Citation & Academic）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **OpenCitations** | 純 citation graph（DOI-to-DOI），COCI + POCI | `curl "https://api.opencitations.net/index/v2/citations/doi:10.1371/journal.pbio.1002541"` | 免費，零 key，180 req/min |
| **NIH iCite** | Field-normalized citation impact (RCR metric)，36M+ PubMed papers | `curl "https://icite.od.nih.gov/api/pubs?pmids=28882288&fields=relative_citation_ratio"` | 免費，零 key，1000 PMIDs/req |
| **ORCID** | 研究員 identity：publications、affiliations、grants | `curl "https://pub.orcid.org/v3.0/0000-0001-5109-3700/works" -H "Accept: application/json"` | 免費，零 key（public read） |
| **ROR** | Research Organization Registry，120K+ institutions | `curl "https://api.ror.org/v2/organizations?query=MIT"` | 免費，零 key，零 limit |
| **OpenAIRE** | EU-funded research + datasets + software outputs | `curl "https://api.openaire.eu/search/researchProducts?keywords=...&format=json"` | 免費，零 key（authenticated = higher limit） |
| **medRxiv API** | Health sciences preprints（同 bioRxiv 共用 API） | `curl "https://api.biorxiv.org/details/medrxiv/2026-03-01/2026-04-03/0/json"` | 免費，零 key |
| **Altmetric** | Social/news attention metrics（Twitter/news/policy mentions） | 需申請免費 research key | 免費 for non-commercial research |
| **Dimensions** | Papers + grants + patents + clinical trials | 需申請免費 non-commercial access | 免費 Metrics API（需申請） |

**新 API（Round 9 新增 — Trend & Social Intelligence）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **Polymarket (Gamma API)** | Prediction market odds — 真金白銀嘅 outcome 預測 | `curl "https://gamma-api.polymarket.com/markets?tag=ai&closed=false"` | 免費，零 key，零 limit |
| **Truth Social** | Mastodon-compatible API，US 政治/右翼 discourse | `curl "https://truthsocial.com/api/v1/timelines/tag/{topic}"` | 免費，需 bearer token（browser extract） |
| **小紅書 (Xiaohongshu)** | 中國 lifestyle/消費 social platform | TikHub direct REST（keyed）或 `social-research.py xhs-search --route browser` | TikHub XHS search/detail/comments 2026-09-11 為 US$0.01/request；browser route 無 API 成本、毋須 MCP |
| **Bluesky AT Protocol** | 36M users，tech discourse tracking | `curl "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=...&limit=25"`（⚠️ 用 `api.bsky.app`，唔好用 `public.api.bsky.app` — 後者 CDN WAF block server IP, 403） | 免費，零 key，幾乎零 rate limit |
| **Mastodon** | 去中心化社群 timelines + trending | `curl "https://mastodon.social/api/v1/trends/statuses"` | 免費，零 key，300 req/5min per instance |
| **Lemmy** | Reddit 替代品 federated communities | `curl "https://lemmy.world/api/v3/search?q=...&type_=Posts"` | 免費，零 key |
| **Lobste.rs JSON** | 高 signal tech community（invite-only） | Append `.json` to any URL，e.g. `https://lobste.rs/hottest.json` | 免費，零 key |
| **Hashnode GraphQL** | 1M+ tech writers blog platform | `POST https://gql.hashnode.com/` + `Authorization: Bearer {PAT}` | ⚠️ **2026-05-13 起轉收費**，冇免費 endpoint。要 Hashnode PAT |
| **Discourse** | OSS 社群論壇（Rust/React/OpenAI/Julia） | `curl "https://{instance}/search.json?q=..."` | 免費，多數 instance 零 auth |
| **StackExchange API** | 170+ sites（ai.se, security.se, devops.se） | `curl "https://api.stackexchange.com/2.3/search?intitle=...&site=ai"` | 免費 key → 10K req/day |

**新 API（Round 9 新增 — Package Registries & Dev Ecosystem）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **PyPI Stats** | Python package download 時間序列 | `curl "https://pypistats.org/api/packages/{name}/recent"` | 免費，零 key，~30 req/min |
| **crates.io** | Rust package metadata + downloads | `curl "https://crates.io/api/v1/crates/{name}/downloads"` | 免費，零 key，需 User-Agent header |
| **Packagist** | PHP package metadata + downloads | `curl "https://packagist.org/packages/{vendor}/{pkg}.json"` | 免費，零 key |
| **RubyGems** | Ruby gem metadata + downloads | `curl "https://rubygems.org/api/v1/gems/{name}.json"` | 免費，零 key |
| **NuGet** | .NET package metadata + total downloads | `curl "https://azuresearch-usnc.nuget.org/query?q={name}"` | 免費，零 key |
| **Homebrew Analytics** | macOS package install stats（30d/90d/365d） | `curl "https://formulae.brew.sh/api/formula/{name}.json"` | 免費，零 key，零 rate limit |
| **Docker Hub** | Container image pull count + stars | `curl "https://hub.docker.com/v2/repositories/{ns}/{image}"` | 免費，零 key（只有 total，唔係時間序列） |
| **HuggingFace Hub** | AI/ML model trending + downloads | `curl "https://huggingface.co/api/models?sort=downloads&direction=-1"` | 免費，零 key（public） |
| **libraries.io** | 跨 40+ registries dependency analysis + SourceRank | `curl "https://libraries.io/api/{platform}/{name}?api_key={key}"` | 免費 key（GitHub login），60 req/min |
| **VS Code Marketplace** | Extension install + rating + trending（unofficial） | `POST https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery` | 免費，零 key（unofficial endpoint） |
| **OSV.dev** | 開源漏洞 advisories（PyPI/npm/Go/Rust...） | `curl "https://api.osv.dev/v1/query" -d '{"package":{"name":"..."}}'` | 免費，零 key（Google 運營） |

**新 API（Round 9 新增 — Government & Economic）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **FRED** | 840K+ 經濟時間序列（GDP/利率/通脹/就業） | `curl "https://api.stlouisfed.org/fred/series/observations?series_id=GDP&api_key={key}&file_type=json"` | 免費 key，120 req/min |
| **BLS** | US 就業/工資/CPI/PPI | `curl "https://api.bls.gov/publicAPI/v2/timeseries/data/" -d '{"seriesid":["LNS14000000"]}'` | 免費，v1 零 key 25/day；v2 免費 key 500/day |
| **US Census** | 人口/經濟/住房 demographics | `curl "https://api.census.gov/data/2020/acs/acs5?get=NAME,B01001_001E&for=state:*"` | 免費 key，500/day |
| **Congress.gov** | US 立法（bills/votes/members） | `curl "https://api.congress.gov/v3/bill?api_key={key}"` | 免費 key（api.data.gov），1000 req/hr |
| **Federal Register** | US 聯邦規則制定（proposed/final rules） | `curl "https://www.federalregister.gov/api/v1/documents.json?conditions[term]=AI"` | 免費，零 key |
| **World Bank** | 16K+ 指標，200+ 國家，50 年歷史 | `curl "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json"` | 免費，零 key，零 limit |
| **IMF** | WEO 預測/GDP 增長/通脹 | SDMX endpoint | 免費，零 key |
| **OECD** | 成員國統計（教育/就業/稅收） | SDMX endpoint | 免費，零 key |
| **openFDA** | 藥物不良反應/召回/標籤/醫療設備 | `curl "https://api.fda.gov/drug/event.json?search=...&limit=10"` | 免費，零 key 240 req/min |
| **USASpending** | 全美聯邦支出（合約/補助/貸款） | `curl "https://api.usaspending.gov/api/v2/search/spending_by_award/"` | 免費，零 key |

**新 API（Round 9 新增 — Company & Startup）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **SEC EDGAR** | US 上市公司 filings（10-K/Q/Form D） | `curl "https://data.sec.gov/submissions/CIK0000320193.json" -H "User-Agent: MyApp/1.0"` | 免費，零 key，10 req/sec |
| **UK Companies House** | 英國公司董事/帳目/filing history | `curl "https://api.company-information.service.gov.uk/search/companies?q=..." -u "{api_key}:"` | 免費 key，600 req/5min |
| **YC OSS API** | YC 公司，每日更新 | `all.json` 仲 work 喺 raw host：`curl "https://raw.githubusercontent.com/yc-oss/api/main/companies/all.json"`。⚠️ **但 per-batch 要用 github.io host（2026-05-31 fix）**：`https://yc-oss.github.io/api/batches/<batch>.json`（raw host 嘅 `batches/` 路徑 404）。最新 batch 睇 `https://yc-oss.github.io/api/meta.json` → 而家係 summer-2026 / fall-2026 / **winter-2027** | 免費，零 key |
| **AI Funding API** | AI startup funding rounds | `curl "https://aifunding.me/api/v1/rounds?limit=20"` | 免費，零 key |
| **Finnhub** | 股票/新聞/fundamentals/IPO calendar | `curl "https://finnhub.io/api/v1/stock/profile2?symbol=AAPL&token={key}"` | 免費 key，60 req/min |
| **FMP** | IPO calendar + M&A data + financials | `curl "https://financialmodelingprep.com/api/v3/ipo_calendar?apikey={key}"` | 免費 key，250 req/day |
| **OpenCorporates** | 200M+ 全球公司，170+ jurisdictions | `curl "https://api.opencorporates.com/v0.4/companies/search?q=..."` | 免費（開源項目）；商業 £2,250+/yr |

**新 API（Round 9 新增 — Patent & IP）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **USPTO ODP（前 PatentsView）** | US 專利搜尋（發明人/分類/citation） | `curl "https://data.uspto.gov/api/v1/patent/applications/search?q=..."`（GET 或 POST JSON 都得，verified 200 2026-05-31） | 免費（部分要 key）。⚠️ **舊 `search.patentsview.org` 2026-03-20 已遷移，而家 DNS NXDOMAIN（死）** |
| **EPO OPS** | 歐洲 + WIPO + 多國專利 | `https://ops.epo.org/3.2/rest-services/` | 免費 registration，4 GB/week |
| **Lens.org** | 140M+ 專利 + scholarly citation 交叉分析 | `curl "https://api.lens.org/patent/search"` | 免費 for non-commercial research（需申請 key） |
| **Google Patents BigQuery** | 76M+ 全球專利（US/EU/CN/JP/KR） | BigQuery SQL | Google Cloud 1 TB/mo 免費 |

**新 API（Round 9 新增 — SEO & Web Infrastructure）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **Open PageRank** | Domain authority（Common Crawl-based） | `curl "https://openpagerank.com/api/v1.0/getPageRank?domains[]=example.com" -H "API-OPR: {key}"` | 免費 key，4.3M lookups/day |
| ~~**OpenRank.io**~~ | ❌ **DEAD（verified 2026-05-31）** — `openrank.io` 而家 serve React SPA，`/api/v1/domain` 返 404 HTML，搵唔到公開 JSON API（似已停運）。改用 Open PageRank（上面，免費 key，仲 work） | ~~`https://openrank.io/api/v1/domain?d=...`~~ |
| **crt.sh** | SSL cert lookup + subdomain discovery | `curl "https://crt.sh/?q=example.com&output=json"` | 免費，零 key，零 limit |
| **Google PageSpeed Insights** | Lighthouse scores + Core Web Vitals | `curl "...runPagespeed?url=...&key={PAGESPEED_API_KEY}"` | ⚠️ keyless quota 而家 = 0（429）。要免費 API key（console.cloud.google.com），25K req/day |
| **Tranco** | Research-grade top-1M domain ranking | `curl "https://tranco-list.eu/api/ranks/domain/example.com"` | 免費，零 key |
| **Wayback CDX** | URL snapshot history + timestamps | `curl "http://web.archive.org/cdx/search/cdx?url=example.com&output=json"` | 免費，零 key |
| **Common Crawl CDX** | Web-scale crawl index（607M domains） | ⚠️ **唔好 hardcode index 日期**（2026-05-31：`CC-MAIN-2026-13` 已 roll over，404）。先攞最新：`curl "https://index.commoncrawl.org/collinfo.json"` → 用 `[0].id`（而家係 `CC-MAIN-2026-21`）→ `curl "https://index.commoncrawl.org/CC-MAIN-2026-21-index?url=example.com&output=json"` | 免費，零 key |
| **Cloudflare Radar** | DNS-based domain popularity ranking | Cloudflare API | 免費 CF key |
| **Serper.dev** | Google SERP JSON（最慷慨 free tier） | REST API | 免費 2,500 searches/mo |

**新 API（Round 11 新增 — GEO / AI Answer-Engine Visibility）：**

> 呢個 cluster 係查「點樣令一個 product / package 俾 AI engine（ChatGPT/Perplexity/Claude/Google AIO）同 AI coding agent（Cursor/Claude Code/Cline）發現 + 推薦 + 用啱」。Verified 2026-05-30。
>
> **核心 evidence（research 出嚟，唔係 vendor hype）：**
> - **llms.txt 對 AI search（ChatGPT/Perplexity）效果 ≈ 0** — limy.ai 500M bot-event study：500M 次 visit 只有 408 次 fetch `/llms.txt`。Google（John Mueller）確認唔用。GO MO 6-month controlled study：「not a meaningful lever」。
> - **但 llms.txt 對 coding agent（Cursor @Docs / Claude Code）有用** — limy.ai 同一份 data 確認 B2A（agent）會 fetch。**llms-full.txt 比 llms.txt 更受 OpenAI/Microsoft crawler 歡迎**（少一個 retrieval step）。
> - **Docs-MCP > llms.txt**（最強 signal）：Astro 2026-05 **移除 llms.txt 改用 MCP server**，因為 llms.txt 係 passive（agent 唔自動發現），MCP 係 active（agent 一定 call）。Better Auth / Stripe / Vercel / Prisma 全部 ship 第一方 docs-MCP。
> - **Reddit 主導 AI answer citation**：Perplexity 46.7% top citations 嚟自 Reddit；ChatGPT 主 source 係 Reddit/SO/forum。StackOverflow + HuggingFace 係 technical query 最常被引。
> - **Princeton GEO paper（KDD 2024, arxiv 2311.09735）唯一 peer-reviewed data**：cite external sources +115% visibility、加 statistics +41%、加 expert quotes +28%、keyword stuffing ≈ 0。Lower-ranked page 得益最大。
> - **Schema markup 令 LLM extraction accuracy 16% → 54%**（Semrush GPT-4 test）。
> - **Training-data incumbency** 係 root：模型推 lodash 因為佢喺 10M training examples，你個新 lib 喺 12 個。短期冇 GEO tactic 解到，只有 docs-MCP / Context7 繞得過。

| Source / Tool | 做咩用 | 點用 / URL | access |
|------|--------|-----------|--------|
| **Context7** | 第三方 index 你個 lib docs，Cursor/Claude Code 自動 inject（4.7M monthly installs, 56K⭐）。**submit 你個 repo = zero-effort win** | github.com/upstash/context7 · context7.com/add-library | 免費 submit |
| **GitMCP** | `github.com` → `gitmcp.io` 即刻將任何 repo 變 MCP endpoint，auto 讀 llms.txt/README（8.1K⭐） | gitmcp.io | 免費，零 setup |
| **LangChain mcpdoc** | 包任何 `llms-full.txt` URL 變 MCP tool：`npx mcpdoc --url .../llms-full.txt` | github.com/langchain-ai/mcpdoc | 免費 OSS |
| **llms.txt 生成 + validate** | Firecrawl generator（爬任何 site 出 llms.txt+full）· llmstxthub.com directory · rankability/rankray validator | llmstxt.firecrawl.dev · llmstxthub.com | 免費 |
| **Perplexity Sonar API** | programmatically query Perplexity 睇佢答咩 / 引咩 source（測「AI 有冇推我」） | docs.perplexity.ai | API key, $1/M tok + $5-12/1K req |
| **SerpApi / DataForSEO / SearchAPI.io** | Google **AI Overview** + AI Mode SERP extraction（測你有冇出現喺 AIO） | serpapi.com（100 free/mo）· dataforseo.com · searchapi.io | API key, free tier |
| **Cloudflare AI Analytics** | 睇 GPTBot/ClaudeBot/PerplexityBot/Google-Extended 有冇爬你 site（free，built-in CF dashboard） | dash.cloudflare.com | 免費（任何 CF plan） |
| **Dark Visitors** | AI bot traffic analytics + LLM referral tracking + auto robots.txt（freemium，generous free tier） | darkvisitors.com | freemium |
| **AI-visibility trackers（free DASHBOARD，⚠️ 冇免費 API — verified 2026-05-31）** | 量度 brand/package 喺 AI answer 出現率 + share-of-voice。呢啲有免費 **dashboard** 但 **API 全部 gate 喺付費 plan**，免費 tier 攞唔到 programmatic data：Knowatoa（free-forever dashboard + CSV，但 API $249/mo+，**冇 public JSON**，Heroku Rails session-only）· Radarkit（dashboard-only，冇 API）。**AIVO** 唔係 SaaS tool 係一套 methodology standard（aivostandard.org，email-gated audit）→ 唔可 query | knowatoa.com · radarkit.ai · aivostandard.org | 免費 dashboard，無 API |
| **AI-visibility trackers（有真 API 但 paid — verified 2026-05-31）** | **Trakkr.ai**：最乾淨 OpenAPI 3.0.3（`https://trakkr.ai/openapi.json` 200，server `api.trakkr.ai`，8 個 GET：brands/scores/citations/competitor…；key 要 `sk_live_`，API 喺 Scale plan）· **Rankscale.ai**：兩個 API surface（`rankscale.ai/v1/metrics/*` + `api.rankscaleai.com`，401 needs-key 已驗），**有官方 OpenClaw Skill `Rankscale/Rankscale-GEO-Skill`**（integration shortcut），API 喺付費 plan | trakkr.ai/openapi.json · api.rankscaleai.com | paid（有 key 先用到，無 free-tier API） |
| **AI-visibility trackers（paid）** | enterprise-grade：Profound（$399+/mo, 10+ engines, Walmart/Figma）· Scrunch（$250+, 埋 crawler analytics）· Semrush/SE Ranking AI（$65-140, bolt-on） | tryprofound.com | paid, 多數有 trial |
| **⭐ Otterly.ai — 有真 API（verified 2026-05-31）** | AI-answer visibility + share-of-voice，**唯一查到有公開 OpenAPI 嘅 tracker**。Base `https://data.otterly.ai/v1`。**Zero-key OpenAPI spec**（可直接攞做 reference）：`GET https://data.otterly.ai/v1/openapi.json`（200）。實際 data：`Authorization: Bearer oai_live_xxx`（unauth→401）。**Trial 都拎到 key**（7 日試用即生成，無 free-forever tier）。仲有 **Claude Skill**：`claude skill add` 個 `.skill`（otterly-skills.s3...） | data.otterly.ai/v1/openapi.json · app.otterly.ai/api-keys | freemium（trial 給 key） |

**Otterly API — 21 個 endpoint（2026-05-31 拆 spec，GEO research 最有用嗰啲標 ⭐）：**

| Endpoint | 攞咩 |
|----------|------|
| `GET /v1/engines` | 支援嘅 AI engine + 國家 list（query 前先睇覆蓋面） |
| `GET /v1/reports/brand` · `/{id}` · `/{id}/stats` | Brand visibility report（你個 brand 喺 AI answer 出現率） |
| ⭐ `GET /v1/reports/brand/{id}/citations` · `/citations/stats` | **AI 答案引咗邊啲 source URL**（GEO 核心：邊個域名被引最多） |
| ⭐ `GET /v1/reports/brand/{id}/citations/prompts` | 某條被引 URL 係由邊啲 prompt 觸發 |
| ⭐ `GET /v1/reports/brand/{id}/prompts` · `/{promptId}` · `/{promptId}/ai-responses` | **AI engine 對每條 prompt 嘅原文答案**（睇佢真係點講你 brand） |
| ⭐ `GET /v1/reports/brand/{id}/recommendations` | 可執行 GEO 建議 |
| `GET·POST /v1/audits/geo/crawlability-checks` · `/content-checks` | GEO audit：crawlability + content check（POST 開 check，GET 攞結果） |
| `GET /v1/workspaces` · `/{id}/tags` · `/v1/accounts/info` | Workspace / account meta |

**GEO/AEO Skills landscape（2026-05-31 用 zero-key skill API 實 pull，按 install 量排）：**

> 透過 skills.sh（`/api/search?q=`）+ agentskills.to pull。`source` field = GitHub repo，install：`npx skills add <owner/repo>`（或加 `/skill` 揀單個）。⚠️ 每裝一個 SKILL.md，個 description 每次 session 入 context — 揀住裝，唔好 bulk。

| Skill | installs | Source repo（⭐） | 用途 |
|-------|:--------:|------------------|------|
| `schema-markup` | 55K | **coreyhaines31/marketingskills**（⭐31,265） | ⭐ 對應 engine 已記 evidence：schema → LLM extraction 16%→54% |
| `seo-audit` | 124K | coreyhaines31/marketingskills | full SEO audit（broad marketing repo） |
| `ai-seo` / `programmatic-seo` | 63K / 76K | coreyhaines31/marketingskills | AI-SEO / 批量 SEO |
| `seo-geo` | 28K | **ReScienceLab/opc-skills**（⭐903） | 單一 GEO 優化 skill |
| **整套 seo-geo-claude-skills（20 個）** | 4-21K each | **aaron-he-zhu/seo-geo-claude-skills**（⭐1,919, Apache-2.0, CORE-EEAT+CITE framework） | ⭐ **最對口 GEO research toolkit**：geo-content-optimizer · content-gap-analysis · competitor-analysis · technical-seo-checker · on-page-seo-auditor · backlink-analyzer · meta-tags-optimizer · keyword-research… |
| `audit-website` · `competitor-alternatives` | 55K · 11.6K | agentskills.to | site audit · 競品比較頁 |

**⚠️ 唔好 `npx skills add`（install = 每 session load 落 context 嘥 token）。Skill 不過係 MD file —— download 落本地、揀有用嘅 link 入 engine、要用先 Read。**

**已 download + review aaron-he-zhu/seo-geo-claude-skills（20 個），filter 後 keep 10 → `skills/geo/`（on-demand Read，唔入 context）：**

| ✅ Kept（research / 純 methodology，靠你 fetch 嘅 data 行，無 live-tool 依賴） | 用途 |
|------|------|
| `geo-content-optimizer` | ⭐ 優化內容俾 ChatGPT/Perplexity/AIO/Gemini 引用（GEO 旗艦） |
| `ai-seo`（coreyhaines31, MIT） | ⭐ 最充實 AEO/GEO（485L）：點俾 LLM/AIO/ChatGPT/Perplexity cite，platform-ranking-factors + content-patterns reference |
| `schema-markup-generator` | JSON-LD（FAQ/HowTo/Article…）— 對應 engine evidence：schema→extraction 16%→54% |
| `entity-optimizer` | Knowledge Graph / Wikidata / sameAs entity 信號 |
| `content-quality-auditor` | **80-item CORE-EEAT scoring** + veto + fix plan（716L，正經 framework） |
| `domain-authority-auditor` | **40-item CITE scoring** |
| `competitor-analysis` · `content-gap-analysis` · `serp-analysis` | research：競品 / 內容 gap / SERP+AIO 分析 |
| `on-page-seo-auditor` · `technical-seo-checker` | audit 你 fetch 落嚟嘅 page（crawl/index/CWV/meta） |

| ❌ Skipped（junk for research：要 live SEO-tool data、或 ops/reporting、或同你 setup 撞） | 點解唔要 |
|------|------|
| `rank-tracker` · `performance-reporter` · `alert-manager` | 要 rank/analytics export + 連 GSC/GA，純 ops monitoring，唔係 research |
| `backlink-analyzer` | 要 backlink-tool（Ahrefs 類）data source，我哋無 |
| `memory-management` | 同 Nicole 自己嘅 memory 系統 + externalize-state rule 重疊/衝突 |
| `keyword-research` · `meta-tags-optimizer` · `seo-content-writer` · `internal-linking-optimizer` · `content-refresher` | 要 keyword-tool data 或純 content-doer，唔屬 research |

> 用法：要做 GEO 工作先 `Read skills/geo/<skill>/SKILL.md`（每個 skill 自帶 `references/` 有 templates/guides/examples）。零 session 開銷。已刪走 repo 頂層 `_references/`（27 個 ADR/evolution/proposal governance junk，skills 一個都冇引用）。
> **coreyhaines31/marketingskills（⭐31K, MIT）review 結果（2026-05-31）**：43 個 skill，多數 marketing doer（cold-email/cro/popups/copywriting/ads/pricing…）唔關 research 事。只 vendor 咗 `ai-seo`（485L，最充實 AEO，我哋冇同等深度）。`schema` 跳過 —— 睇真內容，aaron 嘅 `schema-markup-generator` reference 更紮實（decision-tree/templates/validation-guide vs coreyhaines 得 schema-examples + evals junk），install 數高唔代表內容好。`programmatic-seo`/`seo-audit` 同已有 skill 重疊，亦跳過。
> 來源 + license 見 `skills/geo/README.md`。

| ~~**Peec.ai**~~ | ❌ 冇 public API（verified 2026-05-31：`api.peec.ai` / `peec.ai/api` 都 404）。標準 plan 只有 CSV export + Looker connector，API 淨係 Enterprise/custom。**唔好當 API 用** | watch-list only | enterprise-only |
| **Docs platforms（auto MCP+llms.txt）** | Mintlify（auto MCP at /mcp + llms.txt, free Hobby）· Fern（auto llms.txt+MCP, 90% token cut, free Hobby）· ReadMe · Kapa.ai（free for OSS） | mintlify.com · buildwithfern.com | 免費 Hobby / OSS |
| **⭐ Skills marketplace APIs（zero-key，verified 2026-05-31）** | Programmatic 查 AI-agent skills（GEO/AEO/SEO 相關 SKILL.md）+ install 量遙測。**skills.sh**（Vercel-Labs directory）：`GET https://www.skills.sh/api/search?q=geo`（200 JSON，含 install counts，GET-only；CLI `npx skills add owner/repo`）。**agentskills.to**（marketplace，注意 `.to` 唔係 `.io`）：`GET https://www.agentskills.to/api/skills?q=seo`（200 JSON，含 total_install/weekly_install + 現成 install_command）。**skilldock.io**（registry，**API 喺 `api.` subdomain**）：`GET https://api.skilldock.io/v1/skills`（200，免 auth 返 188 skills）· `/v1/stats` · `/openapi.json`；官方 SDK `pip install skilldock`（Apache-2.0） | skills.sh · agentskills.to · api.skilldock.io | 免費，零 key |
| ~~**agentskills-mcp**~~（裝咗又移除 2026-05-31） | ❌ **唔保留**：always-on MCP 每 session load 6 個 tool schema 入 context，而佢主功能（`install_skill`）正正係我哋唔想要嘅 install 模式。**Skill discovery 用 zero-key API 就得**（`curl skills.sh/api/search`），唔使常駐 MCP。需要時先手動 `uvx pinkpixel-agentskills-mcp`（PyPI/MIT，6 tool：search/get/install/list/scaffold） | 唔常駐；要用先 uvx | 免費 |

**Round 11 — AI-native library file hierarchy（2026-05-30 Round 2 修正排序，按真實 leverage）：**

> 重心已由 llms.txt 移去 **SKILL.md**（agentskills.io, Anthropic open standard, 「npm of AI agents」, AAIF/Linux Foundation governed）。社群共識：**唔好信 prose，externalize 落 executable gate（types/tests/linters）+ measure**。冇 measured A/B 證明任何 markdown file 改變 agent recommendation — ship 係因為低成本 + 已成標準 + 幫 correct-usage，唔係 growth lever。

1. **完整 TypeScript types + JSDoc** — library 版「executable gate」，**減 API hallucination 比任何 markdown 都有效**。最高 actual leverage。
2. **第一方 docs-MCP server**（或 submit Context7）— 最強 active signal。Context7 submit = zero-effort（4.7M monthly installs distribution）。
3. **`SKILL.md` in npm package**（agentskills.io format, `npx skills add`）— install 即 inject。⚠️ **唔係 deterministic**：有 Activation step，個 `description` field 先係 discoverability surface，要 sharp + trigger-rich + 人手寫 lean（LLM-generated context file 實測**減** success + cost 20%↑）。Model：timescale/pg-aiguide（1,750⭐ skills+MCP combo）。
4. `AGENTS.md`（repo root, 134K+ files, Linux Foundation）— **淨係 FACTS**（path/command/config shape），每項 ≤1 句、正面 phrasing。只幫 clone 你 repo 嘅人。
5. `context7.json` — 認領/控制你 Context7 listing（1,740 files, ownership land-grab）。
6. `llms.txt` + `llms-full.txt` — llms-full 有用（manual Cursor @Docs paste + GitMCP）；llms.txt 對 AI search ≈ 0（多個 500M+ event study 確認）但 Lighthouse 13.3.0 而家 audit 佢。低 priority、cheap、唔好 oversell。
7. `.cursorrules` / `.windsurfrules`；watch **WebMCP**（verified 2026-05-31：W3C **Web Machine Learning** group draft，Microsoft+Google co-edit，**唔係 WICG**；JS API `navigator.modelContext.registerTool()`；Chrome 146 起 flag-gated DevTrial（`chrome://flags` → Experimental Web Platform Features）。spec repo `github.com/webmachinelearning/webmcp`（有 `index.bs` Bikeshed + `w3c.json`）。**仲未可以攞嚟做 research data source**——係畀網站 expose tool 畀 agent，無 hosted endpoint 查。純 watch-list）。

**新 API（Round 13 新增 — 2026-05-31，全部我親手 curl verified 200／開新 domain）：**

> 呢輪跳出 GEO，補返 engine cover 唔到嘅 domain。全部 zero-key + live。

| API | 開咩新 domain | 點用（verified 200） |
|-----|--------------|---------------------|
| ⭐ **OpenReview** | **學術 peer-review discourse**（ratings/accept-reject rationale，ICLR/NeurIPS）— arXiv/S2 得 paper 冇 review | `https://api2.openreview.net/notes?content.venue=ICLR%202025&limit=10` |
| ⭐ **CourtListener v4** | **美國全套 case-law + dockets**（36K+ opinion／query）— engine 完全冇法律 | `https://www.courtlistener.com/api/rest/v4/search/?q=...&type=o` |
| ⭐ **SEC EFTS full-text** | EDGAR **全文**搜（搵每份提到某詞嘅 10-K），metadata API 做唔到 | `https://efts.sec.gov/LATEST/search-index?q="AI"&forms=10-K`（要 UA header） |
| ⭐ **Socrata Discovery** | **救返死咗嘅 data.gov**（CKAN 404）— 搜全美 state/city open-data portal | `https://api.us.socrata.com/api/catalog/v1?q=budget` |
| ⭐ **OpenRouter models** | **live LLM catalog**（pricing/context/modality 跨所有 provider）— 對 AI research engine 最 on-mission | `https://openrouter.ai/api/v1/models` |
| **Ollama registry** | trending 開源/local model（配 HF 睇 open-model 脈搏） | `https://ollama.com/api/tags` |
| **OpenCollective GraphQL** | OSS 項目 funding/expenses/backers（engine wishlist 一直想要） | `POST https://api.opencollective.com/graphql/v2` |
| **ClinicalTrials.gov v2** | 藥物/intervention trial registry（PubMed/openFDA 冇） | `https://clinicaltrials.gov/api/v2/studies?query.cond=cancer` |
| **PubChem PUG-REST** | 化合物/化學數據（engine 零 chem coverage） | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/.../JSON` |
| **GBIF** | 生物多樣性 occurrence records | `https://api.gbif.org/v1/occurrence/search?q=...` |
| **USGS Earthquake** | real-time 地球物理事件 feed | `https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson` |
| **Nominatim (OSM)** | 免費 geocoding（place→coords，engine 得 ip-api） | `https://nominatim.openstreetmap.org/search?q=...&format=json`（要 UA） |
| **Wikimedia Pageviews** | 全球 attention signal（睇大眾喺睇咩，補 Google Trends） | `https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{Y}/{M}/{D}` |
| **WHO GHO OData** | 全球健康指標（engine 零 WHO） | `https://ghoapi.azureedge.net/api/Indicator` |
| **Marginalia Search** | indie/small-web index（Google 埋沒嘅 long-tail page） | `https://api.marginalia.nu/public/search/{q}?count=10` |
| **Wikidata SPARQL** | 任意 structured query（唔淨係 entity lookup） | `https://query.wikidata.org/sparql?format=json&query=...`（要 UA） |

**需要 free key（endpoint verified live，要 signup）：** govinfo.gov（`DEMO_KEY` 即用，全套聯邦出版物）· OpenFEC（`DEMO_KEY` 即用，競選財務）· OpenStates v3（州級立法，Congress 得聯邦）· OpenSanctions（制裁/PEP 篩查）· WAQI air quality（`demo` token 即用）。

**Gap-filling MCP（install-menu，唔好 bulk 裝 — cyanheads 一個 framework 出咗 ~35 個 research MCP，多數同 engine 已有 raw API 重疊。只裝真 gap）：**
- `cyanheads/clinicaltrialsgov-mcp-server`（76⭐）· `cyanheads/courtlistener-mcp-server` 或 `blakeox/courtlistener-mcp`（12⭐）· `cyanheads/socrata-mcp-server` · `cyanheads/pubmed-mcp-server`（101⭐）· `cyanheads/secedgar-mcp-server`

**❌ Verified dead / skip（唔好試）：** data.gov CKAN（404 全變體）· ReliefWeb v1（410 deprecated）· Product Hunt GraphQL（要 OAuth）· nostr.band（000 down）· youtube-transcript-mcp（59⭐ 但 2025-07 stale，engine 已有 yt-dlp+Groq）· Stack Overflow MCP（最好得 7⭐，繼續用 raw StackExchange API）。

**新 cluster（Round 15 — 2026-05-31）— 🛍️ Shopping / Product / Gift research：**

> Use case：「我想買個產品 / 送個禮，根據我嘅需求幫我搵」。之前 engine 冇 document，但工具其實齊。**入口 = `/shop` skill**（畀需求+budget，跨店比 specs/價/review）。

| Source | 做咩 | 點用 / 狀態 |
|--------|------|------------|
| ⭐ **`/shop` skill** | 主力入口：理解需求 → 並行 agent 跨店搜 → 比 specs/價/review/availability | Skill（用 amazon/agora/superprecio/scrapegraph/tavily/exa/firecrawl） |
| ⭐ **Serper Shopping** | **Google Shopping** — 任何產品→真價+邊間店賣（gift 必備） | ✅ `POST google.serper.dev/shopping` `{"q":"gift for mom"}`（用 SERPER key，已攞，200 verified） |
| ⭐ **Apify MCP** | **scrape 硬 site 嘅最佳解** — Amazon/Temu/Taobao/1688/AliExpress/eBay/Walmart/Etsy 都有維護好 anti-bot 嘅 actor（`junglee/Amazon-crawler`、`piotrv1001/temu-listings-scraper`、`sian.agency/taobao-tmall-product-scraper`、`zen-studio/1688-wholesale-scraper`…） | remote MCP `https://mcp.apify.com`（OAuth）或 `@apify/actors-mcp-server` + `APIFY_TOKEN`。$5 free/mo，無 card。**要裝** |
| ⭐ **Canopy API** | 免費結構化 Amazon（product/review/deals by ASIN，GraphQL） | `POST https://graphql.canopyapi.co/`（401 verified）。free Hobby 100 req/mo，canopyapi.co 攞 key |
| ⭐ **SerpApi official MCP + Amazon engine** | AI agent 直接搜 Amazon search results；返 ASIN、價錢、rating/review、Prime/delivery 同 clean product link；支援 `amazon.ca` | Hosted MCP `https://mcp.serpapi.com/.../mcp` 或 self-host `github.com/serpapi/serpapi-mcp`；`engine=amazon` + `amazon_domain=amazon.ca` + `k=QUERY`。Free plan 250 searches/mo（2026-09-10 official docs verified） |
| **Amazon Creators API（官方）** | 官方 REST catalog API：`SearchItems` / `GetItems` / `GetVariations` / `GetBrowseNodes`，包括 `OffersV2`；PA-API 5 replacement | **唔係普通個人 shopping API**：要 fully accepted Amazon Associate、target-marketplace Partner Tag、trailing 30 日至少 10 qualified sales；持續 access / rate 同 referred shipped sales 綁定。適合 publisher/affiliate MCP，唔適合 Nicole 私人購物 |
| **Amazon Business Product Search + Ordering APIs（官方）** | Product Search 可搜 Amazon Business catalog/offer；Ordering 可落單；NA 包括 Canada | 要 Amazon Business developer onboarding、Amazon 審批同 assigned API roles；2026 onboarding 不可 self-select roles。官方 `@amazonbusiness/ab-integrations-mcp-server` preview **只搜/讀 API 文件**，唔會 call live product catalog |
| **Amazon.ca consumer AI（官方、非 MCP）** | Rufus（2026-05 改名 Alexa for Shopping）已在加拿大 Amazon app/desktop；Alexa+ 在加拿大可經 Alexa app / Alexa.com shop Amazon | 最低 setup，但係 Amazon 自家界面；截至 2026-09-10 未找到 Amazon 宣布供普通 retail account 給第三方 AI 用的 public Shopping MCP/account API |
| **Existing Serper Shopping fallback** | Google Shopping structured results，`gl=ca` 可 filter `source="Amazon CA"`，毋須 Amazon login/cookie | 2026-09-10 live test：`wireless earbuds` 返 40 CA offers，其中 13 Amazon CA；有 price/rating/count，但 link 係 Google Shopping redirect，shortlist 要再 resolve direct Amazon URL |
| **SerpApi engines** | dedicated `engine=amazon`/`walmart`/`ebay`/`google_shopping`（比 parse Google Shopping 乾淨） | `serpapi.com`；free 250/mo。Amazon path 同 official MCP 見上面（2026-09-10 refreshed；本機 `SERPAPI_KEY` 仍未配置） |
| **superprecio MCP** | 價格比較 / deals / shopping list | `mcp__superprecio__*`（已裝） |
| ~~**amazon-mcp**~~ ❌ | **廢的** — verified：21 行 no-op stub，0 tool / 0 HTTP call，乜都唔做。`/shop` skill 叫 `mcp__amazon__*` 其實攞唔到嘢 → 改用 Apify/Canopy | uninstall（drama-fm/amazon-mcp） |
| ~~**rigwild/mcp-server-amazon**~~ ⚠️ | 真係會 scrape Amazon search/cart/orders，但要將完整 Amazon session cookies export 去本地 JSON；DOM selector 易壞，repo 個 purchase tool 只係 mock。私人 account 風險太高 | **唔裝**；search-only 用 SerpApi MCP / Serper，登入後 price/delivery 才用受控 read-only Agent Chrome |
| ~~**agora-mcp**~~ ❌ | **裝錯** — npm `agora-mcp` 係 Agora **chat** bot（WIP「will not work」），唔係 shopping。真 shopping Agora（Fewsats/SearchAgora）個 API host 已死（000）→ 唔好追 | uninstall |
| ⭐ **Reddit — 按產品品類搵 sub** | 用產品品類 + Serper `site:reddit.com/r/...` + Arctic Shift subreddit/search 去搵真社群攞用家推薦/避雷，**唔係淨係 gift sub**：廚具→r/cookware·r/Cooking·r/castiron·r/BuyItForLife；耳機→r/headphones·r/HeadphoneAdvice；monitor→r/Monitors；床褥→r/Mattress…。**只有明確送禮**先加 r/giftideas·r/Gifts | `agent-chrome.py fetch` live posts/trees；Arctic Shift archive/cross-check；raw curl reddit.com `.json` = 403 |
| **Gift-guide scrape** | 抓專業 gift guide / 評測：Wirecutter · RTINGS · NYT/BuzzFeed gift guides · The Strategist | Firecrawl/Tavily Extract/Exa（畀 URL 或 search「best gift for X 2026」） |
| **Product Hunt · idea-reality** | 新奇 / 獨特產品 | idea-reality MCP（已裝） |
| 要 free key（未攞） | **eBay Browse API**（二手/罕有 gift）· **Etsy API**（handmade/personalised gift） | 入「Key Activation Checklist」，eBay/Etsy 要 dev signup |

> **送禮 workflow**：① 問清收禮人（關係/興趣/年齡/budget）→ ② Reddit（`agent-chrome.py fetch` 打 `/r/SUB/search.json` + 完整 comment tree）按產品品類搵真人推薦（送禮先加 gift sub） → ③ Serper Shopping + Amazon/agora 搵實物+價 → ④ Firecrawl 抓 gift guide 對證 → ⑤ 出 3-5 個推薦連價+買邊度。直接用 `/shop "送 [描述] 嘅禮物，budget $X"` 一條龍。

**新 cluster（Round 14 — 2026-05-31）— 🛡️ AI Security / AI Safety tracking（全部 curl verified）：**

> Nicole（security engineer + AI safety researcher）專用。睇 AI security/safety 最近邊個傾乜、出咩 research。全部 zero-key RSS/API。

| Source | 睇咩 | Endpoint |
|--------|------|----------|
| ⭐ **Simon Willison** | prompt injection / LLM security 最高 signal | `https://simonwillison.net/atom/everything/` |
| ⭐ **Embrace The Red (wunderwuzzi)** | AI red-team / agent hijack PoC exploits | `https://embracethered.com/blog/index.xml` |
| ⭐ **tldr;sec** | 每週 security aggregator（有 AI section，meta-source） | `https://tldrsec.com/feed.xml` |
| ⭐ **LessWrong GraphQL** | alignment posts + score + timestamp（structured trending） | `POST https://www.lesswrong.com/graphql`（`view:"new"`/`"top"`） |
| ⭐ **arXiv cs.CR (LLM)** | adversarial ML / jailbreak / supply-chain papers | `https://export.arxiv.org/api/query?search_query=cat:cs.CR+AND+abs:LLM&sortBy=submittedDate&sortOrder=descending`（⚠️ 用 /api 唔好用 rss，rss 近乎空） |
| **Protect AI** | model supply-chain / ML scanning | `https://protectai.com/blog/rss.xml` |
| **Trail of Bits** | ML supply-chain / model-file exploit audit | `https://blog.trailofbits.com/feed/` |
| **Google Project Zero** | deep vuln research（含 AI-assisted Big Sleep） | `https://googleprojectzero.blogspot.com/feeds/posts/default` |
| **NVIDIA AI Red Team** | AI red-team / ML security | `https://developer.nvidia.com/blog/category/cybersecurity/feed/` |
| **CAIS AI Safety Newsletter** | 每週 AI-safety roundup | `https://newsletter.safe.ai/feed` |
| **Alignment Forum / EA Forum / LessWrong RSS** | alignment 研究 + 政策 | `alignmentforum.org/feed.xml` · `forum.effectivealtruism.org/feed.xml` · `lesswrong.com/feed.xml` |
| **OWASP GenAI / LLM Top-10** | LLM Top-10 更新 | `https://genai.owasp.org/feed/` |
| **DeepMind / OpenAI / Google Security** | safety + 官方 security | `deepmind.google/blog/rss.xml` · `openai.com/news/rss.xml` · `security.googleblog.com/feeds/posts/default` |
| **OSV (AI/ML libs)** | transformers 等 lib 漏洞 | `POST api.osv.dev/v1/query {"package":{"name":"transformers","ecosystem":"PyPI"}}` |
| **MITRE ATLAS / NIST AI RMF** | AI 威脅矩陣 / 框架（scrape，無 RSS） | `atlas.mitre.org` · `mitre-atlas/atlas-data`(GH) |
| **Scrape-only（無 RSS）** | HiddenLayer · Lakera · **Anthropic news** — Webflow/Next.js 無 feed，靠 tldr;sec + Simon Willison surface | scrape `anthropic.com/news` 等 |
| MCP | `CSOAI-ORG/owasp-agentic-mcp`（prompt-injection/tool-poisoning detection）· `mitre-atlas/atlas-data` | gh |

**🔥「最近興乜」trending endpoints（tech + security，Round 14 verified）：**

| 平台 | Trending / Top-recent endpoint |
|------|-------------------------------|
| **Dev.to** | `dev.to/api/articles?tag=TAG&top=7`（last-7d top）；tag: security·ai·machinelearning·llm·aisafety·promptinjection·cybersecurity |
| **HN** | 最新 filter：`hn.algolia.com/api/v1/search_by_date?query=Q&tags=story`；頭版：`.../search?tags=front_page` |
| **Lobste.rs** | `lobste.rs/t/security.json` · `/t/ai.json` · `/t/ai,ml,security.json`（multi-tag） |
| **arXiv** | `/api/query?...&sortBy=submittedDate`（唔好用 rss/） |
| **GitHub Trending** | 冇官方 API → scrape `github.com/trending?since=daily` 或 `api.github.com/search/repositories?q=...+created:>DATE&sort=stars` |
| **Reddit** | `agent-chrome.py fetch`（r/netsec·r/MachineLearning·r/LocalLLaMA·r/ChatGPTJailbreak） |

**新 cluster（Round 14）— 💬 Social/Forum 擴充（睇人最近傾乜，全部 curl verified zero-key）：**

| Source | 睇咩 discussion | Endpoint |
|--------|----------------|----------|
| ⭐ **Arctic Shift** | **Pushshift 後繼** — zero-key Reddit post/comment full-text + full nested comment tree（含今日最新），係 browser 以外嘅第二路 | `arctic-shift.photon-reddit.com/api/posts/search?subreddit=X&sort=desc` · `/api/comments/search` · `/api/comments/tree?link_id=t3_ID&limit=9999` |
| ⭐ **Misskey (misskey.io)** | JP-heavy fediverse trending hashtag + local timeline | `POST misskey.io/api/hashtags/trend` · `/notes/local-timeline` |
| ⭐ **mbin (kbin.earth)** | Reddit-like fediverse link aggregator magazines | `kbin.earth/api/entries?sort=newest` |
| ⭐ **Lemmy 多 instance** | 分開嘅 firehose：`programming.dev`（dev）· `hexbear.net`· `sh.itjust.works`· `lemmy.ml` | `{instance}/api/v3/post/list?sort=Active` |
| ⭐ **Neynar (Farcaster)** | crypto-native trending casts（free key；docs key `NEYNAR_API_DOCS` 即試） | `api.neynar.com/v2/farcaster/feed/trending` header `x-api-key` |
| **Substack Notes** | Substack 作者 short-form（news/政治 commentary） | `substack.com/api/v1/reader/feed` |
| **daily.dev** | dev community feed（anon GraphQL） | `POST api.daily.dev/graphql`（anonymousFeed） |
| **PeerTube** | fediverse video + comment，trending | `{instance}/api/v1/videos?sort=-trending` |
| **Slashdot** | 經典 tech-news 討論（comment-heavy，RSS only） | `rss.slashdot.org/Slashdot/slashdotMain` |
| **StackExchange /sites** | 列晒 170+ 站 fan-out（ServerFault/SuperUser…） | `api.stackexchange.com/2.3/sites` |
| **Mastodon trends statuses/links** | post-level + news-link trends | `mastodon.social/api/v1/trends/statuses` · `/trends/links` |
| MCP（最大 chat 平台，無 public REST） | `chigwell/telegram-mcp`(1,150⭐) · `SaseQ/discord-mcp`(332⭐) · `AustinKelsay/nostr-mcp-server`(36⭐) | gh |
| ❌ skip | Squabbles（死/parked）· nostr.band（000）· Warpcast/Searchcaster/Disqus/Quora/Threads（locked/dead） | — |

**新 API（Round 9 新增 — Podcast & Media）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **PodcastIndex** | 4M+ podcasts 開放 index | `curl "https://api.podcastindex.org/api/1.0/search/byterm?q=..." -H "X-Auth-Key: {key}"` | 免費 key，零 limit |
| **Apple Podcasts (iTunes)** | Podcast search + metadata | `curl "https://itunes.apple.com/search?term=AI&media=podcast"` | 免費，零 key |
| **Listen Notes** | 186M+ episodes search | REST API | Freemium — free tier 有 limit |
| **Open Library** | 書籍 search + metadata | `curl "https://openlibrary.org/search.json?q=..."` | 免費，零 key |
| **Internet Archive** | 所有 media（text/audio/video/web） | `curl "https://archive.org/advancedsearch.php?q=...&output=json"` | 免費，零 key |

**新 API（Round 9 新增 — Currency & Geo）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **Frankfurter** | 160+ 央行匯率，歷史數據 | `curl "https://api.frankfurter.dev/v1/latest?from=USD"`（⚠️ 2026-05-31 fix：path 加咗 `/v1/`；舊 `/latest` 而家 404。`api.frankfurter.app` 301→同樣 `/v1`） | 免費，零 key，零 limit |
| **CoinGecko** | 17K+ crypto 價格/市值/volume | `curl "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"` | 免費零 key 5-15 req/min；免費 demo key 30 req/min |
| **Open-Meteo** | 天氣（1940 年至今）+ 氣候預測 | `curl "https://api.open-meteo.com/v1/forecast?latitude=43.65&longitude=-79.38&hourly=temperature_2m"` | 免費，零 key，10K req/day |
| **ip-api.com** | IP → 國家/城市/ISP | `curl "http://ip-api.com/json/8.8.8.8"` | 免費，零 key，45 req/min（HTTP only） |

**新 API（Round 10 新增 — Blockchain & On-chain Data）：**

> 所有鏈上活動都係 public。做 crypto/DeFi/NFT research、wallet & token analytics、smart-money / insider 追蹤、DEX flow、prediction market 用呢組。
> 核心 insight：高勝率 wallet ≠ 你跟單會賺。Latency（Polygon 4-14 秒）、thin market 滑點、exit-liquidity trap、insider 用 fresh wallet，全部會破壞 naive copy-trading。分 skill vs luck 要用 binomial p-value（p<0.001）+ 100+ trade 樣本 gate；捉 fresh-wallet insider 要用 funding-source clustering（唔係 track record）。

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **DeFiLlama** | TVL/yields/stablecoins/DEX volume/protocol revenue，全鏈 | `curl "https://api.llama.fi/protocols"`；`curl "https://yields.llama.fi/pools"` | 免費，零 key，零 limit |
| **DexScreener** | Live DEX token pair 價格/流動性/volume，全鏈（memecoin 必備） | `curl "https://api.dexscreener.com/latest/dex/search?q=SYMBOL"` | 免費，零 key，300 req/min |
| **GeckoTerminal** | DEX pool/OHLCV per chain | `curl "https://api.geckoterminal.com/api/v2/networks/solana/pools?sort=h24_volume_usd_desc"` | 免費，零 key，30 req/min |
| **Etherscan V2 (multichain)** | 一個 key 打 60+ EVM 鏈：txns/token transfer/balance/contract source | `curl "https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist&address=0x...&apikey=KEY"`（chainid: 1=ETH 137=Polygon 8453=Base 42161=Arb 56=BSC） | 免費 key，5 req/sec |
| **Solana RPC / Solscan** | Solana txns/SPL token flow | `curl https://api.mainnet-beta.solana.com -d '{"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress","params":["ADDR",{"limit":20}]}'` | 免費 public RPC（有 rate limit）；Solscan free tier |
| **mempool.space** | Bitcoin txns/mempool/fees | `curl "https://mempool.space/api/address/{addr}"` | 免費，零 key |
| **Dune Analytics API** | 跑 SQL over decoded chain tables，攞任何 public query 結果 | `curl -H "X-Dune-API-Key: KEY" "https://api.dune.com/api/v1/query/{id}/results"` | 免費 tier（有 credit），需 key |
| **The Graph** | GraphQL subgraph：protocol-specific entities（position/PnL/holder） | `POST "https://gateway.thegraph.com/api/{key}/subgraphs/id/{id}"` | 需 Graph API key（free tier） |
| **Bitquery** | GraphQL on-chain 含 DEX trades/transfers/balance，40+ 鏈 | GraphQL endpoint | 免費 tier，需 key |
| **Covalent/GoldRush · Moralis · Alchemy** | Unified multichain wallet/token/NFT API | REST/SDK | 免費 tier，需 key |
| **Polymarket Gamma** | Prediction market metadata：conditionId/clobTokenIds/outcomePrices/volume/resolution | `curl "https://gamma-api.polymarket.com/markets?closed=false&limit=10&order=volume&ascending=false"` | 免費，零 key |
| **Polymarket Data API** | ⭐ Per-wallet PnL 預先計好（smart-money 分析核心） | `curl "https://data-api.polymarket.com/positions?user=0xADDR&sortBy=CASHPNL&sortDirection=DESC"`（→ realizedPnl/avgPrice/cashPnl）；`/trades?limit=100`（proxyWallet/side/price/timestamp/txHash）；`/activity?user=`；`/value?user=` | 免費，零 key |
| **Polymarket Leaderboard** | Volume 排行 | `curl "https://lb-api.polymarket.com/volume?window=all&limit=20"` | 免費，零 key（PnL-ranked path 未公開） |
| **Nansen** | Rule-based + clustered「Smart Money」labels，30+ 鏈 | Web/API | 💰 $49/mo Pro（無 published accuracy，heuristic） |
| **Arkham** | ML entity attribution/deanonymization + bounty marketplace | Web/API | Freemium（attribution 係 inference 唔係 fact） |
| **Lookonchain** | Whale/smart-money 即時 alert（editorial） | Web/feed | 大致免費 |

**Blockchain 數據 — 開源 reference（睇 methodology）：**

| Repo | Stars | 學咩 |
|------|-------|------|
| `harish-garg/Awesome-Polymarket-Tools` | 108 | Polymarket 工具 aggregator |
| `Drakkar-Software/OctoBot-Prediction-Market` | 88 | 最可信 OSS Polymarket bot（copy-trade + arb） |
| `web3-data-research/smart-money-tracker` | 29 | Jupyter notebook，documented smart-money 策略（打新/生死追蹤），有中文 doc |
| `suislanchez/polymarket-insider-detector` | — | Binomial p-value 統計檢測 insider（p<0.001 flag）+ 0-10 suspicion score |
| `pselamy/polymarket-insider-tracker` | — | 「niche market + unusual sizing + fresh wallet」triad 偵測 |
| `demwick/polymarket-agent-mcp` | 8 | MCP 48 tools：discover_flow（consensus signal）、score_trader（5 維）、backtest |
| Dune `couldbebasic/top-traders` | — | De-facto memecoin wallet screen（win rate/ROI/realized PnL/sample gate） |

**MCP for Academic Search（Round 5 新增）：**

| MCP | 做咩用 | 點裝 |
|-----|--------|------|
| **paper-search-mcp** | 一個 MCP 搜 20+ 平台（arXiv、S2、OpenAlex、Crossref、CORE、dblp、DOAJ、Zenodo 等）919⭐ | ✅ `uvx paper-search-mcp` → `~/.claude/.mcp.json` |
| **Semantic Scholar MCP** | Full S2 API：citation network、recommendations、batch ops、20x concurrency | ✅ `uvx semantic-scholar-mcp` → `~/.claude/.mcp.json` |
| **arxiv-mcp-server** | arXiv semantic search + citation analysis + trend analysis + BibTeX export 2.4K⭐ | ✅ `uvx arxiv-mcp-server` → `~/.claude/.mcp.json` |
| **scholar-mcp** | ~97% peer-reviewed coverage，6 sources，**download + read paper PDF** | ✅ `uvx scholar-mcp` → `~/.claude/.mcp.json`（Round 8 新裝） |

**Academic Paper MCPs — Worth Installing（Round 8 新增）：**

| MCP | Stars | 做咩用 | 點裝 |
|-----|-------|--------|------|
| **openalex-mcp** | 15 | 250M papers via free OpenAlex API，MCP wrapper | `github.com/hbiaou/openalex-mcp` |
| **academia_mcp** | 78 | ArXiv + ACL Anthology + HF Datasets + Semantic Scholar | `github.com/IlyaGusev/academia_mcp` |
| **scholar-mcp** | — | ~97% coverage peer-reviewed literature，6 sources | `github.com/Liyux3/scholar-mcp` |
| **PaperMCP** | 3 | ArXiv/HF/Google Scholar/OpenReview/DBLP/PapersWithCode，32 unified tools | `github.com/ScienceAIHub/PaperMCP` |
| **research-paper-mcp** | — | Autonomous arXiv + S2 ingestion，memory storage，knowledge growth | `playbooks.com/mcp/marc-shade/research-paper-mcp` |

**Deep Research MCP Servers（Round 8 新增）：**

> 呢啲係將 deep research agent 能力加入 Claude Desktop / Claude Code 嘅 MCP servers。

| MCP | Stars | 做咩用 | 點裝 |
|-----|-------|--------|------|
| **deep-research-mcp** (teelaitila) | 317 | General deep research MCP，最多 stars | `github.com/teelaitila/deep-research-mcp` |
| **octagon-deep-research-mcp** | 86 | No rate limits，faster than ChatGPT Deep Research | `github.com/OctagonAI/octagon-deep-research-mcp` |
| **deep-research-mcp** (multi-provider) | 48 | 支援 OpenAI/Gemini/HuggingFace Deep Research | `github.com/pminervini/deep-research-mcp` |
| **openrouter-deep-research-mcp** | 45 | Multi-agent ensemble consensus，async agents，pglite DB | `github.com/wheattoast11/openrouter-deep-research-mcp` |
| **sample-deep-research-mcp** (OpenAI) | 67 | Official OpenAI reference implementation | `github.com/openai/sample-deep-research-mcp` |
| **deep-research-mcp-server** (Gemini) | 68 | Gemini as research AI agent | `github.com/ssdeanx/deep-research-mcp-server` |

**Autonomous Deep Research Agents（Round 8 新增）：**

> 唔係 MCP，係獨立嘅 research agent 系統。可以獨立跑或者做 reference architecture。

| Agent | Stars | 做咩用 | URL |
|-------|-------|--------|-----|
| **RAGFlow** | 76.5K | RAG engine + agent，document ingestion + vector indexing + tool-using agents | `github.com/infiniflow/ragflow` |
| **Khoj** | 33.7K | AI second brain，deep research + custom agents + scheduled automations | `github.com/khoj-ai/khoj` |
| **STORM (Stanford)** | 28K | Wikipedia-quality report generation，multi-perspective synthesis | `github.com/stanford-oval/storm` |
| **GPT Researcher** | 26.1K | OG deep research agent，20+ sources → cited reports | `github.com/assafelovic/gpt-researcher` |
| **SurfSense** | 13.6K | Open-source NotebookLM/Perplexity，connects Tavily/Slack/Notion/GitHub | `github.com/MODSetter/SurfSense` |
| **AI-Research-SKILLs** | 5.8K | Research skill library for any AI model (Orchestra Research) | `github.com/Orchestra-Research/AI-Research-SKILLs` |
| **node-DeepResearch (Jina)** | 5.1K | Iterative search+read+reason until answer，Node.js | `github.com/jina-ai/node-DeepResearch` |
| **local-deep-research** | 4.2K | ~95% SimpleQA，local+cloud LLMs，arXiv/PubMed/web，encrypted | `github.com/LearningCircuit/local-deep-research` |
| **EvoScientist** | 2.4K | Self-evolving AI scientists，autonomous scientific discovery | `github.com/EvoScientist/EvoScientist` |
| **company-research-agent** | 1.6K | Multi-agent company research，LangGraph + Tavily | `github.com/guy-hartstein/company-research-agent` |
| **AutoResearch SibylSystem** | 203 | Fully autonomous AI research with self-evolution，built on Claude Code | `github.com/Sibyl-Research-Team/sibyl-research-system` |
| **LangChain Open Deep Research** | — | LangChain reference implementation using LangGraph | `github.com/langchain-ai/open_deep_research` |
| **JigsawStack Deep Research** | 174 | Open-source deep research library with reasoning，TypeScript | `github.com/JigsawStack/deep-research` |

**Leaderboard 監控（Round 5 新增）：**

用 `changedetection.io`（✅ 已裝，`http://localhost:5000`）監控以下 leaderboard：

| Leaderboard | URL | 監控咩 |
|-------------|-----|--------|
| SWE-bench Verified | `swebench.com` | 排名表 |
| SWE-bench Pro | `labs.scale.com/leaderboard/swe_bench_pro_public` | 排名表 |
| LMSYS Arena | `lmsys.org` chatbot arena | ELO rankings |
| LiveBench | `livebench.ai` | Score tables |
| Aider | `aider.chat/docs/leaderboards/` | Code editing scores |
| Papers With Code | `paperswithcode.com/sota` | SOTA per task |

**Quality Scoring Formula（自動篩選 high-quality research）：**

```
score = (
  author_lab_bonus * 20        # Major lab (Google/Anthropic/OpenAI/Meta/DeepSeek) = +20
  + social_signal * 15         # HN frontpage / Reddit top = +15
  + conference_tier * 25       # NeurIPS/ICML/ICLR/ACL = +25
  + code_available * 10        # Has GitHub repo = +10
  + recency_bonus * 10         # Last 7 days = +10
  + citation_velocity * 20     # Top 10% velocity = +20 (only for papers >6 months)
)
# For papers <6 months: weight author_lab + social_signal more heavily
```

### Social & Trend Research（Round 7 新增）

| Tool | 做咩用 | 成本 | 點用 |
|------|--------|------|------|
| **last30days-skill** ⭐13,958 | 搜 Reddit/X/Bluesky/YouTube/TikTok/Instagram/HN/Polymarket 最近 30 日，multi-signal scoring + convergence detection | 免費（ScrapeCreators 100 free credits 覆蓋 Reddit+TikTok+Instagram） | `/last30days "topic"` — Claude Code Skill |
| **mcp-youtube-transcript** ⭐353 | YouTube 影片 transcript + metadata extraction | 免費，零 key | `uvx mcp-youtube-transcript` → `~/.claude/.mcp.json` |
| **open-webSearch** ⭐866 | 8 引擎搜索（Bing/Baidu/DDG/Brave/Exa/GitHub/Juejin/CSDN），零 API key | 免費，零 key | `npx open-websearch@latest` → `~/.claude/.mcp.json` |
| **paper-distill-mcp** ⭐53 | 11 源 parallel search（OpenAlex/S2/PubMed/arXiv/PwC/CrossRef/Europe PMC/bioRxiv/DBLP/CORE/Unpaywall），4 維 weighted ranking，Zotero 整合 | 免費，零 key（basic search） | `uvx paper-distill-mcp` → `~/.claude/.mcp.json` |

### Market Signals（Round 2 新增）

| Tool | 做咩用 | 成本 | MCP Server |
|------|--------|------|------------|
| **JobSpy** | Scrape Indeed/LinkedIn/Glassdoor job postings（hiring = market signal） | 免費 | `jobspy` |
| **Wayback Machine** | Save/retrieve archived web pages，track competitor changes | 免費 | `wayback` |

### Platform-Specific（免費，raw API / CLI）

| Tool | 做咩用 | 點用 |
|------|--------|------|
| **GitHub CLI** | 搵競品 repos、stars、activity | `gh search repos`, `gh api` |
| **npm CLI** | Package search + download counts | `npm search`, `npm view`, `curl api.npmjs.org/downloads/...` |
| **Reddit live + archive** | User pain points、sentiment | live: `agent-chrome.py fetch`; archive/search: Arctic Shift；raw reddit.com `.json` curl = 403 |
| **Dev.to API** | Ecosystem 文章 | `curl "https://dev.to/api/articles?tag=TAG&per_page=30"` |
| **Twitter API** | Mentions、sentiment | `$0.01/read`，API ready |
| **WebSearch / WebFetch** | General search + page fetch | Built-in |
| **HN Algolia API** | Full-text search 全部 HN history | `curl "http://hn.algolia.com/api/v1/search?query=..."` 免費 |
| **npm Downloads API** | Package download trends | `curl "https://api.npmjs.org/downloads/range/last-month/{pkg}"` 免費 |
| **Stack Overflow API** | Developer adoption trends | `curl "https://api.stackexchange.com/2.3/questions?tagged=...&site=stackoverflow"` 10K req/day free |
| **Wikipedia API** | Entity verification + pageviews | `curl "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=..."` 免費 |
| **Product Hunt API** | Competitor launches | GraphQL, free developer token |
| **Open Collective API** | OSS project funding data | GraphQL, 10 req/min free |

---

## MCP→curl 轉換（2026-06-11 gateway 瘦身：thin wrapper 唔使常駐）

> 背景：MCP server 上咗 1mcp gateway 共享（port 3050）之後，逐個 thin API wrapper「降級」做一次性 curl —— 零常駐 process、零 lifecycle、跨 agent（Claude Code / Codex）通用。下面每條 curl 都係**逐行讀完該 MCP server source 抽出嚟 + 實測過**先寫入。轉咗嘅 server 已從 gateway config 剔除。

### ✅ Agent Reach source harvest → direct HTTP/browser routes（2026-09-11）

Clone 固定喺 `~/MyGithub/Agent-Reach`；今次審到 commit
`da5044d26fc6adddb6554d5679c94ac22e76e428`。只抽 endpoint、fallback 同風險控制，
**冇安裝 Agent Reach、OpenCLI、mcporter 或任何 MCP**。

| Channel | 我哋直接用嘅 route | 2026-09-11 live result | 決定 |
|---|---|---|---|
| **Bilibili** | `GET api.bilibili.com/x/web-interface/search/all/v2?keyword=...&page=1`；UA，遇 412/code≠0 才暖首頁 cookie + Referer 重試 | HTTP 200、JSON `code=0`、20+ items | 收；搜尋毋須 `bili-cli`/OpenCLI/MCP |
| **V2EX** | hot、node topics、topic detail、replies、member 五條 public JSON API | 五條 HTTP 200；probe：hot 8、python node 10、topic 1、replies 173、member `Livid` | 收；discovery 用 `site:v2ex.com`，命中後 API 讀全文+replies |
| **LinkedIn public** | `r.jina.ai/https://www.linkedin.com/in/USERNAME/` | HTTP 200、86,843 bytes；有 public headline/activity，但 full profile 仍有 sign-in wall | 收做 public fallback；需要登入先用現有 Agent Chrome，唔裝 LinkedIn MCP |
| **小宇宙** | GET episode HTML → 抽 `media.xyzcdn.net/*.m4a|mp3` → 需要逐字內容先下載/轉錄 | episode HTTP 200（90,650 bytes），audio HEAD 200 | 收；係直抓鏈，唔係 public search API |
| **雪球** | quote、stock search、public timeline、hot-stock internal JSON endpoints | 暖首頁後四條仍 HTTP 400 / `400016`；Agent Chrome 未有雪球 session 亦 400 | conditional；只在已有登入 session 用 Agent Chrome，唔當 zero-key source |

```bash
# V2EX：search engine discover ID；API 讀完整內容、作者同 replies
curl -sS 'https://www.v2ex.com/api/topics/hot.json' -H 'User-Agent: research-engine/1.0'
curl -sS 'https://www.v2ex.com/api/topics/show.json?node_name=python&page=1' -H 'User-Agent: research-engine/1.0'
curl -sS 'https://www.v2ex.com/api/topics/show.json?id=TOPIC_ID' -H 'User-Agent: research-engine/1.0'
curl -sS 'https://www.v2ex.com/api/replies/show.json?topic_id=TOPIC_ID&page=1' -H 'User-Agent: research-engine/1.0'
curl -sS 'https://www.v2ex.com/api/members/show.json?username=USERNAME' -H 'User-Agent: research-engine/1.0'

# Bilibili public search
curl -sS 'https://api.bilibili.com/x/web-interface/search/all/v2?keyword=QUERY&page=1' \
  -H 'User-Agent: Mozilla/5.0' -H 'Referer: https://www.bilibili.com/'

# LinkedIn public surface（full/logged-in data 改用 agent-chrome.py）
curl -sS 'https://r.jina.ai/https://www.linkedin.com/in/USERNAME/'

# 小宇宙：先抽音頻 URL；唔需要內容就唔好下載成集 podcast
curl -sSL 'https://www.xiaoyuzhoufm.com/episode/EPISODE_ID' -o /tmp/xiaoyuzhou.html
perl -ne 'while (/(https:\/\/media\.xyzcdn\.net\/[^"]*\.(?:m4a|mp3))/gi) { print "$1\n" }' /tmp/xiaoyuzhou.html | head -1
```

**Agent Reach 本身冇可搬嘅 channel：** Facebook、Instagram 同 OpenCLI 版小紅書只係 browser bridge；
Reddit route 比我哋現有 `agent-chrome.py` + Arctic Shift 弱；Exa/LinkedIn rich mode 只係
叫 `mcporter` 起另一個 MCP；GitHub、YouTube、RSS、Jina 已經有等價或更完整 direct route。
呢啲全部冇新增可重用 API 邏輯，所以唔安裝、唔複製 wrapper。

### ✅ Facebook + Instagram + 小紅書 direct-first social layer（2026-09-11）

Agent Reach adapter 冇 API logic，唔代表三個平台冇 route。另行審過 Meta 官方文件、
ScrapeCreators OpenAPI、TikHub endpoint metadata，同 `xpzouying/xiaohongshu-mcp` source 後，
工具庫採用三層：**official special-purpose → direct provider API → local browser fallback**。

一次性工具：`~/MyGithub/ai-research-engine/social-research.py`。佢只在 command 執行期間存在，
唔開 server、唔裝 MCP、唔 export browser cookie。Credential 由環境或
`~/.config/research-engine/keys.env` 讀，唔會輸出 key。

| 平台/用途 | Route | 真正 coverage | 限制／決定 |
|---|---|---|---|
| **Meta Content Library API** | Meta first-party，secure environment | FB Pages/posts/public groups/events/profiles/comments/Marketplace；IG accounts/posts/comments；100+ fields、每 query 最多 100,000 results | 最完整；要 academic 或以 scientific/public-interest research 為 primary/core activity 嘅 nonprofit，獨立審批；只在 Meta SRE/SOMAR 分析。Meta SRE 無 access/computation fee。批准後先當 usable |
| **Facebook Pages Search** | `GET graph.facebook.com/pages/search` | Page name/metadata，批准後可再讀 public Page posts/comments | competitive-analysis live data 需要 Page Public Content Access、App Review、business verification；唔係全站 posts/people search |
| **Facebook Creator Discovery** | `GET /creator_marketplace/creators` | semantic search 已 opt-in creators、recent content/metrics | Brand/partnership ads 用；Business app + eligible brand + Page token + Advanced Access；Standard Access 只返 mock data |
| **Instagram Graph** | hashtag search / business discovery | professional accounts、公開 hashtagged media | hashtag 30 unique/rolling 7 days；要 professional IG account、permissions + App Review；唔係 consumer/general keyword search |
| **Meta Ad Library** | official UI/API | Meta ads、政治/issue ads、publisher platform 包 FB/IG | 專門做 ads；API 需 FB identity/location confirmation + developer app/token |
| **ScrapeCreators** | direct REST + `x-api-key` | IG search/profile/posts/reels/hashtags/comments；FB profile/posts/groups/comments/events/Ad Library | 100 initial free credits；大部分 1 credit。IG comment endpoint vendor 自報約 90% success；`include_replies=true` 固定 15 credits。**OpenAPI 無 XHS/RedNote path** |
| **TikHub XHS** | direct REST + Bearer token | XHS search、note detail、comments、user/product/topic | 2026-09-11 endpoint-info live probe：search/detail/comments US$0.01/request、10/s、free trial credit 不適用 |
| **Local XHS browser** | Agent Chrome :9223 + `window.__INITIAL_STATE__` | 第一頁 native search cards，帶 note ID、`xsec_token`、作者、互動、URL | 無 key、無 cookie export；first-page discovery only。登入/CAPTCHA 失敗要記 FAILED，唔係 EMPTY |

```bash
SR=~/MyGithub/ai-research-engine/social-research.py

# Instagram
python3 "$SR" scrapecreators /v1/instagram/search query='QUERY'
python3 "$SR" scrapecreators /v1/instagram/search/hashtag hashtag='TAG' date_posted=last-month
python3 "$SR" scrapecreators /v2/instagram/reels/search query='QUERY' page=1
python3 "$SR" scrapecreators /v2/instagram/post/comments url='POST_URL'

# Facebook
python3 "$SR" scrapecreators /v1/facebook/profile/posts url='PAGE_URL'
python3 "$SR" scrapecreators /v1/facebook/group/posts url='GROUP_URL' sort_by=CHRONOLOGICAL
python3 "$SR" scrapecreators /v1/facebook/post/comments url='POST_URL'
python3 "$SR" scrapecreators /v1/facebook/events/search query='QUERY'
python3 "$SR" scrapecreators /v1/facebook/adLibrary/search/ads query='QUERY' country=CA status=ALL trim=true

# 小紅書：auto = 有 TikHub key 用 REST；冇 key 用本機 Agent Chrome
python3 "$SR" xhs-search 'QUERY_ZH' --route auto --page 1 --sort general
python3 "$SR" tikhub /api/v1/xiaohongshu/web_v3/fetch_note_detail note_id='NOTE_ID' xsec_token='XSEC_TOKEN'
python3 "$SR" tikhub /api/v1/xiaohongshu/web_v3/fetch_note_comments note_id='NOTE_ID' cursor=''
```

**Source extraction：** clone `~/MyGithub/xiaohongshu-mcp` 固定審查 commit
`aad2a3d249a347859975ce3b76d3442c4a027780`。真正可重用嘅部分唔係 MCP protocol：
`xiaohongshu/search.go` 只係 navigate `search_result?keyword=...`、等
`window.__INITIAL_STATE__.search.feeds`，再抽 `noteCard`；`feed_detail.go` 同樣由
`window.__INITIAL_STATE__.note.noteDetailMap` 抽 detail/comments。呢個 search 核心已縮成
`social-research.py` 一個 command；冇搬 Rod browser、MCP server、login service、posting/like/favourite tools。

**每次跑法：** web search 用 `site:facebook.com` / `site:instagram.com/p|reel` /
`site:xiaohongshu.com/explore` 做 recall；同時跑 native/structured route；命中後展開 comments。
三個 pass 分開寫 ledger，保留 query、language variant、filter、page/cursor、timestamp、count、URL。
Search snippet 只係 lead，未開到原帖就唔好當已驗證正文。

Primary/vendor docs：

- Meta Content Library：`https://transparency.meta.com/researchtools/meta-content-library/`
- Meta Pages search：`https://developers.facebook.com/documentation/pages-api/search-pages`
- Meta Instagram hashtag：`https://developers.facebook.com/docs/instagram-api/guides/hashtag-search/`
- Meta Facebook Creator Discovery：`https://developers.facebook.com/documentation/fb-creator-discovery`
- ScrapeCreators OpenAPI：`https://docs.scrapecreators.com/openapi.json`
- TikHub XHS search：`https://docs.tikhub.io/420136398e0`
- 小紅書官方 Open Platform：`https://openaccount.xiaohongshu.com/docs/api-reference`

### ✅ mcp-hn → HN Algolia API（source: erithwik/mcp-hn，100% passthrough，零附加邏輯）

| 原 MCP tool | curl 等價 |
|---|---|
| `get_stories(top)` | `curl "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=10"` |
| `get_stories(new)` | `curl "https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=10"` |
| `get_stories(ask_hn/show_hn)` | `curl "https://hn.algolia.com/api/v1/search?tags=ask_hn&hitsPerPage=10"`（或 `show_hn`） |
| `search_stories(q)` | `curl "https://hn.algolia.com/api/v1/search?query=Q&tags=story&hitsPerPage=10"`（relevance）；`search_by_date` 版＝按時間 |
| `get_story_info(id)` | `curl "https://hn.algolia.com/api/v1/items/{id}"` — 連 nested comments 成棵樹返晒 |
| `get_user_info(name)` | `curl "https://hn.algolia.com/api/v1/users/{name}"` + `search?tags=author_{name},story` |

實測 quirk：`items/{id}` 食 story id **同** comment id 都得（comment 會有 `parent_id`/`story_id` 指返 story）。

### ✅ wayback → archive.org APIs（source: Mearman/mcp-wayback-machine，100% passthrough）

| 原 MCP tool | curl 等價 |
|---|---|
| `check_archive_status` | `curl "https://web.archive.org/__wb/sparkline?url=URL&collection=web&output=json"`（逐年 capture 統計）+ `curl "https://archive.org/wayback/available?url=URL"` |
| `search_archives` | `curl "https://web.archive.org/cdx/search/cdx?url=URL&output=json&limit=10"`，可加 `&from=YYYYMMDD&to=&matchType=domain&collapse=timestamp:8&filter=statuscode:200` |
| `retrieve` | available API 搵最近 snapshot → `https://web.archive.org/web/{ts}/{url}`；raw content 加 `id_` modifier：`/web/{ts}id_/{url}` |
| `screenshots` | CDX 搵 capture → `https://web.archive.org/web/{ts}im_/{url}` |
| `save`（存檔） | `curl -X POST "https://web.archive.org/save" -d "url=URL"` |

實測 quirk：**`available` API 一定要俾完整 URL**（`https://www.x.com/`）— bare domain（`anthropic.com`）會返空 `archived_snapshots`；CDX 就 bare domain 都食。

### 💀 newsmcp → 死咗，冇得轉（2026-06-11 實測）

newsmcp.io 個服務**永久關閉**（全部 endpoint 返 `{"detail": "NewsMCP has been shut down..."}`，維護者話成本問題）。MCP 同 curl 都救唔返。新聞需求改用：GDELT（零 key）、rss-reader curl（下面）、google-news via Serper。

### ✅ rss-reader → curl + r.jina.ai（source: rss-reader-mcp，PARTIAL）

| 原 MCP tool | 等價 |
|---|---|
| `fetch_feed_entries` | `curl -s "FEED_URL" -H "Accept: application/xml"` — 原始 RSS/Atom XML，LLM 直接讀得明（原 server 只係用 rss-parser 轉 JSON） |
| `fetch_article_content` | **唔係純 passthrough**（JSDOM+Turndown+readability heuristic）。替代：`curl -s "https://r.jina.ai/ARTICLE_URL"`（免費 readability API，直出 markdown）或 Firecrawl scrape（已有） |

### ✅ superprecio → superprecio.ar API（零 auth，已實測，15 個 tool ＝ 5 條 endpoint）

```bash
# 搜產品（compare_prices = 同一 endpoint order=OrderByPriceASC；best_deals = OrderByTopSaleDESC）
curl -s -X POST 'https://superprecio.ar/api/products' -H 'Content-Type: application/json' \
  -d '{"search":"leche","maxResults":9,"order":"OrderByPriceASC"}'
# EAN barcode 搜索
curl -s -X POST 'https://superprecio.ar/api/productsByCode' -H 'Content-Type: application/json' -d '{"search":"7794903232417"}'
# 附近超市
curl -s 'https://superprecio.ar/api/locations/nearby?lat=-34.6037&lng=-58.3816&radius=5'
```
原 server 嘅 compare/deals「邏輯」只係 sort + 百分比算術，LLM 自己做得。

### ⚠️ twitter → api.twitterapi.io（CLEAN passthrough，但**從來冇 work 過**）

2026-06-11 發現：`twitterapi-mcp` 讀 `TWITTERAPI_API_KEY`（twitterapi.io 第三方服務嘅 key），但 config 一直俾緊 `TWITTER_API_KEY`（官方 OAuth1 key）— **env var 名不匹配，呢個 MCP 由裝機嗰日起就係壞嘅**。實測現有 key 對 twitterapi.io 係 invalid。

要救返：去 twitterapi.io 註冊攞 key，然後直接 curl（唔使 MCP）：
```bash
curl -s 'https://api.twitterapi.io/twitter/tweet/advanced_search?query=Q&count=10&result_type=recent' -H "x-api-key: $TWITTERAPI_API_KEY"
curl -s 'https://api.twitterapi.io/twitter/user/last_tweets?userName=anthropic&count=10' -H "x-api-key: $TWITTERAPI_API_KEY"
curl -s 'https://api.twitterapi.io/twitter/user/info?userName=NAME' -H "x-api-key: $TWITTERAPI_API_KEY"
# 仲有 /tweets?tweet_id= /tweet/replies?id= /user/followers /user/followings /user/search
# 寫操作：POST /user_login_v2 {userName,password} → cookie → POST /create_tweet_v2 {text,reply_to?}
```
Twitter 搜索喺 key 未搞掂前用 Bluesky/Mastodon/HN 替代。

### ✅ devto → dev.to REST API（source: @furkankoykiran/devto-mcp，16 tool 全部 1:1，已實測）

```bash
source ~/.config/research-engine/keys.env   # $DEVTO_API_KEY
H=(-H "api-key: $DEVTO_API_KEY" -H "accept: application/vnd.forem.api-v1+json")
curl -s "https://dev.to/api/users/me" "${H[@]}"                        # 自己 profile
curl -s "https://dev.to/api/articles/me/all?per_page=30" "${H[@]}"     # 自己文章連 drafts
curl -s "https://dev.to/api/articles?tag=ai&per_page=30" "${H[@]}"     # 公開文章
curl -s -X POST "https://dev.to/api/articles" -H "api-key: $DEVTO_API_KEY" -H "content-type: application/json" \
  -d '{"article":{"title":"T","body_markdown":"...","published":false,"tags":["ai"]}}'   # 出文
# PUT /articles/{id} 更新；/comments?a_id=；/tags；/followers/users；/readinglist；/organizations/{name}
```
⚠️ 經 curl 出文嘅 sanitize check 已補：settings.json PreToolUse Bash hook，`if: Bash(*dev.to/api/articles*)`。

### 💀 hashnode → 雙重死亡，直接剷（2026-06-11 實測）

①env var 名錯（config 俾 `HASHNODE_API_TOKEN`，code 讀 `HASHNODE_PERSONAL_ACCESS_TOKEN`）— 由裝機起 auth 從來係空；②Hashnode 已 retire 免費 GraphQL API（gql.hashnode.com 301 去公告頁，而家要 Pro plan）。唔修，唔替代。

### ✅ kaggle → 官方 kaggle CLI（kaggle-mcp 全包得一個 tool）

```bash
kaggle competitions download -c <id> -p <dir> && unzip <dir>/*.zip -d <dir>   # = 成個 kaggle-mcp
kaggle competitions list -s <query> / kaggle datasets list -s <query>          # CLI 仲多嘢過 MCP
```
CLI 喺 `~/.local/bin/kaggle`，creds `~/.kaggle/kaggle.json`，已實測。

### ✅ jobspy → 一次性 uv run（成條 Node→Docker→Python 鏈 = 一個 function）

```bash
uv run --with 'python-jobspy>=1.1.80' python3 -c "
from jobspy import scrape_jobs
jobs = scrape_jobs(site_name=['indeed'], search_term='software engineer', location='Vancouver, BC',
                   results_wanted=5, hours_old=72, verbose=0, description_format='markdown', country_indeed='Canada')
print(jobs.to_json(orient='records', indent=2))"
```
已實測（攞到真 Indeed listings）。site_name 可加 'linkedin','glassdoor','zip_recruiter'。

### ✅ mcp-image → Gemini API curl（Claude 自己做 prompt enhancement）

原 server 嘅「增值」= 先叫 gemini-2.5-flash 執靚 prompt — 但 Claude 喺 session 入面自己就係 LLM，寫 prompt 直接寫到位。淨返一條 curl：
```bash
source ~/.config/research-engine/keys.env   # $GEMINI_API_KEY
curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key=$GEMINI_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"DETAILED Subject-Context-Style PROMPT"}]}],"generationConfig":{"responseModalities":["IMAGE"]}}' \
| python3 -c "import json,sys,base64; d=json.load(sys.stdin); [open(f'/tmp/img.png','wb').write(base64.b64decode(p['inlineData']['data'])) for p in d['candidates'][0]['content']['parts'] if 'inlineData' in p]; print('/tmp/img.png')"
# 高質版：model 換 gemini-3-pro-image-preview；圖生圖：parts 加 {"inlineData":{"mimeType":"image/png","data":"<base64>"}}
```

### ✅ context7 + firecrawl → 官方 remote MCP（零本地 process，已實測）

- **context7**：`claude mcp add --transport http context7 https://mcp.context7.com/mcp`（唔使 key；free key 喺 context7.com/dashboard 加額度）。REST 版：`curl "https://context7.com/api/v2/libs/search?query=Q"` + `curl "https://context7.com/api/v2/context?libraryId=/org/repo&query=Q&type=txt&tokens=500"`
- **firecrawl**：hosted MCP `https://mcp.firecrawl.dev/{API_KEY}/v2/mcp` — **比本地版多 12 個 tool**（19 vs 7：extract、agent、monitors…）。REST 版：`curl -X POST https://api.firecrawl.dev/v2/scrape -H "Authorization: Bearer $FIRECRAWL_API_KEY" -d '{"url":"...","formats":["markdown"]}'`，仲有 /v2/search /v2/crawl /v2/map

> **轉換進度（2026-06-11 完成）**：第一批 mcp-hn ✅、wayback ✅、superprecio ✅、rss-reader ✅、newsmcp 💀、twitter ⚠️ 等 key；第二批 devto ✅、kaggle ✅ CLI、jobspy ✅ one-shot、mcp-image ✅ curl、hashnode 💀、context7/firecrawl ✅ 轉官方 remote MCP。**1mcp gateway 最終剩 1 個房客：google-workspace**（唯一有真 OAuth 邏輯）。Keys 集中喺 `~/.config/research-engine/keys.env`。

---

## 應該安裝（🔥 Round 1-5 發現，免費，高價值）

> 呢啲係 tool sharpening 搵到嘅新工具。按優先度裝。

### 🔥🔥 Top Priority — Round 5 Research Engine Upgrade

| Tool | 做咩用 | 成本 | 點裝 | 點解要裝 |
|------|--------|------|------|---------|
| ~~**paper-search-mcp**~~ | ✅ 已裝 → `~/.claude/.mcp.json` | — | — | — |
| ~~**changedetection.io**~~ | ✅ 已裝 → Docker `http://localhost:5000`，data: `~/.changedetection` | — | — | — |
| ~~**Semantic Scholar MCP**~~ | ✅ 已裝 → `~/.claude/.mcp.json` | — | — | — |
| ~~**arxiv-mcp-server**~~ | ✅ 已裝 → `~/.claude/.mcp.json` | — | — | — |
| ~~**ai-rss-feeds**~~ | ✅ Feed URLs 已搵到，直接 curl / r.jina.ai，唔使 MCP 常駐 | — | — | — |
| ~~**Paper Agent**~~ | ❌ 唔用（1⭐，太新）。改用 **paper_claw**（28⭐，GH Actions + email） | — | `github.com/PigeonDan1/paper_claw` | — |

### 🔥 Must Install（Round 1 發現）

| Tool | 做咩用 | 成本 | 點裝 | 點解要裝 |
|------|--------|------|------|---------|
| **idea-reality-mcp** | Scan GitHub + HN + npm + PyPI + PH 搵現有競品，出 reality score 0-100 | 免費 | `github.com/mnemox-ai/idea-reality-mcp` | **專為 competitive analysis 設計** |
| ~~**reddit-research-mcp**~~ | 💀 2026-08-11 sanity check：唔好裝/叫 agent 用。用 `agent-chrome.py` + Arctic Shift | — | — | — |
| **free-web-search-ultimate** | 10+ engines（DuckDuckGo、Bing、Google、Brave、YouTube、Reddit、arXiv），零 API key | 免費 | `github.com/wd041216-bit/free-web-search-ultimate` | **永遠唔會用完 quota** |
| ~~**newsmcp**~~ | 💀 2026-06 shutdown。用 GDELT + RSS curl + Serper/Google News | — | — | — |
| **mcp-hn** | Search HN + top stories + user profiles | 免費 | `github.com/erithwik/mcp-hn` 或 `github.com/paabloLC/mcp-hacker-news` | **HN 係 tech trend 嘅 leading indicator** |

### 🟡 Should Install（免費或低成本 + 中-高 relevance）

| Tool | 做咩用 | 成本 | 點裝 |
|------|--------|------|------|
| **Xpoz MCP** ⭐6 | Search Twitter/Instagram/Reddit/TikTok，1.5B+ posts indexed，CSV export | Free tier（Google OAuth） | Remote MCP：`"url": "https://mcp.xpoz.ai/mcp"` |
| **altmbr/claude-research-skill** ⭐6 | Multi-agent research orchestrator，parallel workstreams + synthesis | 免費 | `git clone` → `~/.claude/commands/research.md` |
| **mcp-wikipedia** ⭐10 | Wikipedia page access MCP | 免費 | `github.com/algonacci/mcp-wikipedia` |
| **ScienceAIHub/PaperMCP** ⭐2 | All-in-one academic：ArXiv/HuggingFace/Google Scholar/OpenReview/DBLP/PapersWithCode，32 tools | 免費 | `github.com/ScienceAIHub/PaperMCP` |
| **Apify Latest News MCP** | 14 tools，27 free APIs（Reuters/AP/BBC/CNN/GDELT/Reddit/HN/Wikipedia trends） | Apify $5 free/mo | `apify.com/mrbridge/latest-news-mcp-server` |
| **Brave Search MCP** | Independent search index（唔係 Google） | $5 free/mo | `npx @anthropic/mcp-server-brave-search` + `BRAVE_API_KEY` |
| **SerpApi MCP** | Multi-engine SERP（Google + Bing + Yahoo + YouTube） | 100 free/mo | `github.com/serpapi/serpapi-mcp` + `SERPAPI_KEY` |
| **Apify MCP** | 12,000+ scraping actors（Reddit、Twitter、PH、LinkedIn...） | $5 free/mo | `npx @apify/mcp-server` + `APIFY_TOKEN` |
| **macrocosmos-mcp** | Multi-platform social data（X + Reddit + YouTube）with date filtering | Free tier | `github.com/macrocosm-os/macrocosmos-mcp` |
| **open-sales-stack** | Competitive intelligence（tech stack、hiring signals、reviews、ads） | 免費 open source | `github.com/ekas-io/open-sales-stack` |
| **google-researcher-mcp** | Google Search + news + arXiv + patents + YouTube transcripts | Depends on Google API | `github.com/zoharbabin/google-researcher-mcp` |
| **Spectrawl** | 8 engines + stealth browse + 24 platforms | 5,000 free/mo | `github.com/FayAndXan/spectrawl` |
| **GPT Researcher MCP** | Autonomous deep research reports with citations | 免費（bring own LLM key） | `docs.gptr.dev/docs/gpt-researcher/mcp-server/` |
| **RSS Aggregator MCP** | Monitor competitor blogs + news feeds | 免費 | `github.com/imprvhub/mcp-rss-aggregator` |
| **Site Spy / changedetection.io** | Track competitor website changes | 免費 self-hosted | `github.com/dgtlmoon/changedetection.io` |
| **SEO MCP (Ahrefs-based)** | Free competitor backlink + keyword analysis | 免費 | `github.com/cnych/seo-mcp` |
| **AppInsight MCP** | App Store + Play Store intelligence | 免費 | `github.com/JiantaoFu/AppInsightMCP` |
| **Jina AI MCP** | Content extraction + screenshot + arXiv search | 1M tokens/day free | Remote MCP |

### 🔥🔥 Top Priority — Round 9 新增

| Tool | 做咩用 | 成本 | 點裝 |
|------|--------|------|------|
| **trendsmcp** | Google/YouTube/TikTok/Reddit/Amazon/npm/GitHub/Steam/Spotify 趨勢 | 100 free req/mo | `npx -y trendsmcp` + `TRENDS_API_KEY` |
| **social-trends-mcp** | Reddit + HN trending，零 auth | 免費，零 key | `npx aiagentkarl-social-trends-mcp-server` |
| **mcp-reddit** (adhikasp) 380⭐ | Reddit content fetch + analysis，zero-config | 免費 | `github.com/adhikasp/mcp-reddit` |
| **SEC EDGAR MCP** 242⭐ | US 公司 filings（10-K/Q/8-K/Form D） | 免費 | `pip install sec-edgar-mcp` |
| **gs-skills** 60⭐ | Google Scholar via Chrome DevTools | 免費 | `github.com/cookjohn/gs-skills` |
| **mcp-simple-pubmed** 105⭐ | PubMed 醫學/生命科學論文 | 免費 | `github.com/andybrandt/mcp-simple-pubmed` |
| **PapersWithCode MCP** 20⭐ | ML 論文 + code implementations | 免費 | `github.com/hbg/mcp-paperswithcode` |
| **openalex-research-mcp** 18⭐ | OpenAlex 240M+ papers，citation analysis | 免費 | `npm install` `github.com/oksure/openalex-research-mcp` |
| **mcp-patents** (pipeworx) | US patent search via PatentsView | 免費 | `github.com/pipeworx-io/mcp-patents` |
| **patent-mcp** (riemannzeta) 50⭐ | USPTO 52 tools：search/PTAB/訴訟 | 免費 | `github.com/riemannzeta/patent_mcp_server` |
| **us-gov-open-data-mcp** 93⭐ | 40+ US 政府 API，250+ tools | 免費 | `github.com/lzinga/us-gov-open-data-mcp` |
| **mcp-wikidata** | Wikidata knowledge graph queries | 免費 | `github.com/zzaebok/mcp-wikidata` |
| **whois-mcp** 52⭐ | WHOIS domain lookup | 免費 | `github.com/bharathvaj-ganesan/whois-mcp` |
| **mcp-domain-availability** 41⭐ | 50+ TLD availability check | 免費 | `uvx mcp-domain-availability` |
| **Jina AI MCP** 608⭐ | URL → clean markdown + arXiv search | 10M token free | Remote MCP |

### 🔥 High Priority — Round 9 新增

| Tool | 做咩用 | 成本 | 點裝 |
|------|--------|------|------|
| **BiomCP** | PubMed + ClinicalTrials.gov + MyVariant.info | 免費 | `github.com/genomoncology/biomcp` |
| **bsky-mcp-server** 42⭐ | Bluesky search + posts + profiles | 免費 | `npm` `github.com/brianellin/bsky-mcp-server` |
| **Slack MCP** 1,505⭐ | Slack workspace data | 免費（需 Slack token） | `github.com/korotovsky/slack-mcp-server` |
| **Discord MCP** 236⭐ | Discord 65 tools | 免費（需 bot token） | `github.com/SaseQ/discord-mcp` |
| **Telegram MCP** 872⭐ | Telegram MTProto 完整接入 | 免費（需電話號碼） | `github.com/chigwell/telegram-mcp` |
| **ActivityPub MCP** 16⭐ | Mastodon/Fediverse WebFinger + timelines | 免費 | `github.com/cameronrye/activitypub-mcp` |
| **NYTimes MCP** 59⭐ | 紐約時報文章 search | 免費（NYT API key） | `github.com/angheljf/nyt` |
| **mcp-open-library** 66⭐ | Open Library book search | 免費 | `github.com/8enSmith/mcp-open-library` |
| **mcp-internet-archive** | Internet Archive（texts/audio/video） | 免費 | `github.com/lawriec/mcp-internet-archive` |
| **mcp-video** | yt-dlp wrapper — Vimeo/Dailymotion/TikTok/Twitter/YouTube 轉錄 | 免費 | `github.com/felores/mcp-video` |
| **mcp-google-analytics** | GA4 data to agents | 免費（GA4 API） | `github.com/surendranb/google-analytics-mcp` |
| **gsc-mcp** | Google Search Console 13 tools | 免費（GSC） | `github.com/mikusnuz/gsc-mcp` |
| **anaisbetts/mcp-youtube** | YouTube metadata + search（beyond transcripts） | 免費（YT Data API） | `github.com/anaisbetts/mcp-youtube` |
| **RivalSearchMCP** | Competitive intelligence，零 API key | 免費 | `github.com/DamionR/RivalSearchMCP` |
| **Aperture** | AI brand visibility（ChatGPT/Perplexity/Claude mentions） | 免費（self-host） | `github.com/anyin-ai/aperture` |
| **google-trends-mcp** | Google Trends wrapper | 免費（self-host） | `github.com/andrewlwn77/google-trends-mcp` |
| **TrendRadar** | 多平台熱點 + 情感分析 + MCP + RSS | 免費（Docker self-host） | `github.com/sansan0/TrendRadar` |
| **Serper MCP** | Google SERP | 2,500 free/mo | `github.com/NightTrek/Serper-search-mcp` |
| **DataForSEO MCP** 72⭐ | Multi-engine SERP | ~$0.0006/req | `github.com/Skobyn/dataforseo-mcp-server` |
| **mcp-seo-tools** | On-page SEO audit（meta/OG/headings/broken links） | 免費，零 key | `npx @rog0x/mcp-seo-tools` |
| **@perplexity-ai/mcp-server** | Perplexity 官方 real-time search + citations | 需 Perplexity API key（有 free tier） | `npm install @perplexity-ai/mcp-server` |
| **gptr-mcp** | GPT Researcher autonomous deep research | BYOK（OpenAI + Tavily key） | `github.com/assafelovic/gptr-mcp` |

### 🟡 Should Install — Round 9 新增

| Tool | 做咩用 | 成本 | 點裝 |
|------|--------|------|------|
| **SociaVault** | 單一 API 接 25+ 平台 influencer data | 50 free credits | REST API `sociavault.com` |
| **mcp-newsapi** | NewsAPI 80K+ sources | Freemium | `github.com/matteoantoci/mcp-newsapi` |
| **Naver Search MCP** | 韓國 Naver 搜尋 + DataLab | 免費 API | `github.com/isnow890/naver-search-mcp` |
| **WET MCP** | 內建 SearXNG，零 API key | 免費 | `github.com/n24q02m/wet-mcp` |
| **kreuzberg** | 91+ 格式 document extraction（PDF/Office/images） | 免費 | `github.com/kreuzberg-dev/kreuzberg` |
| **airweave-mcp-search** | Search connected data（Slack/GitHub/Jira/Notion） | 免費 self-host | `npm install airweave-mcp-search` |
| **DetectZeStack** | Website tech stack detection | 100 free req/mo | REST API `detectzestack.com` |
| **TheirStack** | Tech detection from job postings | 200 credits/mo | REST API `theirstack.com` |
| **Obsei** 1,400⭐ | Social listening + brand monitoring + sentiment | 免費（開源 Python） | `pip install obsei` |
| **respectaso** 217⭐ | Free OSS ASO keyword research | 免費（Docker self-host） | `github.com/respectlytics/respectaso` |
| **appgoblin** | Free app store analytics（Android + iOS） | 免費 | `github.com/ddxv/appgoblin` |
| **Asodesk API** | 18M apps，34M keywords，100+ countries | 免費 token | `api.asodesk.com/free-tools` |
| **mcp-pagespeed** | Google PageSpeed Insights MCP | 免費（25K req/day） | `github.com/sixees/mcp-pagespeed` |
| **mcp-netutils** 9⭐ | DNS + WHOIS + TLS cert + HTTP monitoring | 免費 | `github.com/patrickdappollonio/mcp-netutils` |
| **Cognee MCP** | Graph-RAG：knowledge graph from docs | 免費（self-host） | Smithery |
| **FMP MCP** | Financial Modeling Prep | 免費 key，250 req/day | `github.com/imbenrabi/Financial-Modeling-Prep-MCP-Server` |

### 🟢 Nice to Have（specialized）

| Tool | 做咩用 | 成本 |
|------|--------|------|
| **Crunchbase MCP** | Competitor funding + acquisitions | Limited free |
| **competlab-mcp** | Monitor how AI ranks your brand | Freemium |
| **npm-trends MCP** | Track package download trends | Requires trendsmcp.ai key |
| **SIGMAEO MCP** | 52 SEO tools + AI citation tracking | Check provider |
| **Agent Interviews MCP** | AI-powered user research at scale | Freemium |
| **Crayon MCP** | Competitive intelligence（first CI MCP，Sep 2025） | 付費 |
| **Klue MCP** | Competitive source of truth | 付費 |
| **Signal Labs MCP** | Real-time startup/market signals | 付費 |
| **SimilarWeb MCP** | Traffic + keyword + app performance | 付費（$199+/mo） |
| **Octagon MCP** | Investment research — private + public markets | Free tier + usage-based |
| **Apollo.io MCP** | 210M+ contacts B2B intelligence | Free: 10K email credits/mo |
| **Audiense Insights** | Audience demographic + influencer analysis | 付費 |
| **AICW (AI Chat Watch)** | Track brand mentions in ChatGPT | 免費 OSS |
| **Citatra** | Competitor AI search visibility + backlinks | 免費 OSS |

---

## Research Workflow v2（用晒所有工具）

### Time Budget（from autoresearch pattern）

> 每個 phase 有 fixed time cap。到時間就 stop + synthesize，唔好無限 scope creep。
> 好過嘅 research 有 deadline。

| Phase | Time Cap | 點知做完 |
|-------|---------|---------|
| Phase 0: Reality Check | 2 min | Reality score 出咗 |
| Phase 1: Broad Scan | 15-30 min | 6 agents 全部返咗 |
| Phase 2: Paid Deep Dive | 10-15 min | 只做 user approved 嘅 queries |
| Phase 3: Synthesis | 10 min | Report 寫好 |
| **Total** | **~45-60 min max** | |

### Phase 0: Reality Check（1 agent，2 min）— FREE
```
Agent 0: Does this already exist?
  → idea-reality-mcp（scan GitHub + HN + npm + PyPI + PH）
  → Reality score < 30 = green light
  → Reality score > 70 = pivot or differentiate
```

### Phase 1: Broad Scan（6 parallel agents）— ALL FREE TOOLS FIRST

> ⚠️ 原則：Free tools 先行。跑完 Phase 1 之後，問用家：「免費搵到 X 個結果，需唔需要用 paid tools 再深入？」
> 用家話「夠」→ 直接去 Phase 3 synthesis。用家話「再深入」→ 先跑 Phase 2。
> **永遠唔好自動跑 Phase 2。一定要問。**

```
Agent A: Direct Competitors — FREE
  → open-websearch（8 engines，零 key）  # ⚠️ free-web-search 死咗，用呢個
  → gh search repos（GitHub landscape）
  → npm search + npm Downloads API（package ecosystem）
  → WebSearch（built-in）

Agent B: User Pain Points — FREE
  → Reddit live: agent-chrome.py fetch（search + full comment tree）
  → Reddit archive/cross-check: Arctic Shift posts/search + comments/tree
  → Stack Overflow API（tagged questions volume）
  → open-websearch（"[category] problems frustrations reddit"）

Agent C: Market Trends + News — FREE
  → GDELT curl（real-time global news；注意 shared-IP 429，要 spacing）
  → google-trends（Google News RSS + Trends data）
  → Dev.to API（trending articles）
  → mcp-hn / HN Algolia API（search HN history）
  → RSS curl / r.jina.ai（competitor blog feeds + article extraction）

Agent D: Technical Feasibility — FREE
  → Context7（library docs）
  → Exa Code Context（code examples、changelog、SDK docs — ⚠️ 比 Claude WebFetch 準確得多）
  → GitHub CLI（reference repos, architecture）
  → WebFetch（competitor README raw content — ⚠️ 唔好用嚟抓 code docs，12% empty rate）

Agent E: Distribution Landscape — FREE
  → npm Downloads API（competitor adoption velocity）
  → wayback（competitor website evolution）
  → Wikipedia API（entity verification）
  → Product Hunt API（launches）

Agent F: Market Signals — FREE
  → jobspy（hiring trends = market demand signal）
  → open-websearch（"[category] funding" "series A"）  # free-web-search 死咗
  → Open Collective API（OSS project funding）
```

### Phase 2: Paid Bonus Deep Dive（只喺 Phase 1 唔夠先用）

> 💰 呢度先用 paid credits。每個 session 控制喺 ~$0.50-1.00 USD。

```
If Phase 1 搵到有趣嘅 competitors 但要深入了解：
  → Tavily Research（deep, multi-source synthesis）
  → Exa Search（semantic: 搵 Phase 1 miss 咗嘅 similar tools）
  → Firecrawl Scrape（抓 competitor docs/pricing — single page only）

If Phase 1 搵到 pain points 但要更多 evidence：
  → Tavily Search（targeted deep search）
  → Exa Search（semantic: blog posts discussing the pain）

If 需要 social sentiment：
  → Twitter API（$0.005/read — 只讀最重要嘅 threads）

If 需要 crawl 成個 competitor site（罕見）：
  → Firecrawl Crawl（用 credits 最多嘅操作，慳住用）
```

### Phase 3: Synthesis — FREE
```
Compile all findings into structured report:
  → Competitive landscape table（with real-time data）
  → User pain points ranked by frequency + platform
  → Market gaps ranked by opportunity
  → Technical feasibility assessment
  → Distribution strategy recommendation
  → Go/No-go recommendation with reasoning
  → Cost spent this session: $X.XX
```

### Official dynamic-PDF fallback

政府網站有時用帶 `forcedownload` 或臨時資產 ID 嘅官方 PDF；搜尋／fetch 工具可能已經成功建立索引，
之後 `open` 同一 URL 卻回 502。呢個係 retrieval failure，唔係文件不存在或內容為空。處理次序：

1. 由官方 HTML 頁面 click 出資產 URL，保留 originating page 同 final asset URL。
2. `curl -L --fail --show-error` 直接下載官方 PDF；驗證 `%PDF`、頁數、byte count 同 SHA-256。
3. 用 `pdftotext -layout` 抽完整文字，再按頁碼／section 核對引用內容；需要視覺證據先 render 指定頁。
4. ledger 分開記錄：web fetch `FAILED 502`，direct official download `GOT DATA`；唔准將前者當 EMPTY。

---

## 💀 死咗 MCP — 待 fix queue

> 呢度啲 MCP 喺 config 入面但**而家起唔到**（npm package 404 / 被取代）。parked 喺度做 to-fix 待辦，慢慢修。修好一個就搬去返「已安裝」+ 喺度劃走。
>
> ⚠️ 2026-06-11 更新：gateway 遷移時已將死package（scrapegraph、free-web-search、idea-reality、google-trends、duckdb）**從 config 剔除**（佢哋會搞死 1mcp sync loading），所以唔會再見到 connection error reminder — 呢個 table 而家係唯一記錄，唔好刪。

| MCP | 點解死 | 真正 fix path | 替代品（暫用） |
|-----|--------|--------------|---------------|
| `scrapegraph` | `npx scrapegraph-mcp-server` → npm 404（package 從未存在） | `uvx scrapegraph-mcp`（官方 ScrapeGraphAI，78⭐）但**要收費 `SGAI_API_KEY`** | open-websearch / firecrawl / tavily 已 cover scraping |
| `free-web-search` | `npx free-web-search-ultimate` → npm 404（package 已消失） | 搵返可信版本，或轉 `npx duckduckgo-mcp-server` | **`open-websearch`（1335⭐，已裝）** — Phase 1 改用咗佢 |
| ~~`jobspy`~~ ✅ **修好咗 2026-05-31** | ~~npm 404~~ | **已 clone `borgius/jobspy-mcp-server` → `~/MyGithub/jobspy-mcp-server`，`npm ci`，修咗 prompt registration bug（SDK 1.27.1 要 raw shape 唔係 `z.object()`），boot-test 出 `search_jobs` tool**。config 已指去 `node .../src/index.js`（ENABLE_SSE=0） | — 已修 |
| `scholar-mcp` | 1⭐ solo，被 paper-search（1630⭐）完全蓋過 | 唔修，直接換 → `paper-search-mcp`（已裝）或 `JackKuo666/Google-Scholar-MCP-Server`（343⭐） | **`paper-search` / `arxiv`（已裝）** |

> 修好步驟：boot-test（stdio `initialize`+`tools/list`）→ `claude mcp remove <name>` 舊 entry → `claude mcp add -s user <name> -- <new cmd>` → 跑 health-check.sh 確認 → engine 劃走。

---

## 🔑 Key Activation Checklist（dormant 待啟用）

> 2026-05-31 audit：config 入面**冇一個 research-data free-key API 配咗 key** → 下面全部 listed 但用唔到（endpoint verified alive-needs-key）。撳完 signup 攞到 key，話我知我即刻配落去 + 測試。**優先按 research 用得多嘅排**。
>
> ⚡ **唔使 signup 即刻用**：Congress.gov / govinfo.gov / OpenFEC 全部 `api_key=DEMO_KEY` 即得（2026-05-31 實測：Congress 200、govinfo 41 collections、OpenFEC 返真 candidate data）。
>
> 🗝️ **Keys 已建 scaffold**：`~/.config/research-engine/keys.env`（gitignored，chmod 600）。DEMO_KEY 嗰啲已填好可即用；signup key 留空。用法：`set -a; source ~/.config/research-engine/keys.env; set +a` 然後 curl 用 `${FRED_API_KEY}` 等。攞到新 key 填入去就即刻通。

| 優先 | API | 解鎖 | Signup（多數 instant email） |
|:---:|-----|------|------------------------------|
> **2026-05-31 申請結果**（Claude 經 Chrome 自動申請，key 存 `~/.config/research-engine/keys.env`，account 密碼存 `credentials.txt` + accounts.md ledger）：

| 狀態 | API | 用途 / 備註 |
|:---:|-----|------|
| ✅ | **FRED** | 已攞 + **實測通**（GDP）。經濟時序 |
| ✅ | **US Census** | 已攞 + 啟用。人口/經濟 demographics |
| ✅ | **Open PageRank** | 已攞 + **實測通**（rank）。domain authority |
| ✅ | **FMP** | 已攞 + **實測通**（`/stable/`）。股票/IPO/financials |
| ✅ | **OpenStates** | 已攞 + **實測通**（Google OAuth）。州立法 |
| ✅ | **OpenSanctions** | 已攞 + **實測通**（Google OAuth，free trial key）。制裁/PEP 篩查 |
| 🔑 | **ScrapeCreators** | 未有 `SCRAPECREATORS_API_KEY`；100 initial free credits。解鎖 Facebook/Instagram structured search、posts、groups、comments、events、ads。cached results free |
| 💰 | **TikHub** | 未有 `TIKHUB_API_KEY`；註冊送 US$0.05 trial，但 XHS search/detail/comments 標示 `allow_free_credit=false`。入少量 balance 後每次 US$0.01 |
| ⏳ | **Finnhub** | account + email verified，但 key 仍 reject（疑 anti-bot flag），retest |
| ⏳ | **CORE** | register form submit 咗，key 經 email（多數要審批），未到 |
| ❌ | **Serper.dev** | 自動註冊被 server hard-block（"not possible to register"）— 人手 signup |
| ❌ | **Etherscan** | Cloudflare bot wall 擋 submit — 人手 signup |
| ❌ | **PodcastIndex** | signup widget captcha — 人手 signup |
| ✅ | **WAQI** | `demo` token 即用 |

> 規律：**gov/research/finance（FRED/Census/OpenPageRank/FMP/OpenStates）自動申請順；SERP+crypto+podcast（Serper/Etherscan/PodcastIndex）有強 anti-bot captcha，要人手。**

---

## Tool Sharpening Schedule

> 每個月第一個 session，跑呢個 checklist：

- [ ] `curl -s "https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md" | grep -i "search\|research\|scrape\|analytic\|reddit\|twitter\|monitor\|trend\|social\|intelligence\|seo"` — check awesome-mcp-servers for new entries
- [ ] `gh search repos "mcp server research" --sort stars --limit 20` — search GitHub
- [ ] `npm search mcp-server 2>/dev/null | head -30` — search npm
- [ ] Check Tavily / Exa / Firecrawl release notes for new features
- [ ] Check if any 「應該安裝」tools have been installed → move to 「已安裝」
- [ ] Search: "new free API 2026" + "new mcp server 2026"
- [ ] Update 呢個 file + `/market-research` skill 嘅 allowed-tools

**Sharpening directories to monitor：**
- https://github.com/punkpeye/awesome-mcp-servers (83K+ ⭐)
- https://www.pulsemcp.com/servers
- https://mcpmarket.com
- https://github.com/public-apis/public-apis (300K+ ⭐)
- https://glama.ai/mcp/servers

---

## 唔用嘅工具（記錄點解唔用）

| Tool | 點解唔用 |
|------|---------|
| **Google Custom Search API** | 要 credit card。free-web-search-ultimate + Tavily 夠用 |
| **Browserbase** | Cloud browser。我哋有 Playwright |
| **Browser Use** | AI browser agent，太複雜。Firecrawl 更 practical |
| **Bright Data MCP** | Enterprise scraping。Firecrawl + Apify 夠用 |
| **Crayon CI MCP** | Enterprise competitive intelligence，要 subscription |
| **Klue MCP** | Enterprise CI，要 subscription |
| **G2 MCP** | 要 G2 partnership |
| **Clearbit MCP** | B2B enrichment，我哋唔做 B2B sales |
| **Common Crawl** | Petabyte-scale，太大，我哋唔需要 |
| **galleonli/paper-agent** | 1⭐，3 週前創建，bus factor=1。改用 paper_claw（28⭐，有 email + GH Actions） |
| **Claude web_fetch（code docs）** | Exa WebCode benchmark 實測：12% URL 返回空白，completeness 59.8% vs Exa 82.8%。code research 場景用 Exa Code Context 代替 |

---

## Cost Control（月預算 CAD $20-30）

### 每次 Research Session 預估成本

假設一次完整嘅 `/market-research`（Phase 1 broad scan + Phase 2 deep dive）：

| Tool | 預估用量 | 單價 | 每次成本 |
|------|---------|------|---------|
| Tavily | ~50 searches + 2 deep research | $0.01/search, $0.05/research | ~$0.60 |
| Exa | ~20 semantic searches | ~$0.007/search | ~$0.14 |
| Firecrawl | ~10 pages scraped | 1 credit/page | 10 credits |
| Twitter | ~5 reads（check mentions） | $0.005/read | ~$0.03 |
| 其他全部 | unlimited | 免費 | $0.00 |
| **Total per session** | | | **~$0.77 USD (~$1.05 CAD)** |

### 月度預算 breakdown

| 場景 | Sessions/月 | Tavily credits | Exa 成本 | Firecrawl credits | Twitter | 月總 CAD |
|------|:----------:|:--------------:|:--------:|:-----------------:|:-------:|:--------:|
| Light（2 次 research） | 2 | 104/1000 | $0.28 | 20/500 | $0.06 | ~$2 |
| **Normal（8 次 research）** | 8 | 416/1000 | $1.12 | 80/500 | $0.24 | **~$8** |
| Heavy（20 次 research） | 20 | 1040/1000 ⚠️ | $2.80 | 200/500 | $0.60 | ~$20 |
| Extreme（40 次） | 40 | 2080 ⚠️⚠️ | $5.60 | 400/500 ⚠️ | $1.20 | ~$40 ⚠️ |

### 免費 quota 乜時用完？

| Tool | 免費額度 | Normal pace 用幾耐 | 用完之後 |
|------|---------|:------------------:|---------|
| **Tavily** | 1000 credits/mo（每月 reset） | 2.4 個月嘅 heavy use 先爆 | 超額 $0.01/search |
| **Exa** | $10 one-time credit | ~71 次 research session | 要畀 $0.007/search |
| **Firecrawl** | ~~500 lifetime~~ → **1000 credits/月**（2026-05-31 verified，月度 reset） | normal use 用唔晒 | 超額先 $16/mo（Hobby） |

### ⚠️ Firecrawl 係唯一真正會「用完」嘅

⚠️ **2026-05-31 更正**：Firecrawl 而家係 **1000 credits/月（月度 reset）**，唔再係舊嘅 500 lifetime — 風險細咗好多。以下慳 credit 策略仍然係好習慣，但唔再係「用完就死」嘅 hard limit：

```
慳 Firecrawl credits 嘅方法：
  1. 用 Tavily Extract 代替 Firecrawl Scrape（同樣抓 URL content，用 Tavily quota）
  2. 用 free-web-search 做 general search（唔好嘥 Firecrawl 做 search）
  3. Firecrawl 只用喺「要 crawl 成個 site」嘅場景（Map + Crawl）
  4. Single page → Tavily Extract。Multi-page → Firecrawl Crawl
```

### 免費替代 priority（當 paid tool quota 用完）

```
Tavily quota 用完 → free-web-search-ultimate（10+ engines，零 key）/ open-webSearch
Exa quota 用完   → free-web-search + open-webSearch（⚠️ 唔好 fallback 去 Tavily — 2026-05-31 Tavily 都爆咗）
Firecrawl 用完   → WebFetch（raw HTML）/ Tavily Extract（如 Tavily 有返 quota）
Twitter 太貴     → free-web-search search Twitter（有 Twitter engine）

⚠️ 2026-05-31 實況：Tavily（432）+ Exa（402）quota 兩個都爆 → 任何 search 一律行
   free-web-search-ultimate / open-webSearch（零 key）；Firecrawl Search 仲有 972 credit 可補。
```

### Monthly Cost Alert Rules

```
If Tavily credits > 800/1000 → ⚠️ switch to free-web-search for casual searches
If Exa credit < $2 remaining → ⚠️ reserve for semantic-only searches
If Firecrawl credits < 100   → ⚠️ switch to Tavily Extract for single pages
If Twitter spend > $5/mo     → ⚠️ review if reads are worth it
```

> **結論：Normal usage（每週 2 次 research）= ~$8 CAD/月。遠低於 $30 預算。**
> **即使 heavy usage 都只係 ~$20 CAD/月。要做到 $30+ 要極端頻繁使用。**
> **~~真正嘅 risk 只有 Firecrawl~~（2026-05-31 更正：Firecrawl 升咗做 1000/月 reset，風險細咗）。而家真正 risk 係 Tavily（432）+ Exa（402）quota 兩個都爆，search 要靠零 key fallback。**

---

## Sharpening Log

### Round 28（2026-09-10）— Amazon product search for AI agents

- **Consumer public MCP gap confirmed**：Amazon 有多個 MCP initiative，但 Amazon Business Integrations MCP 只查 API docs、Amazon Ads MCP 只做廣告、AWS Marketplace MCP 只搜 AWS software；AWS Labs `awslabs/mcp` tree 亦無 consumer retail shopping server。未找到 Amazon 宣布 ordinary Amazon.ca account 可供第三方 AI 使用的 public shopping MCP/account API。
- **Official REST paths separated**：Creators API 有真 `SearchItems`，但 access 綁 Amazon Associates final acceptance、Partner Tag、trailing-30-day 10 qualified sales 同 ongoing referral revenue；Amazon Business Product Search/Ordering APIs 有 Canada support，但要 Business account、Amazon approval 同 assigned role。兩者都唔係個人 shopping shortcut。
- **Best practical MCP**：SerpApi 自家 hosted/open-source MCP 支援 `engine=amazon` + `amazon_domain=amazon.ca`，free 250 searches/mo，結構化回傳 ASIN、price、rating/reviews、Prime/delivery、clean link；比 export Amazon cookies 的 unofficial MCP 安全。
- **Zero-new-account fallback live-tested**：existing Serper Shopping key 用 `gl=ca` 搜 `wireless earbuds` 返 40 results，其中 13 個 `Amazon CA`。可即時做 shortlist，但 result link 係 Google Shopping redirect，direct ASIN/link 仍要 second-stage resolution。
- **Security exclusion**：`rigwild/mcp-server-amazon` 會把完整 Amazon session cookies 寫入 `amazonCookies.json`，並 expose orders/cart tools；purchase tool 其實只係 mock。列為不安裝，read-only product discovery 改用 data API，account-specific price/delivery 才用受控 browser read。
- **Amazon Business onboarding live-form audit（2026-09-11）**：官方 Onboarding overview 而家直連 4-page Pulse questionnaire（live GraphQL schema 可公開讀；form 設定 `maximumNumberOfSubmissions: 1`），唔再只係舊 release note 所講 email enquiry。必填 legal entity／incorporation country／HQ／company website／size／revenue bracket／business+developer contacts，並明確分流「own company — internal/operational」vs third-party product；API/AI page 會問 Product Search/Cart/Ordering scope、least-privilege 理由、downstream sharing、AI 是否讀 Amazon Business data、會否送去 OpenAI/Gemini/Anthropic/Bedrock、同 autonomous ordering controls。小公司有 `1–10` employees、`Less than $5M` 選項；冇公開最低規模門檻，但 production approval 仍由 Amazon Business team 指派 role。最乾淨 internal route：Product Search only + Business Product Catalog role + every purchase requires explicit human action。

### Round 16（2026-08-19）— Public-institution staff background verification

- 新增實務次序：①具名人士自己嘅現職 email signature／statement；②機構官方 role page、org chart、escalation guide；③官方 SOFI／public-accounts remuneration schedule；④公開 professional profile；⑤general search。
- **Identity guard**：SOFI 只列 `Surname, Initial` 時，只可以寫「consistent with / corroborative」；唔可以單憑同姓同 initial 斷定係同一人、職銜、年資、學歷或專業資格。
- **Role guard**：用機構對同一職銜嘅公開說明，只可以解釋一般職能同 escalation 位置；唔可以當成該具名人士嘅個人履歷。
- **Tone analysis guard**：將 exact words、已承諾行動、未承諾事項同內心動機分開。`reviewing`／`allow me some time` 支持「position 未落」；唔支持推斷驚、敵意、支持或翻案承諾。
- 呢個流程由 WorkSafeBC Malik Gleason 管理回應研究驗證：general web/LinkedIn 無可靠個人 biography，但官方 email、Client Services Manager 公開職能、provider escalation guide 同 2024–2025 SOFI 足以安全界定職位同證據上限。

### Round 14（2026-05-31）— Health-check repair triage + API key 申請 + AI-Security cluster + Social 擴充

- **health-check.sh 升級「detect + repair」**：source keys.env 用真 key 探 10 個 keyed API（9 verified ✅）；加「⚠️ ACTION NEEDED」triage——每個 fail（zero-key dead / MCP quota 死 / key 壞 / 無 key）都印埋**點修**。PASS 52→67。
- **經 Chrome 自動申請 API key（用 ithiria137 Google session）**：✅ 攞到 + 實測通 7 個 — **FRED · Census · OpenPageRank · FMP · OpenStates · OpenSanctions · Serper**（Serper 之前 "not possible to register" 原來係 transient，retry 即成）。⏳ Finnhub（email verified 但 key 仍被 flag）· CORE（要審批）。❌ **Etherscan（硬 Cloudflare bot wall，撳 Create 完全 no-op）· PodcastIndex（captcha）→ 要人手**。規律：gov/research/finance/Google-OAuth 自動順；crypto/SERP/podcast 有強 anti-bot。Key 存 keys.env，account/PW 存 credentials.txt + accounts.md ledger。
- **新 cluster 🛡️ AI Security / AI Safety**（Nicole 專用）：Simon Willison · Embrace The Red · tldr;sec · LessWrong GraphQL · arXiv cs.CR · Protect AI · Trail of Bits · Project Zero · NVIDIA red team · CAIS · OWASP LLM Top-10 · MITRE ATLAS… + 「最近興乜」trending endpoints（Dev.to top=7 · HN search_by_date · Lobsters tag feeds）。
- **新 cluster 💬 Social/Forum 擴充**：arctic-shift（Reddit Pushshift 後繼）· Misskey · mbin/kbin · 4 個 Lemmy instance · Neynar Farcaster · Substack Notes · daily.dev · PeerTube · Slashdot · StackExchange /sites + Telegram/Discord/Nostr MCP。
- **Interactive mind map**（`research-engine-map.html`）：16+ domain · ~140 source · click 展開睇 source + 即用狀態。

### Round 13（2026-05-31）— Engine-wide sharpen（非 GEO）：fix broken MCP + 16 個新 zero-key source + dormant-key audit

**1. 4 個 MCP 而家根本起唔到（npm 404，config 有但靜靜地 fail — 同 silent-fetch-nothing 同一 root cause）**，全部我親手 `curl registry.npmjs.org` 確認 404。**Nicole 指示：唔好 remove，park 喺「💀 死咗 MCP — 待 fix queue」section 慢慢修**（見下面）：
- `mcp-hn` → **已修** → `uvx mcp-hn`（PyPI 正版，boot-tested）。
- `jobspy` → **已修**（clone borgius source → `~/MyGithub/jobspy-mcp-server`，`npm ci`，patch 咗 SDK 1.27.1 prompt bug〔`z.object()`→raw shape〕，boot 出 `search_jobs`）。config 指去本地 build。
- `scrapegraph`（替代要收費 SGAI key）· `free-web-search`（被 open-websearch 取代）· `scholar-mcp`（被 paper-search 取代）→ **保留喺 config + parked**（見「💀 死咗 MCP queue」）。⚠️ 未處理前每 session show connection error，係刻意 reminder。
- 其餘 research MCP 全 audit 過：healthy（idea-reality 708⭐、open-websearch 1335⭐、arxiv 2803⭐、paper-search 1630⭐、google-trends 81⭐…）；`scholar-mcp`（1⭐）被 paper-search 蓋過，列入 queue 待換。

**2. 16 個新 zero-key source（全部我 curl 200，開新 domain）** — 見上面「Round 13 新增」cluster。最高值：OpenReview（peer-review discourse）、CourtListener（美國 case-law）、SEC EFTS（filing 全文）、Socrata（救返 data.gov）、OpenRouter（live LLM catalog）。另 5 個 free-key（govinfo/OpenFEC `DEMO_KEY` 即用）。

**3. Dormant-key audit**：config 入面**冇一個 research-data free-key API 配咗 key**（淨係 canlii/devto/firecrawl/gemini/twitter 等）→ FRED/Finnhub/Census/CORE/Serper/PodcastIndex/FMP/OpenPageRank 全部 listed 但用唔到。見下面「🔑 Key Activation Checklist」。Congress.gov + govinfo + OpenFEC 用 `DEMO_KEY` 即刻可用，唔使 signup。

**4. Config 改動已備份** `~/.claude.json.bak-r13-*`，用官方 `claude mcp` CLI 改，改完 validate JSON ✓。

### Round 12（2026-05-31）— Retry logic + 真 MCP liveness + stale-URL sweep + skills-marketplace APIs

**1. Health-check retry**：`check()` 加 `--retry 3 --retry-delay 2 --retry-all-errors --retry-connrefused`，timeout 12→25s。效果：之前誤報 dead 嘅 **crt.sh + DOAJ（都係 000 timeout）retry 即返生**。WARN 3→1、PASS 47→52。剩 GDELT（shared-IP 1req/5s，慣性 flaky）+ Open Library 偶發 transient。

**2. 真 MCP liveness probe（最大發現）**：以前個 script 淨係 LIST connected MCP。而家用**真 key 打 search endpoint**偵測 quota 死。實測 **CONNECTED ≠ WORKING**：
- ❌ **Tavily 432 — plan usage limit exceeded**（quota 爆）
- ❌ **Exa 402 — credits exceeded**（$10 用晒）
- ✅ Firecrawl 972/1000 credit、Context7 search API OK、dialog-mcp OAuth reachable（真 call `discover_operations` work）
- 啟示：`initialize` probe 200 唔代表用得，要真 `tools/call` / REST search 先驗到 quota。OAuth MCP（dialog-mcp）bash 探唔到，要 Claude in-session call。

**3. Stale-URL sweep（除咗 Round 11 嗰 11 個，再揾到 8 個，全部 curl verified 2026-05-31）**：
- ❌ **USPTO PatentsView** DNS NXDOMAIN（死）→ `https://data.uspto.gov/api/v1/patent/applications/search`（2026-03-20 遷移）
- ❌ **Common Crawl** `CC-MAIN-2026-13` rolled（404）→ 動態攞 `collinfo.json[0].id`（而家 `CC-MAIN-2026-21`）
- ❌ **YC OSS** `batches/` 錯 host → `yc-oss.github.io/api/batches/<batch>.json`（all.json 喺 raw host 仲 work）
- ❌ **Frankfurter** `/latest` 404 → `/v1/latest`
- ❌ **OpenRank.io** 變 React SPA，API 死 → 改用 Open PageRank
- ❌ **PapersWithCode RSS / HuggingFace papers.rss / LangChain blog RSS** 全部撤咗 feed
- ✅ **KEY-required API 全部 ALIVE-NEEDS-KEY（endpoint 冇搬）**：FRED、Census、Finnhub、FMP、OpenCorporates、Open PageRank、Serper、PodcastIndex、UK Companies House、Lens、EPO、Dune、Etherscan、CORE、Unpaywall。**Congress.gov DEMO_KEY 仲 work**；BLS v1、libraries.io 零 key 仲出 data。
- 📊 **Firecrawl quota 更正**：engine 一直寫「500 lifetime」，實測係 **1000 credits/月**（月度 reset）。

**4. 新 source（task #4，全部 live verified，加入 GEO cluster）**：
- ✅ **skills.sh** zero-key JSON API `GET /api/search?q=`（Vercel-Labs skill directory，含 install counts）
- ✅ **agentskills.to** zero-key JSON API `GET /api/skills?q=`（注意 `.to` 唔係 `.io`；`.io` 係 spec docs）
- ✅ **Otterly.ai** 唯一有公開 OpenAPI 嘅 AI-visibility tracker（`data.otterly.ai/v1/openapi.json` zero-key spec、trial 給 key、有 Claude Skill）
- ✅ **agentskills-mcp**（`pinkpixel-dev/agentskills-mcp`）可裝 — 合 Nicole「有 MCP 就裝」
- ❌ **Peec.ai** 冇 public API（404，enterprise-only）；**WebMCP** W3C draft + Chrome 146 flag，未可做 data source（純 watch）

**5. AI-visibility tracker deep-probe（follow-up，verified 2026-05-31）**：逐個 curl 探咗上輪 flag 嘅 5 個：
- ✅ **skilldock.io** 有**免 auth 真 API**（`api.skilldock.io/v1/skills` 200 返 188 skills、`/v1/stats`、`/openapi.json`）+ `pip install skilldock` SDK → **加入 skills-marketplace zero-key bucket**
- ⚠️ **Trakkr.ai**（OpenAPI 3.0.3 `trakkr.ai/openapi.json`，最乾淨）+ **Rankscale.ai**（雙 API surface + 官方 OpenClaw Skill）→ 有真 API 但 **gate 喺付費 plan**，free tier 無 API → watch（有 key 先用）
- ❌ **Knowatoa**（free 得 dashboard/CSV，API $249/mo+，Heroku Rails session-only）+ **AIVO**（係 methodology standard 唔係 tool，email-gated）+ **Radarkit/Leapd**（dashboard-only）→ drop programmatic 用途
- 5 個全部**冇 MCP**。已更正 engine 入面「AI-visibility trackers（free tier）」嗰行嘅 overclaim（免費 tier 其實攞唔到 API data）。

**6. Improvements（2026-05-31）**：
- 📖 拆咗 **Otterly OpenAPI 全部 21 endpoint** 寫入 engine，標 ⭐ GEO research 最有用嗰 5 個（citations / citations-prompts / prompts-ai-responses / recommendations / geo-audits）。
- 🔁 **agentskills-mcp 裝咗又移除**（Nicole 指正）：skill 不過係 MD，install/常駐 MCP 都係嘥 per-session context。改用 **download-link-on-demand** 模式。
- 📥 **Download + filter GEO skills**：clone `aaron-he-zhu/seo-geo-claude-skills`（20 個），逐個 review frontmatter，**keep 10 / skip 10** → 存 `skills/geo/`（on-demand Read，零 context 開銷）。Keep = 純 methodology（geo-content-optimizer、content-quality-auditor〔CORE-EEAT 80-item〕、domain-authority-auditor〔CITE 40-item〕、entity-optimizer、schema-markup-generator、competitor/content-gap/serp-analysis、on-page/technical auditor）；Skip = 要 live SEO-tool data 或 ops/reporting 或同 Nicole memory 系統撞（rank-tracker、performance-reporter、alert-manager、backlink-analyzer、memory-management、keyword-research…）。

**Verification 原則**：呢輪所有 status 都係今次 curl/tool 實測（唔信舊註解）。未親手測過嘅 ~100 個工具**冇**亂 stamp「verified」date——只有上面打 ✅/❌ + 日期嗰啲先係真驗過。Dead endpoint 嘅 silence ≠「found nothing」。

### Round 11（2026-05-30）— GEO cluster + Health Check + Forum MCP mandate
- **新 cluster 20：GEO / AI Answer-Engine Visibility**（見上面 SEO section 後）— 補返 engine 一直缺嘅 gap：點令 product/package 俾 AI engine + coding agent 發現/推薦/用啱。核心 evidence：llms.txt 對 AI search ≈ 0（limy.ai 500M event study、Google 官方否認）但對 coding agent 有用；**docs-MCP > llms.txt**（Astro 移除 llms.txt 改 MCP）；Reddit 主導 AI citation（Perplexity 46.7%）；Context7 submit = zero-effort win。
- **Health check script（歷史記錄）**（`health-check.sh`）— 初版逐個 ping zero-key API + CLI + connected MCP，首次跑 54 個 zero-key API 有 11 個 dead，揭發 agent silently fetch 唔到嘢。2026-10-13 已改成分層模式：普通 research 只跑 selected `--source`；`--community`／`--full` 留畀定期維護，唔再每個 session 盲掃全 inventory。
- **Forum route 歷史更正** — 當時用 dialog-mcp／logged-in Chrome 對比 raw Reddit curl，證明 browser route 可以攞到完整 thread。現行 route 已唔再用 dialog-mcp：live Reddit 用 Agent Chrome JSON，archive/search cross-check 用 Arctic Shift，禁 raw `reddit.com/*.json` curl。

### Round 1（2026-03-22）
搵到 30+ 新工具。安裝 5 個：idea-reality、dialog-mcp、free-web-search、newsmcp、mcp-hn。

### Round 2（2026-03-22）
Verified Round 1 嘅「Should Install」list。安裝 3 個：rss-reader、google-trends、jobspy。
Skip 咗：Brave Search（同 Tavily 重疊）、SerpApi（付費）、macrocosmos（niche）、GPT Researcher（Tavily Research 夠用）、open-sales-stack（1 star，internal project）、Jina（同 Firecrawl 重疊）。

### Round 4（2026-03-23）
發現 WebCode（Exa search benchmark paper）係被動接收（email）。決定建立主動 research paper 監控。新增 Research Papers & Benchmarks section：10 個 RSS feeds（arXiv x3、Papers with Code、HuggingFace、OpenAI、LangChain、The Gradient、Simon Willison、Import AI）+ Semantic Scholar API + arXiv API。

**WebCode Benchmark 關鍵數據（直接影響我哋嘅 research workflow）：**

| Provider | Completeness | Signal | Code Recall | Table Recall | ROUGE-L |
|----------|:-----------:|:------:|:----------:|:----------:|:-------:|
| **Exa** | **82.8** | **94.5** | **96.7** | 91.9 | **83.2** |
| Parallel | 74.2 | 77.6 | 94.1 | **92.2** | 73.7 |
| Claude web_fetch | 59.8 | 55.1 | 82.4 | 82.0 | 66.8 |

*Claude web_fetch 12% URL 返空白。Exa RAG groundedness 遠超其他 provider。*

**行動：** Agent D 嘅 code research 全部用 Exa Code Context，唔再用 Claude web_fetch。Tavily Extract 做 fallback。

**Daily Research Blog Pipeline（Cloud-based，唔需要開機）：**
- Trigger: `trig_01P9CDN9AtuETRxayS4b5TeF`（每日 8am PDT）
- 自動 fetch 10+ RSS feeds + benchmark sites → 篩選有數據嘅 research → 寫英文版（公開 publish）+ 廣東話版（draft）→ 發佈到 dev.to
- Series: "AI Research Daily"
- API key: mcpware-automation（dev.to）
- 重點：benchmarks > comparisons > evaluations > 行業新聞（只佔 20%）

### Round 5（2026-03-23）— Meta-Research: Upgrade the Engine Itself
用 research engine 去搵可以改善 research engine 嘅工具。關鍵發現：

**新 MCP（待安裝）：**
- `paper-search-mcp`（816⭐）— 一個 MCP 搜 20+ 學術平台，取代多個個別 API
- `semantic-scholar-mcp` — Full S2 API with citation networks + recommendations
- `arxiv-mcp-server` — arXiv semantic search + trend analysis（比 RSS 更精準）

**新 API：**
- OpenAlex（250M+ papers，免費 100K req/day，唔使 auth）
- CORE（300M metadata + 40M full-text PDFs，免費 key）
- Crossref（180M records，DOI resolution）
- Unpaywall（用 DOI 搵 open access PDF）

**填補缺口：**
- `ai-rss-feeds` GitHub repo 用 AI 生成 RSS for DeepMind/Cursor/Groq/Stability（之前標為「冇 RSS 靠 HN」）
- `changedetection.io` 可以監控所有 leaderboard 變化（SWE-bench/LMSYS/LiveBench/Aider/PWC）
- Quality scoring formula：author_lab(20) + social(15) + conference(25) + code(10) + recency(10) + citation_velocity(20)

**Pipeline 改進：**
- DOI-based dedup across all sources（n8n pattern）
- 對 <6 month papers：weight author reputation + social signals > citation count
- Paper Agent 做 explainable filtering（唔係全推送，只推有料嘅）

**Research Engine 從 15 MCP → 18 MCP（+paper-search, +arxiv, +semantic-scholar）。API 從 2 個 → 6 個。**
**後續：changedetection.io ✅ Docker 已跑、ai-rss-feeds ✅ 5 個 feed URL 已搵到、Paper Agent ❌ 改用 paper_claw（28⭐，GH Actions + email）。**

### Round 3（2026-03-22）
Final sweep。安裝 1 個：wayback（competitor history tracking）。
搵唔到 npx-installable 嘅：Stack Overflow MCP、GitHub star history MCP、email alert MCP、Open Collective MCP、awesome list monitoring MCP、npm trend MCP。呢啲缺口記喺「搵唔到」section。

**3 Rounds 總計：10 個新 MCP installed。Research engine 從 5 個 MCP → 15 個 MCP。**

### 而家搵唔到但想要嘅（市場缺口）

| 想要咩 | 現狀 | Workaround |
|--------|------|-----------|
| Stack Overflow MCP | 冇 npx 版 | 用 raw API：`curl api.stackexchange.com/2.3/...` |
| GitHub star history | 冇 MCP | 用 `gh api repos/{owner}/{repo}` 只有 current count |
| Email alert monitoring | 冇 MCP | 用 Gmail MCP search newsletters |
| Open Collective funding | 冇 MCP | 用 raw GraphQL API |
| Awesome list monitoring | 冇 MCP | 用 trackawesomelist.com RSS + rss-reader MCP |
| npm download trends | 冇 MCP | 用 raw API：`curl api.npmjs.org/downloads/...` |

---

## Self-Evolution Rule

> **每次用 research engine 做完 research，都要 self-evolve：**
>
> 1. 搵到新工具？加去「應該安裝」或「已安裝」section
> 2. 搵到新 data source？加去 RSS feeds 或 API list
> 3. 搵到 workflow 改進？update Research Workflow section
> 4. 搵到工具唔 work？加去「唔用嘅工具」section with reason
> 5. Update Sharpening Log with date + what changed
>
> **呢個 file 係 living document。每次 research 都要令佢變得更好。**

### Round 7（2026-03-28）— Self-Upgrade: 新 Tools + APIs + Skills + Quota Classification

用 deep-research 搜索 GitHub/Exa/WebSearch 搵到大量新工具。

**新安裝：**
- `last30days-skill`（13,958⭐）— Reddit/X/Bluesky/YouTube/TikTok/Instagram/HN/Polymarket 最近 30 日，multi-signal scoring。已裝 `~/.claude/skills/last30days`
- `mcp-youtube-transcript`（353⭐）— YouTube transcript extraction
- `open-webSearch`（866⭐）— 8 引擎零 key 搜索
- `paper-distill-mcp`（53⭐）— 11 源 parallel 學術搜索

**新發現（待安裝）：**
- `Xpoz MCP`（6⭐）— 1.5B+ social posts indexed，remote MCP
- `altmbr/claude-research-skill`（6⭐）— multi-agent research orchestrator
- `algonacci/mcp-wikipedia`（10⭐）— Wikipedia MCP
- `ScienceAIHub/PaperMCP`（2⭐）— 32 academic tools
- `Apify Latest News MCP` — 14 tools，27 free APIs

**新免費 API（11 個）：**
GDELT、PubMed、Europe PMC、bioRxiv、DBLP、DOAJ、Zenodo、The News API、NewsDataHub、ScrapeCreators、HN Firebase

**新 Skills 發現：**
- `coreyhaines31/ai-seo` — AI SEO optimization skill
- `sanity-io/seo-aeo-best-practices` — SEO/AEO patterns

**Quota Classification 新增（見下面 section）。**

**Research Engine 從 18 MCP → 22 MCP（+last30days +youtube-transcript +open-webSearch +paper-distill）。API 從 6 → 17。**

**market-research skill 已合併入 deep-research。** deep-research 依家有兩個 mode（general + product），auto-detect from input。

### Round 8-9（2026-03-28）— Saturation Check

用 GitHub search + Exa + WebSearch + PulseMCP 再掃一轉。搵到：
- `nickclyde/duckduckgo-mcp-server`（937⭐）— DDG search，但 open-webSearch（866⭐）已包含 DDG + 7 個引擎，skip
- `pathintegral-institute/mcp.science`（123⭐）— 科學計算 MCP（GPAW/NetKet/Materials Project），非 general research，skip
- `awslabs/mcp` git-repo-research（8,598⭐）— **已 deprecated**，官方推薦 Context7（✅ 我哋已裝）
- `txyz-search` — 學術搜索，但要 TXYZ API key，skip（paper-distill 已經涵蓋 11 源）

**結論：已達到 saturation。下次 sharpening 排 2026-04-28。**

---

### 🏷️ Quota Classification（Round 7 新增）

> 分清邊啲工具零成本可以無限用，邊啲有 quota 要慳住用。

**🟢 零 Quota / 完全免費（盡量用呢啲）：**

| Tool | 類型 | 限制 |
|------|------|------|
| HN Firebase API | API | 零 key，零 limit |
| OpenAlex | API | 100K req/day，零 key |
| arXiv API | API | 零 key，零 limit |
| Crossref | API | 零 key，polite pool |
| DBLP | API | 零 key，零 limit |
| DOAJ | API | 零 key，零 limit |
| PubMed | API | 3 req/sec（有 key 10/sec） |
| Europe PMC | API | 零 key |
| bioRxiv | API | 零 key |
| GDELT | API | 零 key，零 limit |
| Zenodo | API | 零 key |
| Wikipedia API | API | 零 key |
| Reddit live | Browser | `agent-chrome.py fetch` through logged-in Chrome；raw curl `.json` = 403 |
| Arctic Shift | API | zero-key Reddit archive/search/tree |
| HN Algolia | API | 零 key |
| npm Downloads API | API | 零 key |
| open-webSearch | MCP | 零 key，零 limit |
| mcp-youtube-transcript | MCP | 零 key |
| paper-search-mcp | MCP | 零 key（wraps free APIs） |
| paper-distill-mcp | MCP | 零 key（wraps free APIs） |
| arxiv-mcp-server | MCP | 零 key |
| ~~newsmcp~~ | MCP | 💀 shut down 2026-06 |
| Context7 | MCP | 零 key |
| Dev.to API | MCP | 零 key |
| last30days（without keys） | Skill | 只有 web + HN |

**🟡 有 Free Quota（用完要付費，慳住用）：**

| Tool | Free Quota | 用完之後 | 每月 Reset？ |
|------|-----------|---------|:----------:|
| **Tavily** | 1000 credits/mo | $0.01/search | ✅ 每月 |
| **Exa** | $10 one-time | $0.007/search | ❌ one-time |
| **Firecrawl** | **1000 credits/月**（2026-05-31 verified；舊「500 lifetime」已過時） | $16/mo Hobby（超額先要） | ✅ 每月 |
| **Semantic Scholar** | 100 req/5min | 有 key 10 RPS | ✅ rolling |
| **CORE** | 免費 key required | — | — |
| **Unpaywall** | 免費（email required） | — | — |
| **Stack Overflow** | 10K req/day | — | ✅ daily |
| **ScrapeCreators** | 100 free credits | 付費 | ❌ one-time |
| **The News API** | Free tier | 付費 | — |
| **NewsDataHub** | 50 req/day | 付費 | ✅ daily |
| **Twitter** | $0.01/read | — | — |
| **last30days（with keys）** | depends on ScrapeCreators | — | — |

**🔴 付費 / 需要 Subscription：**

| Tool | 成本 |
|------|------|
| Apify | $5 free/mo，之後 pay-per-use |
| Brave Search | $5 free/mo |
| SerpApi | 100 free/mo |
| Xpoz | Free tier + OAuth |
| Spectrawl | 5,000 free/mo |

---

### Round 6（2026-03-24）— SEO/AEO/GEO Research

搵到 4 個新工具 + 2 個新標準：

**新工具（待安裝）：**

| Tool | 做咩用 | 成本 | 點裝 |
|------|--------|------|------|
| **@ainyc/aeo-audit** | AEO readiness audit — 13 criteria check | 免費 | `npx @ainyc/aeo-audit` |
| **aeorank** | 34 criteria + 13,619 domain benchmark database | 免費 | `npx aeorank` |
| **aiseo-audit** | 30+ AEO/GEO factors analysis | 免費 | CLI tool |
| **Canonry** | Monitor AI citation Share of Voice（你喺 AI answers 出現幾多次） | Freemium | SaaS |
| **npm-seo-optimizer** | npm package SEO optimization tool | 免費 | `github.com/ronyman-com/npm-seo-optimizer` |
| **Nakora.ai** | GitHub SEO analyzer（reverse-engineered GitHub search algo） | Freemium | Web tool |

**新標準：**
- **llms.txt** — v1.1.1 spec，~950 sites 用緊。Markdown file at domain root，AI agents 直接讀。成本幾乎零。
- **npm --provenance** — 2026 trust signal，verified link between npm package 同 GitHub repo。

**關鍵數據：**
- AI traffic converts **9x better** than Google organic（15.9% vs 1.76%）
- FAQPage schema = **3.2x** higher AI citation rate
- Reddit appears in **~68%** of AI-generated responses
- Answer-first paragraphs get cited **67% more** by AI
- GitHub topic tags 係 most underoptimized lever for repo discoverability
- Show HN has **0.4 penalty** — needs 2x upvotes to rank equal

**行動：** 已加 llms.txt 去 CCO repo。下一步：run AEO audits、submit 去所有 MCP directories、add FAQPage schema。

---

### Round 18（2026-08-19）— BC legal primary-source acquisition hardening

WorkSafeBC s.135 research exposed a source-integrity problem that applies to all Canadian legal research: a case number, a search hit and a summary are not the source document.

**New primary-source workflow:**

1. **Archive the complete originating-body document.** Preserve an official-issued PDF when the issuing body supplies one. When the body publishes official HTML, preserve the raw HTML and extracted text; any PDF made locally must say `local-render` in the filename and manifest.
2. **Do not assume one appeal number means one document.** WCAT Decision Search returned three public PDFs for `A2400395` and two for `A2500471`. Archive every exact-number result with a date-qualified filename, then mark the relied-on merits decision separately.
3. **Verify content, not only HTTP 200.** Check `%PDF`, page count, extracted word count and a minimum completeness floor. Record final URL, byte count, SHA-256 and retrieval timestamp.
4. **Treat portal outages as outages.** WorkSafeBC Review Division returned repeated HTTP 503. That is not evidence that a decision is unavailable. Use bounded retry, preserve a truthful error record and fall back only to a previously verified exact harvest from the same official portal.
5. **Keep official and local formats distinct.** Review Division provides session-bound/base64 decision HTML rather than a public originating-body PDF. BC Courts normally publishes official judgment HTML. A locally rendered reading PDF is useful, but is never labelled an official-issued PDF.
6. **Keep a machine-readable ledger.** Generate JSON/CSV manifests and `SHA256SUMS`; make partial runs write a truthful manifest in `finally`; provide a source-group selector so a failed endpoint can be retried without redownloading everything.
7. **Full text before synthesis.** A summary, headnote, annual-report note or another case's citation is a discovery lead. It does not support a direct quotation until the underlying full decision is opened and checked.

**Reusable BC endpoints:**

- WCAT Decision Search: `https://www.wcat.bc.ca/home/search-past-decisions/?appeal_number=<ID>`
- WCAT official PDFs: `https://www.wcat.bc.ca/decisions/pdf/YYYY/MM/<ID>.pdf` (suffixes such as `_1` exist)
- WorkSafeBC Review Division: `https://rdpubsearch.online.worksafebc.com/`
- BC Courts official judgments: `https://www.bccourts.ca/jdb-txt/...`
- SCC official newer-decision PDFs: `https://www.scc-csc.ca/cso-dce/<citation>_eng.pdf`

**Tooling produced:** `Evidence/Case-Law-Library/04-Claim-s135-mental-disorder/tools/acquire_official_full_text.py` now implements this workflow with resumable source selection, validation, provenance and hashes.

### Round 19（2026-08-23）— Official-template visual verification

Design-template research needs the same source discipline as text research. Use image search only for broad pattern discovery, then retrieve at least one complete issuing-body PDF and render it for visual inspection. Separate recognition certificates from factual verification letters: borrow their identity hierarchy, but include only fields supported by known facts. Record omitted fields as deliberate exclusions in the coverage ledger.

### Round 20（2026-08-24）— Dynamic government-PDF recovery

BC Community Gaming Grants 嘅 2026 official guidelines 經官方頁面 click 可取得完整 53-page PDF，但 web `open`
其後對同一 dynamic asset URL 回 502。用 `curl -L` 下載、`pdftotext -layout` 抽字後成功核對 program-description、
participant-count、volunteer-hour 同 gaming-record 條文。新增 official dynamic-PDF fallback：originating page + final URL
雙重 provenance、PDF integrity/hash、完整抽字、FAILED 同 GOT DATA 分開記。

### Round 21（2026-08-26）— Hebrew Bible primary-text source

- **Mechon-Mamre Hebrew-English Bible**（`https://mechon-mamre.org/p/pt/`）提供逐章希伯來文與英文平行經文，適合核對Tanakh故事、章節同短引文；本輪已用Genesis 39、Deuteronomy 19及1 Kings 21交叉核對誣告、查證與假見證主題。
- **Sefaria API**（`https://www.sefaria.org/api/v3/texts/<REF>`）適合結構化核對希伯來原文；部分英文版本受授權限制而經API返回`null`，英文引文改用Mechon-Mamre頁面直接核對。
- **Quran.com API**（`https://api.quran.com/api/v4/verses/by_key/<SURAH:VERSE>`）可一次核對多個英文譯本；本輪用Qur'an 12:25–35及49:6核對約瑟故事、證據查驗同收到消息後先查證嘅原文。
- **SuttaCentral Bilara API**（`https://suttacentral.net/api/bilarasuttas/<REF>/<TRANSLATOR>`）提供逐行根本語、英文譯文同註釋；本輪用Dhammapada 256–257核對匆忙判斷、公正及不偏不倚。
- **The Latin Library**（`https://www.thelatinlibrary.com/`）適合核對古典拉丁原文；本輪以Seneca《Medea》199–200核對`parte inaudita altera`段落，英文語境另以Theoi Classical Texts交叉檢查。

### Round 22（2026-08-26）— Corporate org-chart escalation research

- 內部組織圖研究要分清 `people reporting to`、`manager`、`direct report` 同 `also works with`；同頁出現不等於匯報關係。
- 升級對象不能只按職級選。用三點交叉：內部 reporting line、公司公開職責、官方 filing 的責任範圍。
- Privacy／employment record 搜尋要分開「法律決定人」與「records custodian」：DPO／General Counsel 負責回覆及指示；HR／IT 可能持有資料，但不應把 applicant 推去逐個追 custodian。
- 同名者多而公開身份不足時，保留內部職銜並標記 `NO RELIABLE MATCH`；不得把其他人的公開履歷拼接到目標人物身上。

### Round 23（2026-08-28）— Statutory filing deadline vs evidence-wait date

- 法律程序研究必須分開三個時鐘：①啟動 review／appeal 嘅法定期限；②另一條證據線嘅策略等待日；③開檔後 submission／補件期限。唔可以因為等另一機構回覆而延遲保全本身嘅 review 權利。
- WorkSafeBC claim review 嘅官方控制係決定後 90 日內提出；health-and-safety enforcement review 係 45 日。Review Division 官方流程亦寫明，request 提交並 initiated 後會提供 decision file，所有 parties 再有機會交 submission／additional information。
- 因此，日期標籤要連同來源同法律功能記錄。例如 `2026-09-04 Varonis PIPA response control` 唔可以縮寫成 `Prevention deadline`，更唔可以當成 Claim 48979313 Review 嘅 filing trigger。

### Round 24（2026-08-28）— Review filing may terminate first-instance reconsideration

- 行政覆核研究唔可以只比較「早交」同「遲交」嘅 deadline risk；要先查正式 filing 會唔會改變原決定人嘅 jurisdiction、通知其他 parties、披露文件，同啟動法定 decision clock。
- WorkSafeBC compensation decision 有兩個重疊但功能不同嘅時鐘：原決定人一般可於決定後 75 日內自行 reconsider；worker 有 90 日提出 Review Division review。一旦 review 已依 s.270 filed，s.123(2)(b) 一般禁止 Board 再 reconsider 原決定。撤回 review 亦唔會自動令原決定人恢復 jurisdiction。
- 所以 timing recommendation 必須列明：`reconsideration window`、`review filing deadline`、`hard internal filing date`，並核對正式 filing 會否例行通知 employer。不得把「越早保全權利」當成一律越有利；亦不得拖到最後一日。應按用戶目的採用有明確 hard stop 嘅 controlled delay。

### Round 25（2026-08-29）— BCLaws current-consolidation and multi-ground pleading check

- BCLaws 搜尋結果可同時返回舊 `consolXX` 頁和現行 `complete/statreg` 頁；兩者文字可能不同。引用現行法例前，必須開啟 `complete/statreg` 版本並核對頁面當日內容。今輪舊 `consol28` 頁仍顯示《Human Rights Code》s.22 為六個月，而現行 `complete/statreg` 及 BCHRT 2026 Form 1.1 均顯示一年。
- BCHRT 程序研究要分開 `case/file`、`statutory provision`、`protected ground` 和 `allegation`。同一 employment complaint 可在同一份 Form 1.1／同一案號內選擇多個 grounds；修訂則依 Rule 24 用一份 Form 3 加入 details 或 allegations。每個 ground 仍須分別陳述 protected characteristic、adverse effect 和 nexus。
- 表格頁數屬 filing constraint，不是研究或 master pleading 的內容上限。保留完整 master，再把獲批准的事實鏈壓縮到 Tribunal 指定的 Form 3 附頁上限；不得以多份 Form 3 規避同一次 amendment 的頁數控制。

### Round 26（2026-08-29）— Inferring institutional reaction without cultural stereotyping

- 研究收件人「可能點諗／有咩感受」時，民族、國籍、宗教或姓名不是可靠心理證據。最多只可作弱背景，並要明確標示不能推斷個人態度。
- 較可靠的推論順序是：①收件人的正式職責及決策權；②收到的實際文字；③同期回覆的時間和逐字措辭；④其後可觀察行動；⑤機構公開政策及監管承諾。每個推論要指出哪些是文件事實、哪些是角色導向的推斷。
- 同日回覆同時出現安撫、保留原決定、限制溝通和結案語言時，應拆成多個可能並存的 institutional objectives（穩定僱傭關係、建立無報復紀錄、控制法律／聲譽風險、限制未來記錄量），不得把單一句子解讀成完整內心動機。

### Round 27（2026-08-31）— BCHRT complaint／amendment drafting source hierarchy

- BCHRT amendment research 先鎖定現行官方 Form 3、Rules 同 General Application guide；格式、頁數、字體、evidence restriction、particulars／new allegations 分別全部由現行官方來源控制。
- 寫作方法再用 CLAS drafting guide 加一份完整 mock complaint 校準。完整 mock 主要教 chronology、roles、material words、adverse effect 同 nexus；唔用來取代官方程序規則。
- 公開 filed historical Form 3 只用來觀察 amendment syntax：逐項寫清楚 add／delete／replace。舊表格唔控制現行格式。
- Decisions 用來判斷 particulars 與 new allegations 的邊界，以及公平通知所需 facts；唔將整串 authorities 搬入三頁 complaint body。
- 找不到公開的近期完整 Form 3，必須記為 `EMPTY／UNAVAILABLE`，唔可以當成「不存在」；改用 current official form + CLAS full mock + actual historical filing + recent decisions 的組合。
- Complaint body 係 material-fact document，唔係 factum：先說今次改甚麼，再按日期寫 who did what，最後逐項連接 protected characteristic／activity、adverse effect 同 nexus。案例、證據路徑及完整法律分析留在 internal source ledger。

### Round 28（2026-09-12）— Public Naver Cafe retrieval without Search API credentials

- 韓國醫美個案搜尋可以先用 Naver 公開 HTML 搜尋發現 cafe URL；唔應該因為 Naver Search API credentials 缺失就把結果標成 `EMPTY`。API credentials 缺失係 `FAILED`，公開 HTML fallback 另行記錄。
- 公開 Cafe 可用 `https://apis.naver.com/cafe-web/cafe-search-api/v2/cafes/{cafeId}/search/articles` 搜尋文章，再用 `https://article.cafe.naver.com/gw/v4/cafes/{cafeId}/articles/{articleId}` 取文；兩者加 request header `X-Cafe-Product: mweb`。先由 cafe URL／metadata 確認 `cafeId`，再固定記錄 article ID、標題、日期及 canonical public URL。
- Member-only cafe 的 article endpoint 會回 HTTP 401 / error `0004`。Naver 搜尋頁有時仍提供有限 public snippet；snippet 只可支持 snippet 中明示的文字，必須標 `SNIPPET ONLY`，不可當完整文章、不可推斷相片、留言或未顯示手術材料。
- 醫美術式驗證要把 `무보형물`（無人工假體）、`자가연골`（自體軟骨）同 `무이식／연골이식 없이`（零移植）分開。`코끝묶기` 亦可能與鼻中隔／耳軟骨移植同時做；只有手術清單或病歷式材料說明可證明零移植，before/after 外觀本身不能證明。

### Round 29（2026-09-13）— Sungyesa full-post and original-image recovery

- Sungyesa 原帖被 Cloudflare 403 擋住時，可用 `https://r.jina.ai/http://sungyesa.com/d03/{postId}` 取回完整可檢索 Markdown；相片連結仍指向 Sungyesa 靜態原圖，可直接下載保存。呢條路徑可保留帖文標題、術式、日數、醫院、醫生欄、逐圖 `전／후` 標籤及 canonical post URL，比搜尋 snippet 完整。
- 圖片標籤同正文可能矛盾（本輪有兩圖均標 `전`，但作者正文明寫術前及術後 6 小時）。遇到矛盾唔可以靜默修正：PDF 要同時記錄網站標籤、正文敘述、視覺線索同判讀不確定性。
- 比較醫生風格時先按時間穩定度分層：同一人 6–12 個月更新 ＞ 單次長期病人帖 ＞ 1–2 個月時間線 ＞ 術後數日 ＞ 官方精選相。早期低腫脹只支持恢復期觀察，不能代替最終線高、疤痕或持久度。

### Round 30（2026-09-13）— Cross-platform cosmetic-review deduplication

- 同一段醫美評價出現在兩個平台，唔等於兩名獨立病人或兩次獨立驗證。先以術式、醫生、日期／術後日數、圖片同正文 exact／near-exact match 做跨平台 dedup；相同內容只計一個 patient episode。
- 重複貼文可以由病人自行 cross-post、平台同步、活動獎賞或代營運造成；除非來源明示，唔推斷邊一種。但報告必須標示 `DUPLICATE / NOT INDEPENDENT`，並降低「多平台一致」的證據權重。
- 醫生評分頁要先讀 moderation policy。若頁面明文只容許推薦／感謝、不容許個別醫生負評，該頁的高分與大量留言只支持正面訊號的存在，不能估算滿意率、併發症率或正負評比例。

### Round 31（2026-09-29）— Tax-disability forms vs involuntary-care risk

- 評估健康／稅務表格會否觸發強制精神科介入時，要分開三套法律功能：①表格本身嘅行政目的及用字；②稅務資料保密與例外；③省級強制留院嘅獨立法定程序。相同詞語（例如 `severe`、`risk of harm`）唔代表相同法律測試。
- 先開完整現行 T2201，逐項核對實際 checkbox、上下文及 `marked restriction` 定義；再核對《Income Tax Act》s.241。一般保密係主規則，而 s.241(3.1) 只係容許披露與 `imminent danger of death or physical injury` 有關嘅 taxpayer information，唔應將一般功能限制誤寫成自動轉介制度。
- BC 強制留院要用現行 BCLaws `complete/statreg` 版本核對《Mental Health Act》ss.1、22、28及《Mental Health Regulation》規定嘅 Form 4.1／4.2。T2201 唔係 medical certificate；勾選框本身唔取代當時由 physician／NP 作出嘅 examination、法定意見及指定表格。
- 風險溝通要同時避免兩種錯誤：唔可以保證「絕對零披露」，亦唔可以將單一歷史／功能性 checkbox 誇大成 `imminent danger`。要標出最直接涉及安全／現實感／治療決定能力嘅欄位，並把較典型 executive-function 欄位分開。

### Round 32（2026-10-07）— BC Supreme Court self-represented cost triage

- 民事訴訟成本要分開三盤數：①交畀法院嘅 Schedule 1 fees；②自己要付嘅送達、謄本、專家等 disbursements；③輸訴後可能判畀對方嘅 costs。只講「可申請免法院費」會嚴重低估風險。
- Rule 20-5 fee waiver 只處理政府 Schedule 1 fees；官方 Form 80 package 明文指出，waiver 唔包括 transcripts，亦唔包括判畀對方嘅 costs。申請人要以收入、支出、資產、工作及技能資料證明 undue hardship，唔係單憑「唔想畀錢」。
- 短審訊亦要先核對 Rules 14-1(1)(f)(ii) 同 15-1(15)：完成審訊為 1 日或以下、超過 1 日至 2 日、超過 2 日至 3 日，現行 fast-track costs 分別係 $8,000、$9,500、$11,000，另加合理 disbursements 及適用稅項；法院仍可另行命令。
- 風險清單必須另查 Rule 9-1 settlement offers、Rule 9-8 discontinuance，同 Rule 3-4 counterclaim。輸訴本身唔會自動產生一宗「告返轉頭」；但同一宗案嘅 costs order 可執行，而有獨立事實及法律基礎嘅 counterclaim 即使原告撤訴亦可繼續。

### Round 33（2026-10-07）— Separate access nondisclosure from substantive employment wrong

- BC 私人合約僱傭一般冇獨立 procedural-fairness claim；`Golob` 顯示即使調查嚴重有缺陷，單憑程序缺陷仍不足以成立民事 claim。研究必須先指出真正嘅 contract／tort／statutory wrong。
- PIPA s. 30(2) 只係容許 investigation access response 不確認或否認資料存在；佢唔會驗證 finding 正確。要同時核對 s. 23 exception、s. 28 complete response、s. 33 accuracy、s. 51 burden 及 s. 52 remedies。
- 民事 pleading 要寫 material facts，唔需要預先附上對方掌握嘅全部證據。Rule 3-7(17)、(20) 容許按當時已知程度 plead knowledge／particulars；Rule 7-1 及 7-2 再處理文件披露同宣誓問話。
- 當紀錄只證明公司冇指出、提供或確認材料時，唔可以寫成「證據不存在」。可爭辯嘅 honest-performance claim 要建立喺正面陳述、明知誤導、合約直接連繫及後果；拒絕交代只係背景同 discovery 需要，唔係 knowledge 嘅替代品。

### Round 34（2026-10-07）— Separate digital content, authenticity, attribution and evidentiary weight

- 數碼指控研究要拆成四層：①畫面顯示嘅內容；②畫面及時間資料嘅真實、完整性；③相關日期由邊個控制帳號／號碼／裝置；④將全部證據衡量後嘅重量。見到 screenshot 唔可以跳過中間兩層直接寫作者已證明。
- `Balance of probabilities` 係最後衡量證據嘅標準，唔係一件新證據；但亦唔可以誤寫成一定要有 metadata 或獨立 corroboration。`McDougall` 確認可信證供有時可以單獨足夠，判斷要睇全部證據、矛盾、可信性同可靠性。
- 對外文字用「至今未被指出或提供歸屬鏈」，唔寫「冇證據存在」；亦唔寫「screenshot 完全冇證據價值」。最有效係逐項問邊個 file、完整 identifier、日期、來源、核實人、credibility assessment 同實際 decision use。
- 後來出現材料要分兩個時間問題：材料能否證明事件實際發生，以及決策人在原 finding 當日實際知道或審閱過乜。後來材料未必補得返原調查／誠實履約問題，但 `Golob` 顯示佢仍可能影響 after-acquired cause。

### Round 35（2026-10-07）— PIPA investigation-record access：由 blanket conclusion 回到逐項資料

- 先分清「機構拒絕 access 並採取一個法律立場」同「機構違抗已發出嘅 OIPC order」。未有 order 時，`we complied` 只係被覆核嘅結論；order 發出後，PIPA s. 53 先控制 30 日 compliance、judicial review 同 stay。
- PIPA s. 23 係 information-level 分析，唔係用 document label 決定。調查檔案可能同時包含申請人 personal information、第三者 personal information、source identity、privileged material、contact information 同 work product information；要逐部分判斷，並依 s. 23(5) sever 可披露部分。
- `work product information` 唔會將調查員工作時收集嘅所有資料一概排除。P23-06、P24-01 同 P26-11 均確認：針對申請人嘅 statements、allegations、行為詳情、他人對申請人嘅想法，以及討論申請人嘅電郵，可以係申請人 personal information；重點係資料係咪 about 申請人，以及申請人有冇準備／收集該資料。
- 公司可合理爭辯 s. 23(1)(b) 無要求另行創造一張 file-to-finding evidence map；因此申請應鎖定現有 underlying、attribution、verification 同 analysis records 入面關於申請人嘅 personal information，以及該 personal information 實際 ways of use。
- ss. 28／30 要機構合理協助、盡合理可能準確完整回覆，並就每項拒絕講明 reasons 同 exact provision。P26-11 顯示一句「已經提供 responsive records」取代唔到清楚標示被扣起資料、法例條文同理由。
- inquiry 時，s. 51 將 no-access burden 放喺機構；s. 38 俾 Commissioner 私下取得及檢查爭議紀錄。研究結論必須保留真正未知：未睇 underlying records 前，無法逐頁裁定披露範圍，但亦唔可以接受機構以 blanket conclusion 代替 record-specific analysis。

### Round 36（2026-10-07）— Corporate escalation timing：知情層級、notice價值同僱傭風險

- Corporate knowledge要分四層：①direct recipient／signatory；②因職責而合理可能知道；③公司governance文件所寫嘅一般reporting route；④實際向CEO／Board formal notice。CHRO經手個案證明executive HR知情，唔自動證明CEO或任何director睇過。
- email archive「無CEO／director header hit」只支持目前外部紀錄無直接notice；公司內部forward、Legal briefing同Board material仍然係unknown，唔可以由0 hit推成從未發生。
- 拒絕披露可以同litigation-risk control一致，但動機仍要有文件先可以寫成事實。較準確係列出可共存解釋，再用後續內部文件、OIPC production或civil discovery驗證。
- 高層升級同時有兩個相反效果：建立notice並提高其後報復／不利行動嘅證據風險；亦會令事件立即進入Legal、defence同employment-decision層。法定／policy non-retaliation係禁止理由及事後remedy，唔係自動凍結termination power。
- 當員工第一目標係維持僱用，而CHRO／DPO已知、外部程序已啟動、暫無新adverse action，完整CEO／Board package宜trigger-based hold。以termination、PIP、新discipline、bonus／performance reliance、重大職責變動或新一輪同模式指控作客觀release trigger，比純粹再追舊finding更有證據力。
- CHRO出具含termination警告嘅正式紀律文件後，唔應將hold理由寫成「避免提醒公司可以解僱」；termination option早已進入file。要分清公司一般／持續評估終止方案嘅合理風險假設，同已有時間表、批准或具體步驟嘅active termination plan。升級策略加入pre-decision triggers：突發HR／Legal meeting、全面交接、權限移除、新performance paper trail、PIP／show-cause、severance／release等；目標係預防時，唔機械式等正式termination先升級。

### Round 37（2026-10-08）— AI detector evaluation needs a frozen pre-AI human control

- 單篇待測文字跑多個 detector 只顯示跨工具分歧，不能直接暴露 false positive。加入一篇作者、年份及全文來源可核實、生成式 AI 出現前已出版的 human control；固定連續完整段落、長度、SHA-256、word counter、提交範圍和每個服務的 evidence screenshot／raw response。
- 同一固定 control 要交畀同一 detector panel，並用同一表格並排比較待測文本；服務 tokenizer、免費長度上限、model version、sensitivity 及 failed access 要分開記。FAILED 不等於 pass。
- 本輪 Jonathan Swift 1729 *A Modest Proposal* control（463 words）在 Grammarly、GPTZero、Copyleaks、Pangram、Scribbr、Sapling 均獲 0% AI 或 100% human，但 ZeroGPT 回 56.2% AI／260 AI words，直接證明有效 API response 仍可對已知人類文本產生 false positive。
- `n=1` control 只可作 document-level counterexample，不可估計 false-positive rate、confidence interval 或 significance。著名舊文可能已在訓練／reference data 出現；後續完整 benchmark 應再加入同 genre、同長度、較少見且 provenance 清楚的多篇 controls。

### Round 38（2026-10-08）— Company-to-school research needs three denominator layers

- 公開 LinkedIn Talent Insights Company Report 分析有時可由搜尋引擎 mirror 發現，但 evidence record 要保留 canonical LinkedIn article、報告月份、location、current/past-employer 狀態、title/function/skill filters。同一間公司用不同 filter 得到嘅 headcount、school count 同 hires 不可直接合併。
- Company Report 嘅 Education tab 能提供 school、recent graduates、highest degree 同 field of study；Talent Flow／Overview 可補 hires、departures、attrition 同 job posts。呢啲係 LinkedIn profile aggregates，唔係畢業班就業率，亦冇 applicant 或校友總數 denominator。
- 選校判斷要疊三層：① company × school aggregate 睇 target-employer visibility；②校方 first-destination report 睇 cohort、response/knowledge rate、employment、further study、salary 同 named employers；③行政資料如 U.S. Census PSEO 睇同 cohort、同定義嘅 earnings／industry cross-check。三層互相校準，唔將 logo list 當 placement rate。
- PSEO 只包括 partner institutions；earnings 係 2023 dollars、attached workers、用 differential privacy，status 5 cells 要標 suppressed。學校不在資料集係 unavailable，唔係零 outcome。
- 官方 PDF 或 Tableau landing page 被 403／404／dynamic embed 擋住，要記 `FAILED/UNAVAILABLE`、HTTP 狀態同已讀到嘅官方 index metadata；不可因 direct file 失敗就寫成學校冇數，亦不可用過時 PDF 冒充 current static outcome。

### Round 39（2026-10-08）— Hidden-gem university search must separate outcome, access and aid

- 選校 hidden-gem scan 先用 current administrative data 作盲篩選，再先睇校名：同一 credential、CIP、measurement year、valid status 同最小樣本門檻。之後先加入 admission route、transfer-credit ceiling、residency、international aid 同實際淨成本，避免 prestige prompt 決定候選池。
- 每個結果要分三類：① `career gem`＝就業／收入強；② `application gem`＝Nicole 合資格、資助可行而出路亦合理；③ `trap`＝表面 outcome 強，但 route-specific aid 或 eligibility 令佢實際不可行。Career gem 唔自動升格為 application gem。
- 成人／nontraditional program 嘅專屬 aid 可以完全推翻學校一般 international-aid statement。一定要開到 exact route 頁：例如 general international applicants 可獲 full need，唔代表 REAL／GS／continuing-education route 同樣有 aid；route-specific 「no aid」優先。
- College Scorecard field earnings只涵蓋 Title-IV-aided completers，並排除 measurement-year students、死亡者及非工作者；小型 liberal-arts college CS cells 常見 n 細或 suppressed。每個 median 必須連 n 一齊報，`n < 100` 標 descriptive/fragile，唔做顯著性或因果判斷；可再用 PSEO 或校方 first-destination 作獨立 cross-check，但唔合併不同 cohort／定義。
- consortium／cross-registration 係小校 hidden gem 嘅實質資產，但要讀限制：每學期上限、home-school minimum load、host capacity／permission、課程能否計入 major，以及交通。寫「有 access」唔等於保證入到指定 MIT／UMass／Amherst 課。

### Round 40（2026-10-13）— Claude startup credits：direct cohort 同 partner allocation 要分開

- Anthropic 於 2026-10-06 公布嘅 direct Claude Startups cohort，原本接受成立五年內或近兩年有募資嘅 startup；bootstrapped 公司亦可申請。當期主要 Anthropic benefits 係 US$1,000 first-party API credits，同符合條件嘅新 Team 客戶一年最多五個 Premium seats。呢條唔係 Amii 嘅 US$30,000 route，亦唔係 VC partner 嘅最高 US$100,000 route。
- 2026-10-13 官方 launch article 加咗 update：current cohort full，暫停接受新申請。研究任何限時 startup offer 必須同日重開 official program page 同 launch article；搜尋引擎快取仍可能顯示 `Apply today`，不可當 live availability。
- Amii 係獨立 partner route：active ML Exploration 或 Level Up participants `may be eligible` for up to US$30,000 Claude API credits。ML Exploration 仍有自己嘅加拿大、software-product、revenue、time-commitment 同 cohort deadline；入選課程同獲批 credits 都不可混寫成自動結果。
- Founder success story 只證明該申請人自述獲批。比較 eligibility 同 competitiveness 時要拆開：法定／公開門檻、market traction、Claude integration、可驗證 prototype、funding、domain identity、以及申請當日 cohort capacity。`Bootstrapped` 唔等於 `no traction`；本輪 nuva 案例自述零外部募資，但同時列出大量 learners、paying learners、企業客戶及社群分發，因此唔可用佢推論 pre-revenue startup 必然獲批。

### Round 41（2026-10-13）— Diaspora forums 改用 first-party browser-session APIs

- 1Point3Acres 已實測 browser-session API：`user.me` 認證、`search.search` cursor 搜尋、thread API 主文、top-level 同 nested replies 均 HTTP 200。本輪查詢 `加拿大 找工 2026` 返回 2026 年討論；thread 1192114 主文顯示 22 replies，adapter 載入 4 個 top-level 及合計 22 個 reply nodes。
- 原則改為 API-first：請求在 Agent Chrome 原頁面執行，browser 自行攜帶 session/cookies/TLS context；不 export credential，不用 DOM 全頁 crawler。Pagination 串行且至少相隔 300 ms。
- Grapevine first-party API 已實測：post search、single-post feed 及 comments 均 HTTP 200；`software engineer` 搜尋返回對題帖子，指定 post 載入 2/2 comments。公開 post 同時透過 Next/RSC 載入。Blind 公開 post/channel 主要使用 Next/RSC server payload。兩者應先讀 API/RSC network data，只在結構化 route 不可用時才作有限 DOM fallback。
- Indian tech community 需分功能組合：Grapevine/Blind India/r/developersIndia 讀 workplace；TakeUForward/LeetCode Discuss/AmbitionBox 讀面經；Yocket/Indian Academia/Indians Study Abroad 讀留學；RedBus2US Discourse JSON 讀 diaspora immigration。Trackitt 本輪從當前環境連線失敗，只能列 `FAILED/conditional`，不可當 core working source。
- 1P3A 同 Indian 匿名 forum 皆為自選樣本。它們可支持「有這種經驗／這種說法」，不能單獨支持母體比例、整體市場率或法律規則。

### Round 42（2026-10-13）— 1Point3Acres 定位為圈內人資源庫

- 1Point3Acres coverage 擴闊為北美華人跨領域 community resource library：除求職／面經，亦包括學校與 admission、transfer／prerequisite／學分對應、選課、教授、course code、syllabus、assignment、past paper／真題／回憶題、附件、簽證、住房與生活流程。
- 搜尋必須按 query family 分開跑再去重。實測 hybrid query `UBC 选课 教授 真题 往年题` 混入 admission、面經同公開課；之後禁止以一條混合 query 代替學校、course、教授、試卷與附件的獨立檢索。
- 命中 thread 後要讀完整主文、replies 同 attachment metadata，核對年份、教授和 course version。附件失效記為 `FAILED/UNAVAILABLE`，不可當成「冇資源」。現行要求仍回查學校或政府 primary source。
- 印度社群冇單一網站完整複製 1P3A；resource routing 改為組合：University Updates／Education Observer／各校社群處理院校與 course 資料，GATEOverflow／Doc Sansar 處理 PYQ／試題／notes，PaGaLGuY 處理 MBA admission/exams；另保留既有 workplace、interview、study-abroad 與 immigration stack。

### Round 43（2026-10-13）— Rare-admissions source lane（topic-specific）

- 加入升學題目可選用嘅 source lane；核心係 non-traditional／interrupted-education／refugee／international-transfer 等極窄 routes，而唔係一般 ranking 或泛選校。呢條 lane 唔係 general engine 嘅預設。
- 新增八條 evidence lanes：eligibility、academic basis、documents/exceptions、selection reality、comparable people、funding、academic fit、immigration/life。每條獨立搜尋，再交叉核對。
- Rare program search 加入 exact/old names、adjacent programs、year-by-year cohort threads、reapplication、adverse terms、student/alumni people trail、school newspaper、official podcast、archived pages、Common Data Set、FOI/ATI 同 contact map。三輪跨 source-type expansion 冇新材料先可判定 saturation。
- 1Point3Acres、Reddit、College Confidential、The Student Room 等用來挖長尾個案與 timeline；公開規則、waiver authority、funding 同 immigration 結論仍以學校或政府 primary source 為準。Grapevine／Blind 繼續保留作 career/outcome 補充。

### Round 44（2026-10-13）— General source phonebook，LLM 揀 source

- Research engine 收斂成一條簡單 loop：問題 → LLM 提議可能有料嘅 source → Nicole 加／刪 → 讀 access recipe／credential reference → 登入後用 first-party API search → 報告證據同 source ledger。
- `community-sources.json` 係 machine-readable 黃頁，唔做 hard classification、ranking 或排除。Cluster 只係方便 LLM 記得 source；一條問題可以跨任何類別，亦可以試一個未肯定有冇該話題嘅網站。
- 每次 research 開始前列 proposed 同 unused/optional sources，保留 human in the loop；完成後列實際 `USED／UNUSED／EMPTY／FAILED／SKIPPED`。
- 新增 College Confidential public Discourse JSON、The Student Room public thread browser route、BC Transfer Guide official public API adapters；連同既有 Reddit、1Point3Acres、Grapevine、Blind、Xiaohongshu routes 記入電話簿。
- Account 只喺 public route 唔夠而且 gated evidence 真係有獨特價值時先開。Secret 放 gopass 或既有 browser session；Git registry 只放 reference，唔放 credential value。
