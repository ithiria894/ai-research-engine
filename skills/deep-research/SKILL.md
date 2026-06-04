---
name: deep-research
description: Unified entry point for ANY search — deep research, buying a product / finding a gift (Shopping mode), product competitive analysis, AI-security tracking, academic papers, news, social/forum discussion, crypto, gov/legal data. Auto-detects mode + routes the query to the right research-engine cluster. Use for any "find me / research / compare / where to buy / what to gift / what are people saying about X" task.
argument-hint: "<research question, topic, or product name>"
allowed-tools: [Bash, Read, Write, WebSearch, WebFetch, Agent, mcp__tavily__tavily_search, mcp__tavily__tavily_extract, mcp__tavily__tavily_research, mcp__tavily__tavily_crawl, mcp__tavily__tavily_map, mcp__exa__web_search_exa, mcp__exa__get_code_context_exa, mcp__exa__crawling_exa, mcp__firecrawl__firecrawl_search, mcp__firecrawl__firecrawl_scrape, mcp__firecrawl__firecrawl_crawl, mcp__firecrawl__firecrawl_map, mcp__newsmcp__get_news, mcp__newsmcp__get_topics, mcp__rss-reader__fetch_feed_entries, mcp__rss-reader__fetch_article_content, mcp__devto__get_articles, mcp__twitter__search_tweets, mcp__twitter__search_users, mcp__context7__query-docs, mcp__context7__resolve-library-id, mcp__paper-search__*, mcp__arxiv__*, mcp__semantic-scholar__*, mcp__scholar-mcp__*, mcp__youtube-transcript__*, mcp__open-websearch__*, mcp__paper-distill__*, mcp__superprecio__*, mcp__apify__*, mcp__dialog-mcp__*, mcp__chrome-devtools__*, mcp__gmail__*, mcp__teams__*, mcp__reddit__*, mcp__discourse__*, mcp__hackernews__*, mcp__stackoverflow__*, mcp__xiaohongshu__*, mcp__trend-pulse__*, mcp__activitypub__*, mcp__weibo__*, mcp__ptt__*, mcp__zhihu__*]
---

# Research — Unified Deep Research + Product Analysis

## Configuration (edit these paths for your setup)

```
RESEARCH_ENGINE = ~/MyGithub/ai-research-engine/research-engine.md
PRODUCT_SPECS   = ~/MyGithub/agentic-journal/projects/products/
PRODUCTS_INDEX  = ~/MyGithub/agentic-journal/projects/OVERVIEW.md
OUTPUT_DIR      = ~/MyGithub/agentic-journal/projects/1-think/research/
```

**ALWAYS read `RESEARCH_ENGINE` FIRST** for the full tool inventory, cost rules, and Quota Classification.

## Step -1: Official Docs Pre-check (MANDATORY, before Mode Detection)

If the user's question is about **an existing tool, product, or platform they already use** (e.g., "how to get better UI for Claude Code", "does X support Y", "alternatives to X for doing Y"):

1. **Read the tool's official documentation FIRST** — use WebFetch on the official docs site, or `context7`, or the tool's own `--help` / built-in commands
2. **Check session context** — system reminders, startup messages, and existing config may already contain the answer
3. **If the docs answer the question** → reply directly. Do NOT launch research agents. Done.
4. **If the docs confirm the feature doesn't exist** → proceed to Mode Detection below, but note what you already ruled out so agents don't waste time re-searching the same ground

**Why this exists:** In April 2026, user asked for a better Claude Code UI. The answer was `/remote-control` + `claude.ai/code` (built-in features, mentioned in the session's own startup message). Instead, 4 research agents were launched, 3 third-party tools were installed and all failed (wrong glibc, needed API key, required registration). 30+ minutes wasted. Official docs would have answered it in 2 minutes.

**Rule: never search for alternatives to X without first knowing what X can do.**

---

## Mode Detection — 統一入口（route ANY search here）

> 呢個 skill 係**所有 search 嘅統一入口**：研究主題、買產品、送禮、追 AI security、查 crypto、搵 paper、睇社群最近傾乜… 全部入呢度，auto-route。

**Step A — 揀 MODE（睇用戶意圖）：**

**🛍️ Shopping / Buy Mode** — 用戶想**買嘢 / 送禮 / 格價**：
- Input 有「buy」「邊度買」「price」「格價」「cheapest」「gift」「送禮」「禮物」「recommend a [product] under $X」「best [product] for…」
- → Go to [Shopping Mode Workflow](#shopping-mode-workflow)

**📊 Product (Competitive) Mode** — 分析一個產品/idea 嘅競爭格局（**唔係買**）：
- Input matches a product name in `PRODUCT_SPECS`；或有「competitive」「market」「SWOT」「positioning」「vs」「alternative to」「compare」「product idea」；或 `--product`
- → Go to [Product Mode Workflow](#product-mode-workflow)

**🔬 General Mode** — 其餘所有 research question：
- → Go to [General Mode Workflow](#general-mode-workflow)

**Step B — CLUSTER ROUTER（揀啱 source，唔好乜都 web search）：**

讀 `RESEARCH_ENGINE`，按 query 主題 route 去對應 cluster 嘅 source（mind map 17 個 domain）。揀 1-3 個最啱嘅 cluster，淨係用嗰啲 source：

| Query 關於… | Cluster → 用邊啲 source |
|---|---|
| 買嘢/送禮/格價 | 🛍️ Shopping：Serper Shopping · Apify · superprecio · **Reddit（dialog-mcp `discover_subreddits` 按產品品類搵 sub**，e.g. 廚具→r/cookware，唔係淨係 gift sub） |
| 學術/論文/研究 | 📚 Academic：arXiv·OpenAlex·S2·OpenReview + paper-search/arxiv MCP |
| 新聞/時事 | 📰 News：GDELT·newsmcp·google-trends·rss-reader |
| 社群最近傾乜 | 💬 Social：dialog-mcp(Reddit)·HN·Bluesky·Mastodon·Lemmy·arctic-shift·last30days |
| dev/package | 📦 Dev：npm·PyPI·HuggingFace·libraries.io·GitHub GraphQL |
| 政府/經濟/法律 | 🏛️⚖️ Gov/Legal：FRED✅·Census✅·OpenStates✅·CourtListener·Congress |
| 公司/金融/制裁 | 🏢 Company：SEC·FMP✅·OpenSanctions✅·Finnhub |
| AI security/safety | 🛡️ AI-Sec：Simon Willison·Embrace The Red·tldr;sec·LessWrong GraphQL·arXiv cs.CR |
| crypto/區塊鏈 | ⛓️ Chain：DeFiLlama·DexScreener·Dune·Polymarket·CoinGecko |
| LLM/model/benchmark | 🧬 AI-meta：OpenRouter·Ollama·leaderboards |
| domain/SEO/web infra | 🔍 SEO：OpenPageRank✅·Serper·Tranco·Wayback·Common Crawl |
| 科學/健康/化學 | 🔬 Science：ClinicalTrials·PubChem·GBIF·openFDA·WHO |
| **韓國醫美/整容/疤痕修復** | 🏥 K-Beauty Med：見下方「韓國醫美 Research Cluster」 |

> ✅ = 已有 API key（存 `~/.config/research-engine/keys.env`，`source` 佢再 curl）。跑前可 `bash ~/MyGithub/ai-research-engine/health-check.sh` 確認 source 生死。

---

## Agent Model Selection

**🚨 Default: launch ALL research agents with `model: "opus"`.** (Nicole's standing rule, 2026-05-30.)

The research-engine philosophy is **資料質素 > token 成本** — "token cost is not the concern, data quality is". A research agent that mis-reads a source, gives up early, or fails to chain tools wastes the whole run no matter how cheap it was. Opus agents collect more thoroughly, recover from tool errors better, and notice when a source returned nothing (instead of silently reporting "found nothing"). That reliability is worth more than the token saving.

- **Opus** — DEFAULT for every collect/search/extract agent. Use unless the user explicitly says to save tokens.
- **Sonnet / Haiku** — only if the user explicitly opts into cheaper models for a trivial single-source lookup. Not the default.

The pattern: **Opus collects → Opus (main thread) synthesizes.** Agents bring back raw data + citations; the main thread does cross-referencing, gap analysis, and final judgment.

---

## 韓國醫美 Research Cluster（🏥 K-Beauty Med）

整容、疤痕修復、醫美 research 專用。韓國係全球整容首都，資訊最集中喺韓文平台。

### Source 優先順序

#### Tier 1: Naver API（已有，25K/日）
最重要嘅 source。韓國人嘅真實後記 90% 喺 Naver 生態圈。
```bash
# Blog 後記（最多真人分享）
curl -s "https://openapi.naver.com/v1/search/blog.json?query=QUERY_ENCODED&display=10&sort=sim" \
  -H "X-Naver-Client-Id: $NAVER_CLIENT_ID" -H "X-Naver-Client-Secret: $NAVER_CLIENT_SECRET"

# Cafe 社群討論（여우야/퍼플영/재잘재잘/가아사 = 韓國最大整容 Cafe）
curl -s "https://openapi.naver.com/v1/search/cafearticle.json?query=QUERY_ENCODED&display=10&sort=sim" \
  -H "X-Naver-Client-Id: $NAVER_CLIENT_ID" -H "X-Naver-Client-Secret: $NAVER_CLIENT_SECRET"

# 知識iN Q&A（專科醫生答問）
curl -s "https://openapi.naver.com/v1/search/kin.json?query=QUERY_ENCODED&display=10&sort=sim" \
  -H "X-Naver-Client-Id: $NAVER_CLIENT_ID" -H "X-Naver-Client-Secret: $NAVER_CLIENT_SECRET"

# 地區搜索（搵診所地址/電話）
curl -s "https://openapi.naver.com/v1/search/local.json?query=QUERY_ENCODED&display=5&sort=comment" \
  -H "X-Naver-Client-Id: $NAVER_CLIENT_ID" -H "X-Naver-Client-Secret: $NAVER_CLIENT_SECRET"

# DataLab 趨勢（追蹤整容趨勢）
curl -s -X POST "https://openapi.naver.com/v1/datalab/search" \
  -H "X-Naver-Client-Id: $NAVER_CLIENT_ID" -H "X-Naver-Client-Secret: $NAVER_CLIENT_SECRET" \
  -H "Content-Type: application/json" -d '{"startDate":"2024-01-01","endDate":"2026-06-01","timeUnit":"month","keywordGroups":[...]}'
```

**⚠️ 永遠唔好用 Chrome DevTools / Playwright 操作 Naver 網站 — 即時永久封號**

#### Tier 2: 韓國整容 App 平台（web search 搵佢哋嘅內容）
呢啲平台冇 public API，但佢哋嘅內容可以通過 web search 搵到。

| 平台 | URL | 內容 | 點搵 |
|------|-----|------|------|
| **강남언니 (Gangnam Unni)** | gangnamunni.com | 最大整容 review（10K+ 後記/診所）、醫生 profile、價錢 | `site:gangnamunni.com QUERY` via Tavily/Exa |
| **여신티켓 (YeoTI)** | yeoshin.co.kr | 醫生驗證、手術價錢、學會資格 | `site:yeoshin.co.kr QUERY` |
| **바비톡 (BabiTalk)** | babitalk.com | 手術後記 + before/after | `site:babitalk.com QUERY` |
| **성예사 (SungYeSa)** | sungyesa.com | 醫生評分 + 닥터찾아삼만리（醫生搜索） | `site:sungyesa.com QUERY` |
| **모두닥 (Modoodoc)** | modoodoc.com | 醫療 review + 認證後記 + 價錢比較 | `site:modoodoc.com QUERY` |

#### Tier 3: 其他韓文論壇
| 平台 | 內容 | 點搵 |
|------|------|------|
| **DC Inside 성형갤러리** | 匿名討論（最真實但最毒舌） | `site:dcinside.com 성형 QUERY` |
| **뽐뿌 (Ppomppu)** | 格價 + review | `site:ppomppu.co.kr QUERY` |

#### Tier 4: 中文/台灣/國際
| 平台 | 內容 | 點搵 |
|------|------|------|
| **Dcard 醫美板** | 台灣人去韓國整容後記 | `site:dcard.tw 醫美 韓國 QUERY` |
| **小紅書** | 中國人去韓國整容後記 | Chrome DevTools 搜索 / RedNote MCP |
| **RealSelf** | 英文 review + 國際患者經驗 | `site:realself.com korea QUERY` |

### 常用韓文搜索詞

| 中文 | 韓文 | 用途 |
|------|------|------|
| 鼻翼縮小 | 콧볼축소 / 코날개축소 | 搜手術後記 |
| 外切 | 외절개 | 指定切口方式 |
| 內切 | 내절개 / 비절개 | 對比方式 |
| 疤痕 | 흉터 | 搜疤痕相關 |
| 疤痕修復 | 흉터수정 / 흉터교정 | 搜修復手術 |
| 後記 | 후기 | 真人分享 |
| 副作用 | 부작용 | 搜負面 |
| 失敗 | 실패 | 搜失敗案例 |
| 再手術 | 재수술 | 修復/重做 |
| 推薦 | 추천 | 搜推薦 |
| 醫生 | 원장 / 의사 | 搜醫生 |
| 整形外科 | 성형외과 | 搜診所 |
| 費用 | 비용 / 가격 | 搜價錢 |
| 諮詢 | 상담 | 搜諮詢經驗 |
| 恢復期 | 회복기간 / 다운타임 | 搜恢復時間 |
| 自然 | 자연스러운 | 搜自然效果 |

### 醫生驗證 Checklist

搵到候選醫生後，逐個 verify：
1. `site:sungyesa.com 醫生名` → 닥터찾아삼만리 profile（學歷/經歷/學會）
2. `site:gangnamunni.com/doctors 醫生名` → 後記數 + 評分
3. `site:yeoshin.co.kr/doctors 醫生名` → 學會驗證
4. Naver Blog 搜「醫生名 후기」→ 真人後記
5. Naver Blog 搜「醫生名 부작용 실패」→ 負面搜索
6. `site:dcinside.com 醫生名` → 匿名真話（DC Inside 最毒舌但最真）

### Nicole 嘅 Case: 疤痕修復 + 鼻翼微調

**背景：** 細個整親鼻翼留低疤痕，拉扯到鼻翼高低唔平衡。唔係大整容，係修復 + 微調對稱。
**需求：** reconstructive（疤痕修復）> cosmetic（美容）。外切。
**Tracker：** `~/MyGithub/PersonalDoc/trackers/健康-醫療.md` → 「修補疤痕 + 縮鼻翼」section

---

## Tools Catalog

Launch as many searches as possible simultaneously. Don't do them one by one.

### Web Search (use ALL of these)
```
mcp__tavily__tavily_search — LLM-optimized search (best for factual queries)
mcp__exa__web_search_exa — semantic search (best for "find pages similar to X")
mcp__open-websearch__* — 8 engines (Bing/Baidu/DDG/Brave/Exa/GitHub/Juejin/CSDN), zero API keys
mcp__firecrawl__firecrawl_search — another web search source
WebSearch — built-in web search
```

### Content Extraction (when you find a good URL)
```
mcp__tavily__tavily_extract — extract clean content from URLs
mcp__exa__crawling_exa — crawl and extract from URLs
mcp__firecrawl__firecrawl_scrape — scrape single page
mcp__rss-reader__fetch_article_content — extract article text
```

### Platform-Specific
```
mcp__devto__get_articles — Dev.to articles by tag/keyword
mcp__twitter__search_tweets — Twitter/X discussions
mcp__newsmcp__get_news — real-time news clusters
mcp__rss-reader__fetch_feed_entries — RSS feeds (Simon Willison, HN, etc.)
gh search issues/repos — GitHub ecosystem data
```

### Discussion Forums & Communities (use the Forum Deep Dive Agent for these)

Every forum below has a concrete curl command — agents MUST use these, not just web search.

#### Tier 1: Zero Auth, Always Available (🟢 FREE curl)
```bash
# Hacker News — full-text search all history (Algolia, zero key, generous limits)
curl "https://hn.algolia.com/api/v1/search?query=TOPIC&tags=story"
curl "https://hn.algolia.com/api/v1/search?query=TOPIC&tags=comment"
# Filter: 30 days, 10+ points
curl "https://hn.algolia.com/api/v1/search?query=TOPIC&tags=story&numericFilters=created_at_i>$(date -d '30 days ago' +%s),points>10"

# Lobste.rs — append .json (zero key, zero auth)
curl "https://lobste.rs/search.json?q=TOPIC&what=stories&order=relevance"
curl "https://lobste.rs/hottest.json"

# Bluesky — public search API (zero auth, generous limits)
curl "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=TOPIC&limit=25"
# With date range:
curl "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=TOPIC&since=2025-01-01T00:00:00Z"

# Mastodon — public search (zero auth on most instances)
curl "https://mastodon.social/api/v2/search?q=TOPIC&type=statuses&limit=20"
curl "https://mastodon.social/api/v1/trends/statuses"
# Other instances: hachyderm.io, infosec.exchange, fosstodon.org

# Lemmy — REST API (zero auth for reads)
curl "https://lemmy.world/api/v3/search?q=TOPIC&type_=Posts&sort=TopMonth&limit=20"
# Other instances: lemmy.ml, beehaw.org, sh.itjust.works

# StackExchange — 170+ sites (zero key = 300/day, free key = 10K/day)
curl -s --compressed "https://api.stackexchange.com/2.3/search/excerpts?order=desc&sort=relevance&q=TOPIC&site=stackoverflow"
# Change site= for different communities:
#   health, beauty, cooking, fitness, skeptics, biology, parenting, diy, etc.

# DEV.to — public articles (zero auth)
curl "https://dev.to/api/articles?tag=TOPIC&per_page=30"

# Reddit — ⛔ DO NOT use raw curl .json (returns 403 from most environments + surface-only).
#   Use dialog-mcp (reddit-research) OR the logged-in Chrome session instead.
#   See the HARD RULE in the Forum Deep Dive Agent Template below.
```

#### Tier 2: Asian Communities (🟡 cookie/逆向工程, higher signal for lifestyle/beauty/culture)
```bash
# === 中文 (Chinese) ===

# Bilibili 哔哩哔哩 (中國影片平台, 真人測評最多) — 🟢 免 login
curl -s "https://api.bilibili.com/x/web-interface/search/all/v2?keyword=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("TOPIC_ZH"))')&page=1" -H "User-Agent: Mozilla/5.0"
# 高信號：搵 "真实测评"、"翻车"、"半年后" 過濾廣告

# 百度貼吧 (中國論壇) — 🟢 免 login (mobile API 更穩定)
curl -s "https://tieba.baidu.com/mo/q/search/thread?word=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("TOPIC_ZH"))')&pn=0&rn=20" -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
# Desktop fallback:
curl "https://tieba.baidu.com/f/search/res?qw=TOPIC_ZH&ie=utf-8"

# V2EX (中國 Tech 論壇) — 🟢 免 login
curl -s "https://www.v2ex.com/api/topics/hot.json"
# Search via web: site:v2ex.com TOPIC

# Dcard (台灣, 18-30歲) — unofficial API, may break
curl "https://www.dcard.tw/service/api/v2/search/posts?query=TOPIC_ZH&limit=20"
curl "https://www.dcard.tw/service/api/v2/forums/FORUM_NAME/posts?popular=true&limit=30"
# Forums: makeup, skincare, mood, relationship, tech, movie

# PTT (台灣 BBS) — web version, needs over18 cookie
curl "https://www.ptt.cc/bbs/BOARD/index.html" -H "Cookie: over18=1"
# Boards: Beauty, MakeUp, e-shopping, Gossiping, Tech_Job

# LIHKG (香港連登) — needs x-li-device header (SHA1 UUID)
curl "https://lihkg.com/api_v2/thread/search?q=TOPIC_ZH&page=1&count=30" \
  -H "x-li-device: $(python3 -c 'import uuid,hashlib; print(hashlib.sha1(str(uuid.uuid4()).encode()).hexdigest())')" \
  -H "x-li-device-type: browser"

# === 日本語 (Japanese) ===

# 5ch (日本最大匿名論壇, 前2ch) — 🟢 免 login (Shift_JIS encoding)
curl -s "https://kizuna.5ch.net/cook/subject.txt" | iconv -f SHIFT_JIS -t UTF-8
# Board list: kizuna.5ch.net/cook (料理), egg.5ch.net/kaden (家電)

# Hatena Bookmark はてなブックマーク (日本 social bookmarking) — 🟢 免 login
curl -s "https://b.hatena.ne.jp/search/text?q=$(python3 -c 'import urllib.parse; print(urllib.parse.quote("TOPIC_JA"))')&sort=popular"
# Also: https://b.hatena.ne.jp/entry/jsonlite/?url=TARGET_URL

# Kakaku.com 価格.com (日本最大產品比較/評價網) — 🟢 via web search
# Use: site:review.kakaku.com TOPIC_JA (product reviews)
# Use: site:bbs.kakaku.com TOPIC_JA (user discussions)

# Amazon.co.jp reviews — via web search
# site:amazon.co.jp "TOPIC_JA" レビュー

# === 한국어 (Korean) ===

# Naver Blog/Cafe (韓國最大平台) — 🔑 需要免費 API key
# API: https://openapi.naver.com/v1/search/blog?query=TOPIC_KO (25K calls/day free)
# API: https://openapi.naver.com/v1/search/cafearticle?query=TOPIC_KO
# API: https://openapi.naver.com/v1/search/shop?query=TOPIC_KO (shopping reviews)
# Headers: X-Naver-Client-Id + X-Naver-Client-Secret (from developers.naver.com)

# DC Inside (韓國論壇, 似 Reddit) — 🟢 via web search
# site:dcinside.com TOPIC_KO

# Naver Shopping Reviews — via web search
# site:shopping.naver.com TOPIC_KO "후기" (reviews)
```

#### Tier 3: MCP Servers (📦 install for richer access)
```
mcp__reddit__*           — Reddit read/search (uvx reddit-no-auth-mcp-server OR npx -y reddit-mcp-buddy)
mcp__discourse__*        — Any Discourse forum (npx @discourse/mcp@latest) — official
mcp__hackernews__*       — HN stories/comments (npx mcp-server-hackernews)
mcp__stackoverflow__*    — Stack Overflow official (npx mcp-remote mcp.stackoverflow.com)
mcp__xiaohongshu__*      — 小紅書 notes/comments (needs XHS cookie) ⭐13.6K
mcp__zhihu__*            — 知乎 Q&A (needs cookie)
mcp__weibo__*            — 微博 feeds/hot search (uvx mcp-server-weibo, needs cookie)
mcp__ptt__*              — PTT BBS (Docker, needs PTT account)
mcp__activitypub__*      — Mastodon/Lemmy/Misskey/Pixelfed (npx @iflow-mcp/cameronrye-activitypub-mcp)
mcp__trend-pulse__*      — 37 sources: Reddit/HN/Mastodon/Bluesky/PTT/Dcard/Weibo/XHS (uvx trend-pulse, FREE)
```

#### Tier 4: Chrome CDP Fallback (for logged-in sessions)
```
When curl APIs fail or rate-limit, use Chrome DevTools MCP to browse forums
with the user's logged-in session. Best for:
- Reddit (when .json is rate-limited)
- 小紅書 (when cookie expires)
- LIHKG (when headers change)
- Any forum requiring login

Tools: mcp__chrome-devtools__navigate_page, evaluate_script, take_snapshot, click, fill, press_key
```

#### Forum Selection Guide (which forums for which topics)
```
Tech/Programming    → HN, Lobste.rs, StackExchange, Reddit r/programming, DEV.to, Discourse (OSS)
Beauty/Skincare     → Reddit r/SkincareAddiction r/AsianBeauty, 小紅書, Dcard 美妝, PTT MakeUp/Beauty
Health/Medical      → StackExchange Health, Reddit r/AskDocs, 知乎 醫學, acne.org (web scrape)
HK/Cantonese        → LIHKG, Reddit r/HongKong
Taiwan              → PTT, Dcard, 巴哈姆特 (web only)
China Mainland      → 知乎, 微博, 百度貼吧, 小紅書
Finance/Investing   → Reddit r/investing, LIHKG 財經台, PTT Stock, Lemmy
Gaming              → Reddit, 巴哈姆特, Discord (via MCP)
Startups/Products   → HN, Product Hunt, IndieHackers (web scrape)
Science/Academic    → StackExchange (multiple sites), Reddit r/askscience
```

### Technical/Code
```
mcp__context7__query-docs — latest library documentation
mcp__exa__get_code_context_exa — code examples and docs (82.8% completeness vs 59.8% for WebFetch)
```

### Academic Papers (use ALL for comprehensive literature search)
```
mcp__paper-search__* — search 20+ academic platforms (arXiv, S2, OpenAlex, Crossref, CORE, dblp, DOAJ, Zenodo) ⭐919
mcp__arxiv__* — arXiv semantic search + citation analysis + trend analysis ⭐2.4K
mcp__semantic-scholar__* — Full S2 API: citation networks, recommendations, batch ops
mcp__scholar-mcp__* — ~97% peer-reviewed coverage, 6 sources, download + READ paper PDFs ⭐NEW
mcp__paper-distill__* — 11-source parallel academic search with weighted ranking ⭐53
```

### Academic Papers — Worth Installing (not yet installed, need Python ≥3.12 or clone)
```
academia_mcp — ArXiv + ACL Anthology + HF Datasets + Semantic Scholar ⭐78 (needs Python ≥3.12)
openalex-mcp — 250M papers via free OpenAlex API ⭐15 (needs git clone)
PaperMCP — ArXiv/HF/Google Scholar/OpenReview/DBLP/PapersWithCode, 32 tools (github.com/ScienceAIHub/PaperMCP)
research-paper-mcp — autonomous arXiv + S2 ingestion, memory storage (playbooks.com/mcp/marc-shade/research-paper-mcp)
```

### Video/Transcript
```
mcp__youtube-transcript__* — YouTube video transcripts + metadata (free, no key)
```

### Prediction Markets (Round 9)
```
Polymarket Gamma API — real-money outcome predictions (free, zero key, zero limit)
  curl "https://gamma-api.polymarket.com/markets?tag=ai&closed=false"
  When to use: trend-sensitive topics, elections, geopolitics, tech launches, crypto
  Polymarket odds are among the highest-signal data — real money > opinion
```

### Blockchain & On-chain Data (Round 10)
```
# All blockchain activity is public. Use these for crypto/DeFi/NFT research,
# wallet & token analytics, smart-money / insider tracking, DEX flows, prediction markets.

## Price / market / TVL (zero key)
DeFiLlama — TVL, yields, stablecoins, DEX volume, protocol revenue (free, zero key, zero limit)
  curl "https://api.llama.fi/protocols"  ·  curl "https://api.llama.fi/protocol/aave"
  curl "https://yields.llama.fi/pools"   ·  curl "https://stablecoins.llama.fi/stablecoins"
CoinGecko — 17K+ coins price/mcap/volume/history (free, zero key 5-15 req/min)
  curl "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc"
DexScreener — live DEX token pairs across all chains, price/liquidity/volume (free, zero key)
  curl "https://api.dexscreener.com/latest/dex/search?q=SYMBOL"
  curl "https://api.dexscreener.com/token-pairs/v1/{chain}/{tokenAddress}"
GeckoTerminal — DEX pools/OHLCV per chain (free, zero key)
  curl "https://api.geckoterminal.com/api/v2/networks/solana/pools?sort=h24_volume_usd_desc"

## Block explorers — txns, token transfers, balances, contract source (free key)
Etherscan V2 multichain — ONE key, 60+ EVM chains via chainid param (free key, 5 req/sec)
  curl "https://api.etherscan.io/v2/api?chainid=1&module=account&action=txlist&address=0x...&apikey=KEY"
  (chainid: 1=ETH, 137=Polygon, 8453=Base, 42161=Arbitrum, 56=BSC, 10=Optimism ...)
Solana — JSON-RPC (free public RPC) · Solscan API (free tier) for SPL token flows
  curl https://api.mainnet-beta.solana.com -d '{"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress","params":["ADDR",{"limit":20}]}'
mempool.space — Bitcoin txns/mempool/fees (free, zero key) · Blockchair — multi-chain explorer (free tier)

## Indexed / query layers (free tier, key)
Dune Analytics API — run SQL over decoded chain tables, fetch any public query result (free tier, key)
  curl -H "X-Dune-API-Key: KEY" "https://api.dune.com/api/v1/query/{query_id}/results"
The Graph — GraphQL subgraphs for protocol-specific entities (positions, PnL, holders)
  POST "https://gateway.thegraph.com/api/{key}/subgraphs/id/{subgraph_id}"  (Graph API key)
Bitquery — GraphQL on-chain incl. DEX trades, transfers, balances, 40+ chains (free tier, key)
Covalent/GoldRush · Moralis · Alchemy — unified multichain wallet/token/NFT APIs (free tier, key)

## Prediction markets — Polymarket full stack (zero auth)
Gamma API — market metadata: conditionId, clobTokenIds, outcomePrices, volume, resolution
  curl "https://gamma-api.polymarket.com/markets?closed=false&limit=10&order=volume&ascending=false"
Data API — PER-WALLET PnL precomputed (the key endpoint for smart-money work):
  curl "https://data-api.polymarket.com/positions?user=0xADDR&sortBy=CASHPNL&sortDirection=DESC"
    → realizedPnl, avgPrice, cashPnl, percentPnl per position
  curl "https://data-api.polymarket.com/trades?limit=100"  → proxyWallet, side, price, timestamp, txHash
  curl "https://data-api.polymarket.com/activity?user=0xADDR"  ·  /value?user=0xADDR (portfolio USD)
Leaderboard — curl "https://lb-api.polymarket.com/volume?window=all&limit=20" (volume confirmed)
Settlement = USDC on Polygon; CTF Exchange 0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e; UMA oracle resolves.

## Smart-money / insider labels (paid, but highest-signal)
Nansen ($49/mo Pro) — rule-based + clustered "Smart Money" labels, 30+ chains
Arkham — ML entity attribution/deanonymization + bounty marketplace · Lookonchain — whale alerts (free)
Solana copy-trade terminals: GMGN.ai / Photon / BullX (1% fee, 2-5s copy latency — research only)

# CAVEAT for synthesis: high wallet win-rate ≠ copier returns. Latency (4-14s on Polygon),
# slippage on thin markets, exit-liquidity trap, multi-wallet hedging, and fresh-wallet insiders
# all break naive copy-trading. Use binomial p-value (p<0.001) + 100+ trade gate to separate
# skill from luck; use funding-source clustering (not track record) to catch fresh-wallet insiders.
```

### Trend & Social Intelligence (Round 9)
```
trendsmcp — Google/YouTube/TikTok/Reddit/Amazon/npm/GitHub trends (100 free/mo)
social-trends-mcp — Reddit + HN trending (free, zero key)
google-trends-mcp — Google Trends wrapper (free)
Bluesky AT Protocol — api.bsky.app (free, near-zero rate limit)
Mastodon API — per-instance public timelines + trending (free, 300 req/5min)
Lobste.rs JSON — append .json to any URL (free)
Hashnode GraphQL — ⚠️ moved to PAID tier (2026-05-13), no free endpoint; needs a Hashnode PAT
Discourse API — {instance}/search.json (free, most instances zero auth)
StackExchange API — 170+ sites beyond SO (free key, 10K req/day)
Truth Social API — Mastodon-compatible, US political discourse (needs bearer token)
小紅書 (Xiaohongshu) — Chinese lifestyle/consumer platform (via xiaohongshu-mcp or ScrapeCreators)
```

### Package Registries & Dev Ecosystem (Round 9)
```
PyPI Stats API — pypistats.org/api/ (free, zero key)
crates.io API — Rust packages (free, zero key)
Packagist API — PHP packages (free, zero key)
RubyGems API — Ruby gems (free, zero key)
Homebrew Analytics — formulae.brew.sh/api/ (free, zero key, ZERO rate limit)
Docker Hub API — hub.docker.com/v2/ (free, total pull count only)
HuggingFace Hub API — AI/ML model trending (free, zero key)
libraries.io API — 40+ registries cross-analysis (free key, 60 req/min)
VS Code Marketplace — unofficial endpoint (free, zero key)
OSV.dev — open source vulnerability data (free, zero key)
```

### Citation & Academic Metrics (Round 9)
```
OpenCitations API — citation graph, DOI-to-DOI (free, zero key, 180 req/min)
NIH iCite API — field-normalized impact RCR metric (free, zero key)
ORCID API — researcher identity + publications (free, zero key)
ROR API — Research Organization Registry, 120K+ institutions (free, zero key)
OpenAIRE API — EU-funded research + datasets + software (free)
medRxiv API — health sciences preprints (free, zero key)
Altmetric API — social/news attention metrics (free for research)
```

### Patent & IP (Round 9)
```
USPTO PatentsView API — US patent search (free key, 45 req/min)
EPO OPS — European + WIPO + multi-country patents (free registration, 4 GB/week)
Lens.org API — 140M+ patents + scholarly citation cross-analysis (free for research)
```

### Government & Economic (Round 9)
```
FRED API — 840K+ economic time series (free key, 120 req/min)
BLS API — US employment/wages/CPI (free, v1 zero key 25/day, v2 free key 500/day)
Congress.gov API — US legislation (free key, 1000 req/hr)
Federal Register API — US regulations (free, zero key)
SEC EDGAR — US company filings (free, zero key, 10 req/sec)
UK Companies House — company directors/filings (free key, 600 req/5min)
World Bank API — 16K+ indicators, 200+ countries (free, zero key)
openFDA — drug/device/food safety data (free, zero key, 240 req/min)
```

### Company & Startup (Round 9)
```
YC OSS API — 5,690 YC companies (free, zero key, daily updated)
AI Funding API — aifunding.me AI startup rounds (free, zero key)
Finnhub — stock/news/fundamentals/IPO (free key, 60 req/min)
FMP — IPO calendar + M&A + financials (free key, 250 req/day)
OpenCorporates — 200M+ global companies (free for open-data)
```

### SEO & Web Infrastructure (Round 9)
```
Open PageRank — domain authority via Common Crawl (free key, 4.3M/day)
OpenRank.io — bulk DA on 40M domains (free, 10K req/24h)
crt.sh — SSL cert + subdomain discovery (free, zero key, zero limit)
Google PageSpeed Insights — Lighthouse + CWV (free, 25K req/day)
Tranco — research-grade top-1M domain ranking (free, zero key)
Wayback CDX — URL snapshot history (free, zero key)
Common Crawl CDX — web-scale crawl index (free, zero key)
Serper.dev — Google SERP JSON (free 2,500/mo)
```

### Podcast & Media (Round 9)
```
PodcastIndex API — 4M+ podcasts (free key)
Apple Podcasts/iTunes API — podcast search (free, zero key)
Open Library API — book search (free, zero key)
Internet Archive API — all media types (free, zero key)
```

### Knowledge Graph (Round 9)
```
Wikidata SPARQL — structured entity queries (free, zero key, 60s timeout)
```

### Site Discovery
```
mcp__tavily__tavily_map — find all URLs on a domain
mcp__firecrawl__firecrawl_map — same, different source
mcp__tavily__tavily_crawl — crawl entire site sections
mcp__firecrawl__firecrawl_crawl — same, different source
```

### Deep Research Agents (use for comprehensive multi-source research)
```
GPT Researcher MCP — autonomous deep research agent, 26K⭐, produces cited reports
STORM (Stanford) — Wikipedia-quality report generation, 28K⭐, multi-perspective synthesis
node-DeepResearch (Jina) — iterative search+read+reason until answer found, 5.1K⭐
local-deep-research — ~95% SimpleQA, local+cloud LLMs, arXiv/PubMed/web, 4.2K⭐
Khoj — AI second brain, deep research + custom agents, 33.7K⭐
AI-Research-SKILLs — research skill library for any AI model, 5.8K⭐ (Orchestra Research)
EvoScientist — self-evolving AI scientists, 2.4K⭐
SurfSense — open-source NotebookLM/Perplexity, connects to Tavily/Slack/Notion/GitHub, 13.6K⭐
RAGFlow — RAG engine + agent capabilities, document ingestion + vector indexing, 76.5K⭐
```

### Free APIs (use via Bash curl — zero key, zero quota)
```
GDELT — global events/news: curl "https://api.gdeltproject.org/api/v2/doc/doc?query=...&mode=ArtList&format=json"
HN Firebase — full HN data: curl "https://hacker-news.firebaseio.com/v0/topstories.json"
OpenAlex — 250M papers: curl "https://api.openalex.org/works?search=..."
Semantic Scholar — citation networks, recommendations: curl "https://api.semanticscholar.org/graph/v1/paper/search?query=...&fields=title,year,citationCount"
Crossref — 150M+ DOIs, metadata: curl "https://api.crossref.org/works?query=..."
CORE — 300M+ open access papers: curl "https://api.core.ac.uk/v3/search/works?q=..."
PubMed — biomedical: curl "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=..."
Europe PMC — European biomedical: curl "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=..."
DBLP — CS papers: curl "https://dblp.org/search/publ/api?q=...&format=json"
DOAJ — Open Access Journals: curl "https://doaj.org/api/search/articles/..."
Zenodo — research data: curl "https://zenodo.org/api/records?q=..."
bioRxiv — biology preprints: curl "https://api.biorxiv.org/details/biorxiv/2026-03-01/2026-03-28"
arXiv API — papers by category/keyword: curl "https://export.arxiv.org/api/query?search_query=..."
Unpaywall — find open access PDFs by DOI: curl "https://api.unpaywall.org/v2/{doi}?email=you@example.com"
HN Algolia — full-text search all HN history: curl "http://hn.algolia.com/api/v1/search?query=..."
Stack Overflow — developer adoption trends: curl "https://api.stackexchange.com/2.3/questions?tagged=...&site=stackoverflow"
npm Downloads — package download trends: curl "https://api.npmjs.org/downloads/range/last-month/{pkg}"
Wikipedia — entity verification + pageviews: curl "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=..."
```

### GitHub CLI (use via Bash — already installed)
```
gh search repos "query" --sort stars — find repos by topic
gh search issues "query" — find issues/discussions
gh api repos/{owner}/{repo} — get repo metadata
gh api search/repositories?q=... — advanced search
```

---

## General Mode Workflow

**Architecture: Opus collects, Opus synthesizes.**

The skill has three phases. Phase 1 (collection) is delegated to **Opus agents** (default). Phase 1.5 (verification) is one **Opus** agent that audits coverage. Phase 2 (synthesis) is done by you (Opus) in the main thread. NEVER do collection yourself — launch agents.

### Step 0: Source Selection — "執藥" (Opus, before launching agents)

Like a pharmacist picking the right medicines for a patient, analyze the user's question and select which source clusters are relevant. Each source cluster = one agent.

**Available source clusters (the full pharmacy):**

Each source has an access type:
- 🟢 **FREE** = curl directly, zero key, zero setup
- 🔑 **KEY** = free API key required (register first)
- 📦 **MCP** = MCP server must be installed (`uvx`, `npx`, or `pip`)
- 💰 **PAID** = has quota/credits, may cost money
- 🔧 **CLI** = needs a CLI tool installed (e.g., `gh`)

| # | Cluster | Sources + access type | When to pick |
|---|---------|----------------------|-------------|
| 1 | **Web Search** | 📦 Tavily Search (1000 credits/mo free) · 📦 Exa Search ($10 free) · 📦 Firecrawl Search (500 credits free) · 📦 open-websearch (free, zero key) · 🟢 WebSearch (built-in) | Almost always |
| 2 | **News & Events** | 📦 newsmcp (free) · 🟢 GDELT (curl, zero key) · 📦 RSS reader (free) · 📦 NYTimes MCP (free key) | Current events, recent developments |
| 3 | **Academic Papers** | 📦 paper-search (free) · 📦 arxiv-mcp (free) · 📦 semantic-scholar (free) · 📦 paper-distill (free) · 🟢 OpenAlex/DBLP/Crossref/DOAJ/Zenodo/arXiv API (all curl, zero key) · 🔑 CORE (free key) | Research, scientific topics |
| 4 | **Citation & Impact** | 🟢 OpenCitations (curl, zero key) · 🟢 NIH iCite (curl, zero key) · 🟢 ORCID (curl, zero key) · 🟢 ROR (curl, zero key) · 🟢 OpenAIRE (curl, zero key) · 🟢 medRxiv (curl, zero key) · 🔑 Altmetric (free research key) | Research impact, key researchers |
| 5 | **Patent & IP** | 🔑 USPTO PatentsView (free key) · 🔑 EPO OPS (free registration) · 🔑 Lens.org (free for research) · 🔑 Google Patents BigQuery (1TB/mo free) | Prior art, IP landscape |
| 6 | **Discussion Forums** | **Reddit → 📦 dialog-mcp (reddit-research) OR 🖥️ logged-in Chrome session — NEVER raw curl (403 + surface-only).** Other login-gated (小紅書/知乎/微博/LIHKG/PTT/Dcard) → their MCP or Chrome CDP. curl OK only for deep zero-auth: 🟢 HN Algolia · 🟢 Lobste.rs · 🟢 Bluesky · 🟢 Mastodon · 🟢 Lemmy · 🟢 StackExchange · 🟢 DEV.to. MCPs: 📦 Discourse (official) · 📦 trend-pulse (37 sources) · 📦 Twitter (💰) | Community discussions, user experiences, sentiment — **USE FORUM DEEP DIVE AGENT TEMPLATE (has the HARD RULE)** |
| 7 | **Trends & Predictions** | 📦 trendsmcp (100 free/mo) · 📦 google-trends-mcp (free) · 🟢 Polymarket Gamma API (curl, zero key) · 💰 ScrapeCreators TikTok/IG (100 free credits) | Trending topics, predictions |
| 8 | **Video & Podcasts** | 📦 youtube-transcript (free) · 🔑 PodcastIndex (free key) · 🟢 iTunes API (curl, zero key) · 💰 Listen Notes (freemium) | Conference talks, expert opinions |
| 9 | **Package Registries** | 🟢 npm/PyPI/crates.io/Packagist/RubyGems/Homebrew/Docker Hub/HuggingFace (all curl, zero key) · 🔑 libraries.io (free key) · 🟢 VS Code Marketplace (curl, unofficial) · 🟢 OSV.dev (curl, zero key) | Dev tool adoption, ecosystem data |
| 10 | **Code & Libraries** | 🔧 GitHub CLI (`gh`, free) · 📦 Exa Code Context ($10 free) · 📦 Context7 (free) | Technical feasibility, implementations |
| 11 | **Company & Startup** | 🟢 SEC EDGAR (curl, zero key) · 🟢 YC API (curl, zero key) · 🔑 Finnhub (free key) · 🔑 FMP (free key) · 🟢 OpenCorporates (curl, free for open-data) · 🔑 UK Companies House (free key) · 🟢 AI Funding API (curl, zero key) | Funding, company intel |
| 12 | **Government & Economic** | 🔑 FRED (free key) · 🟢 BLS v1 (curl, zero key) · 🔑 Census (free key) · 🔑 Congress.gov (free key) · 🟢 Federal Register (curl, zero key) · 🟢 World Bank (curl, zero key) · 🟢 openFDA (curl, zero key) | Economic data, regulations |
| 13 | **SEO & Web Infra** | 🔑 Open PageRank (free key) · 🟢 OpenRank.io (curl, free) · 🟢 crt.sh (curl, zero key) · 🟢 Google PSI (curl, zero key) · 🟢 Tranco (curl, zero key) · 🟢 Wayback CDX (curl, zero key) · 🟢 Common Crawl (curl, zero key) · 🔑 Serper.dev (2500 free/mo) | Domain analysis, SEO |
| 14 | **Knowledge Graph** | 🟢 Wikidata SPARQL (curl, zero key) · 🟢 Wikipedia API (curl, zero key) | Entity verification, facts |
| 15 | **Books & Archives** | 🟢 Open Library (curl, zero key) · 🟢 Internet Archive (curl, zero key) · 📦 mcp-open-library (free) | Books, historical docs |
| 16 | **Biomedical** | 🟢 PubMed (curl, zero key) · 🟢 bioRxiv/medRxiv (curl, zero key) · 🟢 Europe PMC (curl, zero key) · 🟢 openFDA (curl, zero key) · 📦 BiomCP (free) | Medical research, clinical trials |
| 17 | **Competitive Intelligence** | 📦 idea-reality-mcp (free) · 📦 RivalSearchMCP (free) · 📦 Aperture (free, self-host) · 🔑 DetectZeStack (100 free/mo) · 🔑 TheirStack (200 credits/mo) | Competitor analysis |
| 18 | **Product Validation** | 📦 idea-reality-mcp (free) · 🟢 Product Hunt API (free GraphQL token) · 🟢 Wayback CDX (curl, zero key) · 🔑 Asodesk (free token) | Does this exist? Market fit |
| 19 | **Blockchain & On-chain Data** | 🟢 DeFiLlama (curl, zero key) · 🟢 DexScreener (curl, zero key) · 🟢 GeckoTerminal (curl, zero key) · 🟢 CoinGecko (curl, zero key) · 🟢 Polymarket Gamma/Data/CLOB (curl, zero key) · 🔑 Etherscan V2 multichain (free key, 50+ chains) · 🔑 Dune Analytics API (free tier) · 🔑 Bitquery GraphQL (free tier) · 🟢 The Graph subgraphs (GraphQL) · 🟢 mempool.space (curl, zero key) · 🟢 Solana RPC/Solscan (curl) · 💰 Nansen/Arkham (paid, smart-money labels) | Crypto/DeFi/NFT, wallet & token analytics, prediction markets, on-chain flows, smart-money/insider tracking, DEX trades |
| 20 | **GEO / AI Answer-Engine Visibility** | 🟢 Context7 submit (free) · 🟢 GitMCP gitmcp.io (free) · 🟢 LangChain mcpdoc (free) · 🟢 Cloudflare AI Analytics (free) · 🟢 Dark Visitors (freemium) · 🔑 Perplexity Sonar API (probe what AI says) · 🔑 SerpApi / DataForSEO / SearchAPI.io (Google AI Overview extraction, free tier) · 🟡 free-tier visibility trackers: Rankscale / Knowatoa / Trakkr / AIVO / Radarkit · 💰 Profound / Otterly / Peec / Scrunch (paid SOV trackers) · 🟢 Mintlify / Fern (auto llms.txt + MCP, free Hobby) | "Will AI engines / coding agents discover + recommend + correctly use my product/package?" GEO/AEO, llms.txt/MCP discoverability, AI citation share-of-voice. See research-engine.md **Round 11** for the evidence (llms.txt ≈ 0 for AI search but useful for coding agents; docs-MCP > llms.txt; Reddit dominates AI citations; Context7 submit = zero-effort win). |

### Pre-flight Check: "Research Engine Status"

**Step 1 — Run the health check (MANDATORY before any research session):**

```bash
bash ~/MyGithub/ai-research-engine/health-check.sh
```

This pings every zero-key free API, CLI, and lists connected MCP servers, then writes `~/MyGithub/ai-research-engine/health-check-report.md` with ✅/⚠️/❌ per source. **Read that report. Only hand agents ✅ sources.** A ❌ endpoint that returns nothing is NOT evidence of "nothing found" — it's a dead tool, and citing its silence as a finding is a research defect. (If the report is fresh — generated today — you can reuse it instead of re-running.)

**Step 2 — confirm what's available for the selected clusters:**

- 🟢 FREE APIs → check the health report (some go dead/change without notice)
- 🔧 CLI → check if installed: `which gh` etc.
- 📦 MCP → check the report's "Connected MCP servers" list. **Forums (Reddit etc.) MUST go through MCP or the logged-in Chrome session — never raw curl (see the HARD RULE in the Forum Deep Dive Agent Template).**
- 🔑 KEY → check if env var is set (e.g., `FRED_API_KEY`, `FINNHUB_API_KEY`)
- 💰 PAID → check if key exists AND note remaining quota if known

**Then in your Step 0 presentation, flag any issues:**

```
I'll search these sources (10 agents in parallel):

**Does this already exist?**
✅ Code & Libraries — GitHub repos, npm/PyPI packages
✅ Package Registries — all free, no setup needed
✅ Product Validation — Product Hunt, Wayback CDX
⚠️ Competitive Intelligence — idea-reality-mcp not installed
   → Install: uvx idea-reality-mcp (takes 30 seconds)
   → Or skip this cluster, I'll use Web Search + GitHub instead

**What are people saying?**
✅ Social Platforms — Reddit, Bluesky, StackExchange (all free curl)
⚠️ Twitter — MCP installed but reads cost $0.01 each
✅ Web Search — Tavily (923/1000 credits remaining this month)

**Is this space growing?**
✅ News & Events — GDELT + newsmcp
⚠️ Trends — trendsmcp not installed (Google Trends data)
   → Install: npx -y trendsmcp (needs TRENDS_API_KEY, 100 free/mo)
   → Or skip, I'll use WebSearch for trend data instead

⚠️ 2 sources need setup. Want to install them first, or proceed without?
```

**The user can then:**
- Install the missing tools and proceed with full coverage
- Skip the missing tools and proceed with what's available
- Ask which tools are most important to install

**Key principle: NEVER silently skip a source because it's not installed. Always tell the user what they're missing and how to get it.**

**How to pick — the reasoning process (this is the most important step):**

Don't just keyword-match. Think about what KIND of answer the user needs, and WHERE that answer would live in the real world.

**Step 0a: Understand the real question behind the question.**

| User says | Real question | Where the answer lives |
|-----------|--------------|----------------------|
| "Has anyone done X?" | Is there prior art? Is this a new idea or solved problem? | GitHub repos, academic papers, patents, Product Hunt, blog posts, HN discussions |
| "What's the best X?" | What are my options and how do they compare? | Package downloads, GitHub stars, Reddit/SO recommendations, benchmark papers |
| "Should we build X?" | Is there market demand + is the space crowded? | Competitor repos, funding data, job postings, social pain points, app store data |
| "How does X work?" | Technical deep dive | Library docs, conference talks, academic papers, source code |
| "What's happening with X?" | Current events + trend direction | News, social media, Google Trends, prediction markets, RSS feeds |
| "Is X better than Y?" | Head-to-head comparison with data | Benchmarks, download stats, community sentiment, pricing pages, expert reviews |

**Step 0b: For each source cluster, reason about whether it would contain relevant data.**

Think like a detective: "If the answer to this question exists somewhere in the world, WHERE would it be?"

Examples of good reasoning:
- "User asks if anyone has built an MCP server for X → I should check GitHub (repos), npm/PyPI (packages), Product Hunt (launches), HN (announcements), academic papers (if research-y), and patents (if they're worried about IP)"
- "User asks about React state management → npm downloads will show adoption velocity, StackOverflow tag volume shows developer demand, Reddit/Twitter shows sentiment, GitHub stars shows mindshare — but patents and government data are irrelevant"
- "User asks about AI regulation impact → Congress.gov for actual bills, Federal Register for proposed rules, news for coverage, academic papers for policy analysis, financial data for market impact, social platforms for industry reaction"

**Step 0c: Present your selection — grouped by WHY, with a "maybe" section.**

Default stance: **cast wide**. If a source cluster is even slightly related, include it. Only skip clusters that are clearly irrelevant (e.g., biomedical for a React library question). When in doubt, put it in the "maybe" section and let the user decide.

Group your selected sources by the REASON you're picking them, so the user understands your thinking:

```
Your question: "Has anyone built an MCP server for browser recording?"

Here's what I need to find out, and where I'll look:

**Does this already exist?**
✅ Code & Libraries — search GitHub repos, npm/PyPI packages
✅ Package Registries — check download stats if competitors exist
✅ Product Validation — Product Hunt launches, app store presence
✅ Competitive Intelligence — reality score + similar tools scan

**What are people saying about browser recording tools?**
✅ Social Platforms — Reddit/HN/Twitter/Bluesky/StackOverflow discussions
✅ Web Search — blog posts, announcements, landing pages

**Is this space growing or dying?**
✅ News & Events — recent launches, industry news
✅ Trends & Predictions — Google Trends interest, Polymarket (if applicable)

**How are existing tools built?**
✅ Video & Podcasts — demo videos, conference talks about the space

**Maybe related (want me to include these too?):**
❓ Academic Papers — there might be research on browser automation/recording
❓ Patent & IP — someone might have patented browser recording techniques
❓ SEO & Web Infra — could check competitor domain authority + tech stack

**Skipping (clearly not relevant):**
⬚ Biomedical
⬚ Government & Economic
⬚ Knowledge Graph
⬚ Books & Archives

That's 9 definite + 3 maybe agents. Want me to include the maybes too?

Options:
(a) Go with everything (install missing tools first)
(b) Just use what's ready now — skip anything that needs setup
(c) Let me adjust the list
```

**Wait for user confirmation.** The user may:
- Say "go" / "全部啦" / option (a) → include all, install missing tools first
- **Say "just use what's ready" / option (b) → auto-skip all 📦/🔑/💰 sources that aren't already installed/configured. Only use 🟢 FREE curl APIs + already-installed MCPs + built-in tools. No setup friction at all.**
- Say "let me adjust" / option (c) → user picks specific clusters to add/remove
- Say "add X" / "remove Y" → adjust specific clusters
- Say "why no Z?" → explain your reasoning, adjust if they disagree

**Option (b) is important** — some users want results NOW without installing anything. The engine should gracefully degrade: use whatever free curl APIs are available in each cluster, skip MCP-only sources that aren't installed, and note in the final report which sources were skipped and what coverage was lost.

**Only after user confirms sources, launch the agents.**

Default: **all collection agents run on `model: "opus"`** (standing rule — data quality > token cost). Don't ask which model; just use Opus. Only drop to Sonnet/Haiku if the user explicitly says to save tokens. Then Opus (main thread) synthesizes.

**Then proceed to Phase 1.**

### Forum Deep Dive Agent Template (MANDATORY when Cluster 6 is selected)

When the user's question involves community opinions, user experiences, reviews, or "what do people think about X", **ALWAYS launch a dedicated Forum Deep Dive Agent** using this template.

> 🚨 **HARD RULE — Reddit and any login-gated forum MUST use MCP or the logged-in Chrome browser session, NEVER raw `curl .json`.**
>
> Raw `curl` on `reddit.com/....json` is surface-level and rate-limited: you get truncated search results, no deep comment trees, and silent throttling. That makes the research shallow and the agent can't even tell it got starved. So:
> - **Reddit → `dialog-mcp` (reddit-research, semantic search 20K+ subs + full comment trees) OR `mcp__chrome-devtools__evaluate_script` `fetch()` from the logged-in session** (authenticated cookie = no rate limit, deep threads). Fetch the FULL comment tree (`/r/<sub>/comments/<id>/.json`), not just titles.
> - **Login-gated / cookie forums (小紅書, 知乎, 微博, LIHKG, PTT, Dcard) → their MCP, or Chrome CDP with the user's session.**
> - **`curl` is allowed ONLY for genuinely deep zero-auth APIs:** HN Algolia (full-text all history), Lobste.rs `.json`, Bluesky, Mastodon, Lemmy, StackExchange, DEV.to. These are NOT rate-starved and return real depth.
> - Before relying on any source, the agent must confirm it actually got data. An empty/truncated response is NOT evidence of "nothing found" — it's a dead tool. Say so explicitly.

**Agent prompt template (copy and customize {TOPIC}, {SUBREDDITS}, {FORUMS}):**

```
You are a Forum Research Agent. Search ALL of these discussion forums for: {TOPIC}

You MUST use tools. Do NOT plan or ask for confirmation. Execute immediately.

## Reddit — MANDATORY via MCP or logged-in browser, NOT raw curl

Reddit raw curl .json is surface-level + rate-limited. Use ONE of:

(A) dialog-mcp (reddit-research — semantic search + full comment trees):
   ToolSearch: "select:mcp__dialog-mcp__discover_operations,mcp__dialog-mcp__get_operation_schema,mcp__dialog-mcp__execute_operation"
   → discover_operations → discover_subreddits/search → fetch posts + FULL comment trees (10+ posts), verbatim quotes + scores.

(B) Logged-in Chrome session (authenticated = no rate limit, deep):
   ToolSearch: "select:mcp__chrome-devtools__new_page,mcp__chrome-devtools__evaluate_script"
   → evaluate_script: await fetch('https://www.reddit.com/r/{SUBREDDIT}/search.json?q={TOPIC}&restrict_sr=on&sort=top&limit=25').then(r=>r.json())
   → for each hit, fetch the FULL thread: await fetch('https://www.reddit.com/r/<sub>/comments/<id>/.json').then(r=>r.json())
   Try subreddits: {SUBREDDITS}

Capture verbatim quotes from BOTH posts AND top comments — the comment depth is the point.

## Tier 1: Free curl APIs — ONLY for these deep zero-auth sources (Reddit is NOT here)

# Hacker News (Algolia — full-text, deep, fine via curl)
curl -s "https://hn.algolia.com/api/v1/search?query={TOPIC}&tags=story"
curl -s "https://hn.algolia.com/api/v1/search?query={TOPIC}&tags=comment"

# Bluesky
curl -s "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={TOPIC}&limit=25"

# Mastodon (try multiple instances)
curl -s "https://mastodon.social/api/v2/search?q={TOPIC}&type=statuses&limit=20"

# Lemmy
curl -s "https://lemmy.world/api/v3/search?q={TOPIC}&type_=Posts&sort=TopMonth&limit=20"

# StackExchange (pick relevant sites)
curl -s --compressed "https://api.stackexchange.com/2.3/search/excerpts?order=desc&sort=relevance&q={TOPIC}&site={SE_SITE}"

# Lobste.rs
curl -s "https://lobste.rs/search.json?q={TOPIC}&what=stories&order=relevance"

# DEV.to
curl -s "https://dev.to/api/articles?tag={TOPIC_TAG}&per_page=20"

## Tier 2: Asian forums (if topic is relevant to beauty/lifestyle/culture/HK/TW/CN)

# Dcard (台灣)
curl -s "https://www.dcard.tw/service/api/v2/search/posts?query={TOPIC_ZH}&limit=20"

# LIHKG (香港)
curl -s "https://lihkg.com/api_v2/thread/search?q={TOPIC_ZH}&page=1&count=20" \
  -H "x-li-device: $(python3 -c 'import uuid,hashlib; print(hashlib.sha1(str(uuid.uuid4()).encode()).hexdigest())')" \
  -H "x-li-device-type: browser"

# 百度貼吧
curl -s "https://tieba.baidu.com/f/search/res?qw={TOPIC_ZH}&ie=utf-8"

## Tier 3: MCP servers (if installed)
- mcp__reddit__* for deeper Reddit search
- mcp__xiaohongshu__* for 小紅書
- mcp__zhihu__* for 知乎
- mcp__discourse__* for Discourse forums
- mcp__weibo__* for 微博

## Tier 4: Chrome CDP fallback
If any curl API fails or rate-limits, use Chrome DevTools MCP to browse with the user's logged-in session.

## Output format
For each forum, report:
- Forum name + URL
- Number of relevant results found
- Top 3-5 most relevant posts/comments with:
  - Author (username)
  - Direct quote (paste key quotes verbatim)
  - Vote count / engagement
  - URL
- CONFIDENCE: 1-5 how well this forum covered the topic
- GAPS: what this forum didn't cover

Report in the user's language. Cite every finding with source URL.
```

**Forum selection by topic type:**
- Tech/Dev → HN, Lobste.rs, StackOverflow, Reddit r/programming, DEV.to
- Beauty/Skincare → Reddit r/SkincareAddiction r/AsianBeauty, 小紅書, Dcard 美妝, PTT MakeUp
- Health → StackExchange Health, Reddit r/AskDocs, 知乎
- HK topics → LIHKG, Reddit r/HongKong
- TW topics → PTT, Dcard
- CN topics → 知乎, 微博, 百度貼吧, 小紅書
- Finance → Reddit r/investing, LIHKG 財經, PTT Stock
- Gaming → Reddit, Discord, 巴哈姆特
- Startups → HN, Product Hunt, IndieHackers

### Phase 1: Collection (Opus agents, background)

#### Step 1: Launch Agents

For each confirmed source cluster, launch ONE agent at the confirmed model. Launch ALL in ONE message with `run_in_background: true`.

Each agent's prompt MUST include:
- The specific tools/APIs from its cluster (copy from the table above)
- "Report raw findings with URLs. Do NOT synthesize or draw conclusions."
- "Use tables and structured formats. Paste key quotes directly."
- "Cite every finding with a source URL."
- "At the END of your report, add a CONFIDENCE section: rate your confidence 1-5 that you found comprehensive data, and list any GAPS — topics you searched for but found little/nothing on."

Agents return RAW DATA — lists of papers, URLs, quotes, numbers. Not analysis. Plus a confidence rating + gap list for the verification step.

**Content Extraction (second wave):**
After first wave returns, if specific URLs need deep-diving, launch additional agents: Tavily Extract + Exa Crawl + Firecrawl Scrape.

#### Step 3: Wait for all agents to complete
Do not proceed until all background agents have returned.

### Phase 1.5: Verification (Opus, BEFORE synthesis — Round 9 新增)

After ALL Phase 1 agents return, launch ONE Opus verification agent with ALL agent results:

```
Verification Agent prompt:
"You are a research completeness auditor. Given these findings from [N] agents:
[paste all agent results]

Evaluate:
1. COVERAGE: Which aspects of the research question are well-covered? Which are MISSING?
2. CONTRADICTIONS: Do any sources contradict each other? List each contradiction with both claims + sources.
3. CONFIDENCE: Rate overall confidence 1-5 (1=barely any data, 5=comprehensive multi-source coverage).
4. GAPS: What specific follow-up searches would fill the biggest gaps?

Output a structured JSON:
{
  'coverage_score': 1-5,
  'well_covered': ['topic A', 'topic B'],
  'missing': ['topic X', 'topic Y'],
  'contradictions': [{'claim_a': '...', 'source_a': '...', 'claim_b': '...', 'source_b': '...'}],
  'recommended_followup': ['search query 1', 'search query 2']
}
"
```

**If coverage_score < 3**: Launch follow-up agents targeting the gaps before synthesis.
**If contradictions found**: Flag them explicitly in the final report — never silently merge conflicting claims.

> This step is based on VMAO (ICLR 2026) which improved answer completeness from 3.1 → 4.2/5.

### Phase 2: Synthesis (Opus, main thread — NEVER delegate this)

**Tell the user:** "All agents returned. I'm now reading and cross-referencing everything myself (Opus). This is the part where cheap models won't cut it — synthesis needs the best model."

#### Step 4: Cross-Reference and Synthesize
YOU (Opus) do this — NEVER delegate synthesis to a collection agent. Read all agent results yourself and:
- Compare findings across sources
- Flag contradictions
- Identify consensus vs outlier opinions
- Find the GAP — what's missing from existing research/products?
- Cite sources for every claim

#### Step 5: Report

```markdown
# Research: [Topic]
Date: [today]
Sources: [count] sources across [count] tools
Coverage Score: [1-5 from verification agent]

## Key Findings
1. [Finding with source]
2. [Finding with source]
...

## Detailed Analysis
[Organized by subtopic]

## Contradictions & Disputes
[Any conflicting claims between sources — list both sides with citations. Never silently merge.]

## What's New (if researching updates)
[Only things that changed recently]

## Gaps & Limitations
[What the research could NOT find or verify. Be honest about blind spots.]

## Actionable Recommendations
[What to do based on findings]

## Quality Assessment (DRACO dimensions)
- Factual accuracy (52% weight): [self-rate 1-5]
- Analytical depth (22% weight): [self-rate 1-5]
- Presentation (14% weight): [self-rate 1-5]
- Source attribution (12% weight): [self-rate 1-5]

## Sources
[Full list with URLs]
```

#### Step 6: Save Results
Save to `OUTPUT_DIR/[topic-slug]-[date].md`.

---

## Shopping Mode Workflow

> 用戶想**買產品 / 送禮 / 格價**。核心：aggregator 行先（繞過 anti-bot），唔好直接 Firecrawl/curl Amazon/Temu（一定 503/captcha）。

### Step 1 — 問清需求（如未清楚）
- 買乜 / budget / must-have / nice-to-have / 邊度（Canada？）
- 送禮多問：**收禮人**（關係/年齡/興趣）、場合

### Step 2 — 並行收 data（用 verified stack）
```bash
source ~/.config/research-engine/keys.env 2>/dev/null
# ⭐ Serper Shopping = Google Shopping，跨店真價，繞過 anti-bot（primary）
curl -s -X POST "https://google.serper.dev/shopping" -H "X-API-KEY: $SERPER_API_KEY" \
  -H "Content-Type: application/json" -d '{"q":"<product + key spec>","gl":"ca"}' | jq '.shopping[:10]'
```
- **Apify MCP**（`mcp__apify__*`）攞硬 site 深度數據（review/variants/sold-history）：actor `junglee/Amazon-crawler`、`piotrv1001/temu-listings-scraper`、`sian.agency/taobao-tmall-product-scraper`、`zen-studio/1688-wholesale-scraper`、`piotrv1001/aliexpress-listings-scraper`、`e-commerce/walmart-product-detail-scraper`、`caffein.dev/ebay-sold-listings`、`automation-lab/etsy-scraper`。
- ⭐ **Reddit（dialog-mcp）— 按產品揀 sub，唔係淨係 gift sub**：用 `discover_subreddits` 搵嗰個**產品品類**嘅真實社群，喺嗰度攞用家真實推薦/避雷。買廚具→r/cookware·r/Cooking·r/castiron·r/BuyItForLife；耳機→r/headphones·r/HeadphoneAdvice；monitor→r/Monitors；床褥→r/Mattress… 任何品類都 discover 返佢自己嘅 sub。**只有當明確係「送禮」**先額外睇 r/giftideas·r/Gifts。（raw .json 403，一定用 dialog-mcp）
- **專業評測**：Firecrawl/Tavily Extract 抓 Wirecutter·RTINGS·NYT/Strategist gift guide。
- **superprecio MCP**：grocery/食品先用。
- ⚠️ 唔好叫 `mcp__amazon__*` / `mcp__agora__*`（已移除，係廢的）。

### Step 3 — 比較表
| Model | Price (CAD) | Key Specs | Pros/Cons | Review | 邊度買 |

### Step 4 — 推薦：Best overall · Best value · Premium pick（每個 1-2 句 tie 返需求），連直接購買 link。

> 詳細版見 `/shop` skill（同一套 stack）。Shopping mode = 將 /shop 嘅能力收喺統一入口。

---

## Product Mode Workflow

### Reference Documents
- **Research Engine (MASTER TOOL LIST)**: `RESEARCH_ENGINE`
- **Existing products**: `PRODUCTS_INDEX`
- **Product specs**: `PRODUCT_SPECS`

### Step 1: Understand What to Research

If user gives a product name:
- Read the product spec / README from the repo
- Identify the core value proposition in 1 sentence

If user gives an idea (e.g. "MCP server for browser recording"):
- Clarify the core value proposition in 1 sentence

### Step 2: Phase 0 — Reality Check (FREE, 2 min)
```
idea-reality-mcp: scan GitHub + HN + npm + PyPI + PH
→ Reality score < 30 = green light
→ Reality score > 70 = pivot or differentiate
```

### Step 3: Phase 1 — Broad Scan (parallel agents, ALL FREE TOOLS)

> ⚠️ Free tools first. After Phase 1, ask user: "免費搵到 X 個結果，需唔需要用 paid tools 再深入？"

Launch ALL agents in ONE message with `model: "opus"` and `run_in_background: true`.

#### Agent A: Direct Competitors — FREE
```
→ WebSearch + open-websearch + Exa Search ("alternative to {product}")
→ gh search repos + gh api search/repositories (GitHub landscape)
→ npm search + npm Downloads API + PyPI Stats API (package ecosystem adoption velocity)
→ libraries.io API (cross-registry dependents + SourceRank)
→ Homebrew Analytics + Docker Hub API (if CLI/infra tool)
→ VS Code Marketplace (if IDE extension)
→ HuggingFace Hub API (if AI/ML tool)
```

#### Agent B: User Pain Points — FREE
```
→ Reddit pain points → dialog-mcp (reddit-research) OR logged-in Chrome session — NEVER raw curl .json
→ StackExchange API (170+ sites — tagged questions volume + answers)
→ Discourse API (OSS community forums: Rust/React/OpenAI/Julia)
→ Bluesky AT Protocol + Mastodon API (tech discourse)
→ Twitter search (mcp__twitter__search_tweets)
→ Hashnode + DEV.to (developer blog posts about the problem)
→ Lobste.rs JSON (high-signal tech community)
→ WebSearch ("{category} problems frustrations")
```

#### Agent C: Market Trends + News — FREE
```
→ newsmcp (real-time clustered news)
→ GDELT curl (global news events)
→ Dev.to API (trending articles)
→ HN Algolia API (search HN history)
→ rss-reader (competitor blog RSS feeds)
→ trendsmcp / Google Trends (search interest over time)
→ Polymarket Gamma API (prediction market odds if applicable)
```

#### Agent D: Technical Feasibility — FREE
```
→ Context7 (library docs)
→ Exa Code Context (code examples, SDK docs — better than WebFetch per WebCode benchmark)
→ GitHub CLI (reference repos, architecture, contributor activity)
→ YouTube transcripts (conference talks about the space)
→ PodcastIndex + iTunes API (podcast discussions about the space)
→ paper-search-mcp / arxiv-mcp (if research-heavy area)
```

#### Agent E: Distribution & Ecosystem — FREE
```
→ npm Downloads + PyPI Stats + crates.io + Homebrew Analytics (adoption curves)
→ libraries.io (who depends on this? cross-registry)
→ Product Hunt API (launches + upvotes)
→ Wayback CDX (competitor website evolution)
→ Wikipedia API (entity verification)
→ Open PageRank + OpenRank.io (competitor domain authority)
→ crt.sh (competitor infrastructure — subdomains)
→ Asodesk API / appgoblin (if mobile app)
```

#### Agent F: Market Signals — FREE
```
→ jobspy (hiring trends = market demand signal)
→ SEC EDGAR curl (if competitor is public — filings, Form D funding)
→ YC OSS API (is competitor YC-backed?)
→ AI Funding API (AI startup funding rounds)
→ Finnhub curl (stock/news if public company)
→ OpenCorporates curl (company registry info)
→ UK Companies House curl (if UK competitor)
→ Open Collective API (OSS project funding)
→ WebSearch ("{category} funding series A")
```

#### Agent G: SEO & Web Intelligence — FREE
```
→ Open PageRank + OpenRank.io (domain authority comparison)
→ Google PageSpeed Insights (competitor site performance)
→ Serper.dev (Google SERP — who ranks for target keywords?)
→ crt.sh (SSL cert history — how old is their infrastructure?)
→ Tranco (domain ranking comparison)
→ DetectZeStack / Wappalyzer (competitor tech stack)
```

### Step 3.5: Verification (same as General Mode Phase 1.5)

After ALL agents return, launch ONE Opus verification agent to check coverage + contradictions. See the **Phase 1.5: Verification** section above for the full prompt.

If coverage_score < 3 or major gaps found, launch follow-up agents before proceeding.

### Step 4: Phase 2 — Paid Deep Dive (ONLY if Phase 1 insufficient)

> 💰 Ask user first. Budget: ~$0.50-1.00 per session.

```
If need deeper competitor analysis:
  → Tavily Research (deep, multi-source synthesis)
  → Exa Search (semantic: similar tools Phase 1 missed)
  → Firecrawl Scrape (competitor docs/pricing)

If need more pain point evidence:
  → Tavily Search (targeted deep search)

If need social sentiment:
  → Twitter API ($0.005/read — only most important threads)
  → ScrapeCreators (TikTok + Instagram data)
```

### Step 5: Comparison Table

| | Our Product | Competitor A | Competitor B | Competitor C |
|---|---|---|---|---|
| **Name** | | | | |
| **GitHub stars** | | | | |
| **npm downloads** | | | | |
| **Price** | | | | |
| **Key feature 1** | | | | |
| **Key feature 2** | | | | |
| **Key feature 3** | | | | |
| **Weakness** | | | | |
| **Last updated** | | | | |
| **MCP native?** | | | | |

### Step 6: SWOT Analysis

| | Positive | Negative |
|---|---|---|
| **Internal** | **Strengths**: what we do better | **Weaknesses**: what we lack |
| **External** | **Opportunities**: market gaps we can fill | **Threats**: competitors that could kill us |

### Step 7: Positioning Recommendation

1. **Our unique angle** — the 1 sentence that differentiates us
2. **Target user** — who specifically should we market to?
3. **Messaging** — how to describe the product
4. **Missing features** — what should we add?
5. **Distribution priority** — which channels matter most?

### Step 8: Quality Assessment (DRACO dimensions)

Same as General Mode — rate the research output:
- Factual accuracy (52% weight): [self-rate 1-5]
- Analytical depth (22% weight): [self-rate 1-5]
- Presentation (14% weight): [self-rate 1-5]
- Source attribution (12% weight): [self-rate 1-5]

Also include:
- **Contradictions & Disputes** — any conflicting claims between sources
- **Gaps & Limitations** — what the research could NOT find or verify

### Step 9: Save Results
Save findings to `OUTPUT_DIR/[product]-[date].md`.

---

## Rules

0. **Run the health check FIRST** — `bash ~/MyGithub/ai-research-engine/health-check.sh`, read the report, only use ✅ sources. A dead endpoint's silence is never "found nothing".
1. **Read research-engine.md FIRST** — every time, no exceptions
1b. **🚨 FORUMS = MCP OR BROWSER SESSION, NEVER RAW CURL.** Reddit and any login-gated forum (小紅書/知乎/微博/LIHKG/PTT/Dcard) MUST be researched through their MCP (e.g. `dialog-mcp` reddit-research) or the logged-in Chrome session (`mcp__chrome-devtools__evaluate_script` fetch). Raw `curl .json` is surface-level + rate-limited = shallow research the agent can't tell is starved. `curl` is allowed only for genuinely deep zero-auth APIs (HN Algolia, Lobste.rs, Bluesky, Mastodon, Lemmy, StackExchange, DEV.to). Fetch FULL comment trees, not just titles.
2. **Use ALL available FREE tools** — don't just use one source. Parallel everything.
3. **Parallel execution** — launch multiple searches simultaneously
3b. **Sub-agents MUST execute immediately** — when launching sub-agents for data collection, their prompts MUST include "You MUST use tools. Do NOT plan or ask for confirmation. Execute immediately." Sub-agents cannot see the user, so they must never wait for confirmation. Any agent that plans without executing is wasting tokens and time. The Step 0 confirmation workflow is for the MAIN THREAD only, never for sub-agents.
4. **🚨 FREE TOOLS ONLY BY DEFAULT** — NEVER use paid/limited tools without asking first:
   - After free phase, ASK: "Found X results from free sources. Want to use paid/limited APIs for deeper coverage? (Tavily Research, Exa, Firecrawl, Twitter, ScrapeCreators)"
   - If user says NO → go straight to synthesis with free results
   - If user says YES → THEN use the paid tools
   - See research-engine.md **Quota Classification** for which tools are free vs limited
5. **Cite everything** — no claims without sources
6. **Be specific** — "42% increase" not "significant increase"
7. **Report what's NEW** — if the user asks about 2026 updates, don't give generic 2024 advice
8. **Cross-reference** — if only one source says something, flag it as unverified
9. **Exa Code Context > Claude WebFetch** for code docs (WebCode benchmark: 82.8% vs 59.8% completeness)
10. **Be brutally honest** — in product mode, if our product is worse, say so
