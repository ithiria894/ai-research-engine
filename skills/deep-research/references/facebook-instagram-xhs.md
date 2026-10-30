# Facebook, Instagram, and Xiaohongshu research routes

Verified 2026-09-11. Use this reference whenever a question could benefit from
Facebook, Instagram, or Xiaohongshu/RedNote coverage. These are separate sources;
do not treat a web-search hit as equivalent to native platform search.

## Required routing order

Run discovery and native/structured retrieval as separate passes:

1. Discover candidate URLs with several search engines and language variants.
2. Use the best structured route below to search the platform itself.
3. Open promising posts and retrieve comments/replies where the route supports it.
4. Record each pass separately in the source coverage ledger. A login wall,
   CAPTCHA, 401/402/403, missing key, or parser failure is `FAILED`/`SKIPPED`, not
   `EMPTY`.

Do not install Agent Reach, OpenCLI, mcporter, or another third-party social MCP
for these routes. Codex already has the local read-only `xiaohongshu` MCP, backed
by `~/MyGithub/ai-research-engine/xhs_mcp_server.py`; other harnesses can use
`social-research.py` or direct HTTP as a compatibility fallback. Never export the
Agent Chrome cookie jar. Never like, follow, comment, post, or message during
research.

## Fast route table

| Need | First route | Fallback / special route |
|---|---|---|
| Broad Facebook/Instagram public-interest corpus | Meta Content Library API, only when the research program has approved access | ScrapeCreators + web discovery |
| Facebook Pages by name | Meta `GET /pages/search` when approved | Web discovery, then ScrapeCreators profile/posts/comments |
| Facebook public groups/posts/comments | ScrapeCreators | Agent Chrome read-only UI; Meta Content Library if approved |
| Facebook ads | Meta Ad Library API/UI | ScrapeCreators Ad Library endpoints |
| Facebook opted-in creators | Meta Creator Discovery, when brand/app eligible | ScrapeCreators profile/posts |
| Instagram keyword/profile/reel/hashtag/comments | ScrapeCreators | Web discovery + Agent Chrome read-only UI |
| Instagram first-party professional-account data | Instagram Graph API | ScrapeCreators for public accounts not owned by the app user |
| Xiaohongshu notes/details/comments | `social-research.py xhs-search` + `xhs-note` (`auto` chooses TikHub when funded, otherwise Agent Chrome) | Web discovery for extra recall |

## Zero-key discovery pass

Vary English, Traditional Chinese, Simplified Chinese, local slang, brand names,
product model numbers, and adverse terms. Examples:

```text
site:facebook.com "QUERY"
site:facebook.com/groups "QUERY"
site:instagram.com/p "QUERY"
site:instagram.com/reel "QUERY"
site:xiaohongshu.com/explore "QUERY_ZH"
site:xiaohongshu.com "QUERY_ZH" (翻车 OR 避雷 OR 真实测评 OR 半年后)
```

Search-engine results are leads. Retrieve the actual post before quoting it. If
the actual page is unavailable, cite the search result only as an indexed lead
and state that the content could not be verified.

## ScrapeCreators: practical Facebook and Instagram route

Credential: `SCRAPECREATORS_API_KEY` in
`~/.config/research-engine/keys.env`. Authentication is the `x-api-key` header.
The provider advertises 100 initial free credits, free cached results, credits
that do not expire, and no enforced rate limit; it recommends staying below 500
concurrent requests. Most listed routes cost one credit. Check the response's
`credits_charged` and `credits_remaining` fields; do not assume every route costs
one credit.

Use the generic one-shot client:

```bash
SR=~/MyGithub/ai-research-engine/social-research.py

# Instagram discovery
python3 "$SR" scrapecreators /v1/instagram/search query='QUERY'
python3 "$SR" scrapecreators /v1/instagram/search/hashtag hashtag='TAG' date_posted=last-month
python3 "$SR" scrapecreators /v2/instagram/reels/search query='QUERY' date_posted=last-month page=1
python3 "$SR" scrapecreators /v1/instagram/search/profiles query='QUERY'

# Instagram expansion
python3 "$SR" scrapecreators /v2/instagram/user/posts handle='HANDLE'
python3 "$SR" scrapecreators /v1/instagram/post url='POST_URL'
python3 "$SR" scrapecreators /v2/instagram/post/comments url='POST_URL'

# Facebook expansion
python3 "$SR" scrapecreators /v1/facebook/profile url='PAGE_OR_PROFILE_URL'
python3 "$SR" scrapecreators /v1/facebook/profile/posts url='PAGE_OR_PROFILE_URL'
python3 "$SR" scrapecreators /v1/facebook/group/posts url='GROUP_URL' sort_by=CHRONOLOGICAL
python3 "$SR" scrapecreators /v1/facebook/post url='POST_URL'
python3 "$SR" scrapecreators /v1/facebook/post/comments url='POST_URL'
python3 "$SR" scrapecreators /v1/facebook/events/search query='QUERY'
python3 "$SR" scrapecreators /v1/facebook/adLibrary/search/ads query='QUERY' country=CA status=ALL trim=true
```

Pagination rules:

- Pass the returned `cursor` to the next request when the endpoint exposes one.
- Instagram hashtag and reel keyword search use Google-indexed discovery and cap
  at page/cursor 11. This is not a complete Instagram corpus.
- Instagram comments is documented by the provider as approximately 90%
  successful. `include_replies=true` always costs 15 credits and can take about
  29 seconds; fetch replies only when the research question needs them.
- Stop only after another page produces no material new evidence, not after an
  arbitrary first page.

Official provider references:

- <https://docs.scrapecreators.com/openapi.json>
- <https://docs.scrapecreators.com/authentication>
- <https://docs.scrapecreators.com/v2/instagram/post/comments/>
- <https://scrapecreators.com/>

## Meta first-party routes: useful but narrower or controlled

### Meta Content Library and API

This is Meta's broad public-content research route. It includes Facebook Pages,
posts, public groups, events, profiles, comments, Marketplace listings and
fundraisers; Instagram accounts, posts, comments, fundraisers and channels; and
WhatsApp Channels. It can return up to 100,000 results per query and search over
100 fields.

It is not a normal internet API. Applications require affiliation with an
academic institution or a nonprofit whose primary purpose or core activity is
scientific or public-interest research. Applications are independently reviewed.
API work runs in Meta Secure Research Environment or SOMAR Virtual Data Enclave.
Meta states that its own secure environment has no access or computation fee.

Use it only for an approved research program. Never claim it is available merely
because the public documentation loads.

Official references:

- <https://transparency.meta.com/researchtools/meta-content-library/>
- <https://www.icpsr.umich.edu/sites/somar/meta-content-library>

### Facebook Pages

`GET https://graph.facebook.com/pages/search?q=QUERY&fields=id,name,location,link`
searches Page metadata. Competitive-analysis use without a logged-in app user
requires Page Public Content Access; live access requires App Review and business
verification. This searches Pages, not arbitrary Facebook posts or people.

Official references:

- <https://developers.facebook.com/documentation/pages-api/search-pages>
- <https://developers.facebook.com/docs/features-reference/page-public-content-access/>

### Facebook Creator Discovery

This can semantically search opted-in Facebook creators and inspect recent public
content/metrics. It is for eligible brands and partnership-ad workflows. It
requires a Business app, Facebook Login on behalf of a brand-admin user,
`facebook_creator_marketplace_discovery`, `pages_show_list`, a Page access token,
and Advanced Access after App Review. Standard Access returns mock creator data.
Creators must have opted into data sharing, so this is not full Facebook search.

Official reference:

- <https://developers.facebook.com/documentation/fb-creator-discovery>

### Instagram Graph API

Useful first-party reads:

- Hashtag Search finds public media for up to 30 unique hashtags per Instagram
  Business/Creator account in a rolling seven-day period. It requires App Review,
  Instagram Public Content Access, and `instagram_basic`.
- Business Discovery retrieves public fields/media for a named professional
  Business/Creator account through the app user's professional account.
- Instagram Login manages the app user's professional account; it is not a
  consumer-account or general keyword-search API.

Official references:

- <https://developers.facebook.com/docs/instagram-api/guides/hashtag-search/>
- <https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/business-discovery>
- <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/>

### Meta Ad Library

Use the official Ad Library UI/API for ad and competitor-ad questions. It can
search political/social-issue ads globally for the retained period and broader
ads where Meta makes them available. It requires a Facebook account, identity and
location confirmation, a developer account, and a token for API use.

Official reference:

- <https://www.facebook.com/ads/library/api/>

Do not plan new work on the old Facebook Groups API; Meta removed the Groups API
permissions/features for all versions on 2024-04-22. Use Content Library (approved
research), a public-data provider, or controlled browser reading instead.

## Xiaohongshu: direct paid API plus local browser fallback

Xiaohongshu's official Open Platform currently exposes authorization/basic-user,
sharing, mini-app, merchant and related business capabilities. Its published API
reference does not expose public note keyword search or comment retrieval.

Official references:

- <https://openaccount.xiaohongshu.com/docs/api-reference>
- <https://miniapp.xiaohongshu.com/doc/DC591932>

### Direct CLI (same for Claude and Codex, no MCP)

```bash
SR=~/MyGithub/ai-research-engine/social-research.py
python3 $SR xhs-search '咖啡' --route browser              # also a login probe
python3 $SR xhs-search 'QUERY_ZH' --route auto             # returns id + xsec_token per note
python3 $SR xhs-note NOTE_ID XSEC_TOKEN --route auto --comment-limit 20
```

`xhs-note` exits non-zero (no stdout) when XHS redirects away from the note: deleted or
private note, expired `xsec_token`, or login needed. Never record that as an empty note.
2026-10-30: Agent Chrome's XHS session had expired ("XHS requires login"); Nicole has to
log in once by hand before the browser route works. Codex uses the same CLI (its `xiaohongshu-research` skill was rewritten 2026-10-30). The old gateway
MCP wrapper was removed from `~/.config/1mcp/mcp.json` and archived as `archive/xhs_mcp_server.py`.

Search with materially different Simplified-Chinese variants: the core subject,
`攻略`, `教程`, `真实体验`, and adverse terms such as `避雷`, `翻车`, `缺点`,
or `后悔`. Deduplicate by note ID, then open relevant notes; search-card titles
are discovery leads rather than verified note content.

The `auto` route uses TikHub only when `TIKHUB_API_KEY` is configured; otherwise it
reuses Agent Chrome on port 9223. It never returns credentials or browser cookies.

### TikHub direct REST

Credential: `TIKHUB_API_KEY` in `keys.env`; authentication is
`Authorization: Bearer ...`. On 2026-09-11 TikHub's own endpoint-information API
reported US$0.01/request and 10 requests/second for XHS search, detail, and comments;
these endpoints do not accept its free trial credit.

```bash
SR=~/MyGithub/ai-research-engine/social-research.py

# Convenience command: TikHub when key exists; otherwise Agent Chrome
python3 "$SR" xhs-search 'QUERY_ZH' --route auto --page 1 --sort general

# Direct generic calls
python3 "$SR" tikhub /api/v1/xiaohongshu/app_v2/search_notes keyword='QUERY_ZH' page=1 sort_type=general note_type=不限 time_filter=不限
python3 "$SR" tikhub /api/v1/xiaohongshu/web_v3/fetch_note_detail note_id='NOTE_ID' xsec_token='XSEC_TOKEN'
python3 "$SR" tikhub /api/v1/xiaohongshu/web_v3/fetch_note_comments note_id='NOTE_ID' cursor=''
```

Supported search sort values include `general`, `time_descending`,
`popularity_descending`, `comment_descending`, and `collect_descending`. Paginate
and preserve `note_id` plus `xsec_token` for expansion.

Official provider references:

- <https://docs.tikhub.io/420136398e0>
- <https://github.com/TikHub/TikHub-API-Python-SDK/blob/main/docs/reference.md>

### Agent Chrome fallback

```bash
python3 ~/MyGithub/ai-research-engine/social-research.py xhs-search 'QUERY_ZH' --route browser
```

This reuses the dedicated Agent Chrome profile on port 9223 and reads
`window.__INITIAL_STATE__.search.feeds`, the same core technique used by the
reviewed `xpzouying/xiaohongshu-mcp` source. It opens and closes one temporary
tab, returns compact JSON, and does not copy cookies.

Browser search is currently first-page discovery. The installed MCP can also
open a selected note and return its body, engagement fields, images, and the
comments present in the page's initial state. State the comment-depth limit.
For exhaustive comment pagination, prefer TikHub when configured. CAPTCHA or
login failure is a failed route and must be shown in the ledger.

Reviewed source references:

- `~/MyGithub/xiaohongshu-mcp/xiaohongshu/search.go`
- `~/MyGithub/xiaohongshu-mcp/xiaohongshu/feed_detail.go`
- <https://github.com/xpzouying/xiaohongshu-mcp>

## Coverage and synthesis rules

- For reputation, safety, medical, shopping, or market-gap research, search both
  positive and adverse vocabulary and read comments, not only post captions.
- Facebook/Instagram/XHS ranking is personalized and incomplete. Preserve query,
  route, filters, page/cursor, timestamp, returned count, and exact URL.
- Do not infer prevalence from raw result counts across different routes. They
  have different indexes and ranking rules.
- Deduplicate cross-posts by canonical URL/content identity, while preserving
  independent comments as separate evidence.
- Clearly distinguish official first-party data, provider-returned public data,
  browser-rendered data, search-engine snippets, and inference.
