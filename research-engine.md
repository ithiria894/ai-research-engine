# Research Engine — 資料搜集工具 Inventory

> 最後更新：2026-04-03（Round 9: 16-agent comprehensive audit — trend/influencer, patents, podcasts, community, package registries, gov/economic, company/startup, SEO, citations, AI brand visibility, workflow improvements）
> 呢個 file 係 research 工具嘅 master list。定期更新（搵新 API、MCP、data source）。
> Skill: `/market-research` 會 reference 呢個 file。
>
> **Philosophy：** 資料搜集係所有 decision 嘅 foundation。寧願花 80% token 做 research，20% 做 execution。
> **原則：** 所有免費嘅工具一定要 apply。Token 成本唔係問題，資料質素先係。

---

## 已安裝（✅ 即刻可用）

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
| **Firecrawl Scrape/Crawl/Map/Search/Extract** | 抓網頁 → clean markdown | 500 credits free | `mcp__firecrawl__*` |

### Product Validation & Competitive Intelligence（Round 1 新增）

| Tool | 做咩用 | 成本 | MCP Server |
|------|--------|------|------------|
| **idea-reality-mcp** | Scan GitHub + HN + npm + PyPI + PH，出 reality score 0-100 | 免費 | `idea-reality` |
| **reddit-research-mcp (Dialog)** | Semantic search 20K+ subreddits，免 Reddit API creds | 免費 | `dialog-mcp`（HTTP） |
| **free-web-search-ultimate** | 10+ engines（DuckDuckGo、Bing、Google、Brave、YouTube、Reddit、arXiv）零 API key | 免費 | `free-web-search` |

### News & Trends（Round 2 新增）

| Tool | 做咩用 | 成本 | MCP Server |
|------|--------|------|------------|
| **newsmcp** | Real-time clustered news，hundreds of sources | 免費 | `newsmcp` |
| **mcp-hn** | Search HN + top stories + user profiles | 免費 | `mcp-hn` |
| **Google News & Trends** | Google News RSS + Google Trends data | 免費 | `google-trends` |
| **RSS Reader** | Subscribe + extract any RSS feed | 免費 | `rss-reader` |

### Research Papers & Benchmarks（Round 4 新增）

> 呢個 category 係搵 WebCode 類型嘅文章：company benchmark、comparison study、"we tested X vs Y" findings。

**RSS Feeds（全部用 `rss-reader` MCP subscribe）：**

| Feed | 內容 | URL |
|------|------|-----|
| **arXiv cs.IR** | Information Retrieval 學術 papers（search benchmark 類） | `https://export.arxiv.org/rss/cs.IR` |
| **arXiv cs.AI** | AI 學術 papers | `https://export.arxiv.org/rss/cs.AI` |
| **arXiv cs.LG** | Machine Learning papers | `https://export.arxiv.org/rss/cs.LG` |
| **Papers with Code** | 最新 ML papers + benchmark results | `https://paperswithcode.com/latest.rss` |
| **Hugging Face Papers** | Curated AI papers，有社群討論 | `https://huggingface.co/papers.rss` |
| **OpenAI News** | OpenAI research + product announcements | `https://openai.com/news/rss.xml` |
| **LangChain Blog** | LangChain engineering findings | `https://blog.langchain.com/rss/` |
| **The Gradient** | Deep-dive AI research commentary | `https://thegradient.pub/rss` |
| **Simon Willison** | LLM tool findings + practical benchmarks（高 signal） | `https://simonwillison.net/atom/everything/` |
| **Import AI** | Jack Clark weekly AI research digest | `https://importai.substack.com/feed` |

**AI-Generated RSS Feeds（解決冇 RSS 嘅問題）：**
- **ai-rss-feeds** (`github.com/leontloveless/ai-rss-feeds`) — 用 AI 自動生成 CSS selector，每小時 GitHub Actions 更新
- 直接 subscribe GitHub raw XML（用 `rss-reader` MCP `fetch_feed_entries`）

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
| **ScrapeCreators** | Reddit+TikTok+Instagram 一個 key 搞掂 | `curl "https://api.scrapecreators.com/..."` | 100 free credits（last30days 用呢個） |
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
| **小紅書 (Xiaohongshu)** | 中國 lifestyle/消費 social platform | via xiaohongshu-mcp HTTP API 或 ScrapeCreators | 需 MCP server 或 ScrapeCreators credits |
| **Bluesky AT Protocol** | 36M users，tech discourse tracking | `curl "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor=..."` | 免費，零 key，幾乎零 rate limit |
| **Mastodon** | 去中心化社群 timelines + trending | `curl "https://mastodon.social/api/v1/trends/statuses"` | 免費，零 key，300 req/5min per instance |
| **Lemmy** | Reddit 替代品 federated communities | `curl "https://lemmy.world/api/v3/search?q=...&type_=Posts"` | 免費，零 key |
| **Lobste.rs JSON** | 高 signal tech community（invite-only） | Append `.json` to any URL，e.g. `https://lobste.rs/hottest.json` | 免費，零 key |
| **Hashnode GraphQL** | 1M+ tech writers blog platform | `POST https://gql.hashnode.com` GraphQL query | 免費，零 auth for read |
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
| **YC OSS API** | 5,690 YC 公司，每日更新 | `curl "https://raw.githubusercontent.com/yc-oss/api/main/batches/latest.json"` | 免費，零 key |
| **AI Funding API** | AI startup funding rounds | `curl "https://aifunding.me/api/v1/rounds?limit=20"` | 免費，零 key |
| **Finnhub** | 股票/新聞/fundamentals/IPO calendar | `curl "https://finnhub.io/api/v1/stock/profile2?symbol=AAPL&token={key}"` | 免費 key，60 req/min |
| **FMP** | IPO calendar + M&A data + financials | `curl "https://financialmodelingprep.com/api/v3/ipo_calendar?apikey={key}"` | 免費 key，250 req/day |
| **OpenCorporates** | 200M+ 全球公司，170+ jurisdictions | `curl "https://api.opencorporates.com/v0.4/companies/search?q=..."` | 免費（開源項目）；商業 £2,250+/yr |

**新 API（Round 9 新增 — Patent & IP）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **USPTO PatentsView** | US 專利搜尋（發明人/分類/citation） | `curl "https://search.patentsview.org/api/v1/patent/?q=..."` | 免費 key，45 req/min（⚠️ 遷移至 data.uspto.gov，舊 API 2026-04-20 關） |
| **EPO OPS** | 歐洲 + WIPO + 多國專利 | `https://ops.epo.org/3.2/rest-services/` | 免費 registration，4 GB/week |
| **Lens.org** | 140M+ 專利 + scholarly citation 交叉分析 | `curl "https://api.lens.org/patent/search"` | 免費 for non-commercial research（需申請 key） |
| **Google Patents BigQuery** | 76M+ 全球專利（US/EU/CN/JP/KR） | BigQuery SQL | Google Cloud 1 TB/mo 免費 |

**新 API（Round 9 新增 — SEO & Web Infrastructure）：**

| API | 做咩用 | 點用 | 限制 |
|-----|--------|------|------|
| **Open PageRank** | Domain authority（Common Crawl-based） | `curl "https://openpagerank.com/api/v1.0/getPageRank?domains[]=example.com" -H "API-OPR: {key}"` | 免費 key，4.3M lookups/day |
| **OpenRank.io** | Bulk domain authority，40M domains | `curl "https://openrank.io/api/v1/domain?d=example.com"` | 免費，10K req/24h |
| **crt.sh** | SSL cert lookup + subdomain discovery | `curl "https://crt.sh/?q=example.com&output=json"` | 免費，零 key，零 limit |
| **Google PageSpeed Insights** | Lighthouse scores + Core Web Vitals | `curl "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=..."` | 免費，25K req/day，零 billing |
| **Tranco** | Research-grade top-1M domain ranking | `curl "https://tranco-list.eu/api/ranks/domain/example.com"` | 免費，零 key |
| **Wayback CDX** | URL snapshot history + timestamps | `curl "http://web.archive.org/cdx/search/cdx?url=example.com&output=json"` | 免費，零 key |
| **Common Crawl CDX** | Web-scale crawl index（607M domains） | `curl "https://index.commoncrawl.org/CC-MAIN-2026-13-index?url=example.com&output=json"` | 免費，零 key |
| **Cloudflare Radar** | DNS-based domain popularity ranking | Cloudflare API | 免費 CF key |
| **Serper.dev** | Google SERP JSON（最慷慨 free tier） | REST API | 免費 2,500 searches/mo |

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
| **Frankfurter** | 160+ 央行匯率，歷史數據 | `curl "https://api.frankfurter.dev/latest?from=USD"` | 免費，零 key，零 limit |
| **CoinGecko** | 17K+ crypto 價格/市值/volume | `curl "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"` | 免費零 key 5-15 req/min；免費 demo key 30 req/min |
| **Open-Meteo** | 天氣（1940 年至今）+ 氣候預測 | `curl "https://api.open-meteo.com/v1/forecast?latitude=43.65&longitude=-79.38&hourly=temperature_2m"` | 免費，零 key，10K req/day |
| **ip-api.com** | IP → 國家/城市/ISP | `curl "http://ip-api.com/json/8.8.8.8"` | 免費，零 key，45 req/min（HTTP only） |

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
| **Reddit .json** | User pain points、sentiment | Append `.json` to any Reddit URL，100 req/min |
| **Dev.to API** | Ecosystem 文章 | `mcp__devto__get_articles` |
| **Twitter API** | Mentions、sentiment | `$0.01/read`，API ready |
| **WebSearch / WebFetch** | General search + page fetch | Built-in |
| **HN Algolia API** | Full-text search 全部 HN history | `curl "http://hn.algolia.com/api/v1/search?query=..."` 免費 |
| **npm Downloads API** | Package download trends | `curl "https://api.npmjs.org/downloads/range/last-month/{pkg}"` 免費 |
| **Stack Overflow API** | Developer adoption trends | `curl "https://api.stackexchange.com/2.3/questions?tagged=...&site=stackoverflow"` 10K req/day free |
| **Wikipedia API** | Entity verification + pageviews | `curl "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=..."` 免費 |
| **Product Hunt API** | Competitor launches | GraphQL, free developer token |
| **Open Collective API** | OSS project funding data | GraphQL, 10 req/min free |

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
| ~~**ai-rss-feeds**~~ | ✅ Feed URLs 已搵到，用 rss-reader MCP subscribe（見下面 list） | — | — | — |
| ~~**Paper Agent**~~ | ❌ 唔用（1⭐，太新）。改用 **paper_claw**（28⭐，GH Actions + email） | — | `github.com/PigeonDan1/paper_claw` | — |

### 🔥 Must Install（Round 1 發現）

| Tool | 做咩用 | 成本 | 點裝 | 點解要裝 |
|------|--------|------|------|---------|
| **idea-reality-mcp** | Scan GitHub + HN + npm + PyPI + PH 搵現有競品，出 reality score 0-100 | 免費 | `github.com/mnemox-ai/idea-reality-mcp` | **專為 competitive analysis 設計** |
| **reddit-research-mcp** | Semantic search across 20K+ subreddits，唔使 Reddit API creds | 免費 | `github.com/king-of-the-grackles/reddit-research-mcp` | **免 API 嘅 Reddit deep research** |
| **free-web-search-ultimate** | 10+ engines（DuckDuckGo、Bing、Google、Brave、YouTube、Reddit、arXiv），零 API key | 免費 | `github.com/wd041216-bit/free-web-search-ultimate` | **永遠唔會用完 quota** |
| **newsmcp** | Real-time clustered news，hundreds of sources | 免費 | `npx -y @newsmcp/server` | **零成本 news monitoring** |
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
  → free-web-search-ultimate（10+ engines，零 key）
  → gh search repos（GitHub landscape）
  → npm search + npm Downloads API（package ecosystem）
  → WebSearch（built-in）

Agent B: User Pain Points — FREE
  → reddit-research-mcp / dialog（semantic search 20K+ subreddits）
  → Reddit .json（specific subreddit top posts）
  → Stack Overflow API（tagged questions volume）
  → free-web-search（"[category] problems frustrations reddit"）

Agent C: Market Trends + News — FREE
  → newsmcp（real-time clustered news）
  → google-trends（Google News RSS + Trends data）
  → Dev.to API（trending articles）
  → mcp-hn / HN Algolia API（search HN history）
  → rss-reader（competitor blog RSS feeds）

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
  → free-web-search（"[category] funding" "series A"）
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
| **Firecrawl** | 500 credits（lifetime！唔 reset） | 6 個月 normal use | 要畀 $16/mo（Hobby plan） |

### ⚠️ Firecrawl 係唯一真正會「用完」嘅

Firecrawl 500 credits 係 **lifetime，唔係每月**。用完就要 subscribe。策略：

```
慳 Firecrawl credits 嘅方法：
  1. 用 Tavily Extract 代替 Firecrawl Scrape（同樣抓 URL content，用 Tavily quota）
  2. 用 free-web-search 做 general search（唔好嘥 Firecrawl 做 search）
  3. Firecrawl 只用喺「要 crawl 成個 site」嘅場景（Map + Crawl）
  4. Single page → Tavily Extract。Multi-page → Firecrawl Crawl
```

### 免費替代 priority（當 paid tool quota 用完）

```
Tavily quota 用完 → free-web-search-ultimate（10+ engines，零 key）
Exa quota 用完   → free-web-search + Tavily Search
Firecrawl 用完   → Tavily Extract（single page）+ WebFetch（raw HTML）
Twitter 太貴     → free-web-search search Twitter（有 Twitter engine）
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
> **真正嘅 risk 只有 Firecrawl — 500 lifetime credits 用完就要 $16/mo。慳住用。**

---

## Sharpening Log

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
| Reddit .json | API | 100 req/min |
| HN Algolia | API | 零 key |
| npm Downloads API | API | 零 key |
| open-webSearch | MCP | 零 key，零 limit |
| mcp-youtube-transcript | MCP | 零 key |
| paper-search-mcp | MCP | 零 key（wraps free APIs） |
| paper-distill-mcp | MCP | 零 key（wraps free APIs） |
| arxiv-mcp-server | MCP | 零 key |
| newsmcp | MCP | 零 key |
| Context7 | MCP | 零 key |
| Dev.to API | MCP | 零 key |
| last30days（without keys） | Skill | 只有 web + HN |

**🟡 有 Free Quota（用完要付費，慳住用）：**

| Tool | Free Quota | 用完之後 | 每月 Reset？ |
|------|-----------|---------|:----------:|
| **Tavily** | 1000 credits/mo | $0.01/search | ✅ 每月 |
| **Exa** | $10 one-time | $0.007/search | ❌ one-time |
| **Firecrawl** | 500 credits lifetime ⚠️ | $16/mo Hobby | ❌ lifetime |
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
