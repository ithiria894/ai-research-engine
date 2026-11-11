# forward_snapshot：每星期影相，留住會消失嘅公開數據

為 2026-11-11 預先登記嘅向前驗證（PersonalDoc `financial/reports/investing/kol-research-2026-11/預先登記-2026-11-11.md`
「要每星期影相嘅會消失來源」）而寫。啲網站只會顯示「而家」，唔留舊版，所以每星期自己存一份 raw。

## 存啲乜

| source（ledger 名） | 攞乜 | 點攞 |
|---|---|---|
| `etoro` | 公開排行頭 6 頁 × 100 人（`sort=-gain&period=OneYearAgo&verified=true`，即係 hidden-gold-2026-11 用過、HTTP 200 嗰條 query），再逐個人攞 `/sapi/userstats/gain/cid/<id>/history`（每月／每年回報） | curl，每人之間停 1.5 秒，大約 18 分鐘 |
| `polymarket` | Data API v2 leaderboard，PNL 榜，`all` / `month` / `week` 各頭 5,000 行（5 頁 × 1000，跟 `next_cursor`） | curl，每頁停 2 秒 |
| `cryptokrios` | `/creators` 清單頁，再攞清單上每一個 `/creators/<slug>`（每頁內嵌最新最多 5 個預測 `recentPredictions`）。預先登記嗰 10 個唔喺清單都照攞 | curl，每頁停 2 秒；如果頁面冇 `recentPredictions` 先用 agent Chrome（CDP port file `~/.config/agent-chrome/DevToolsActivePort`），Chrome 冇開就記 FAILED，唔會自己開瀏覽器 |
| `youtube_lists` | 名單 A 每個頻道 `/videos` 同 `/streams` 兩個 tab 最新 30 條（`yt-dlp --flat-playlist -J --extractor-args youtubetab:approximate_date`） | 每個 tab 之間停 3 秒 |
| `youtube_upload_dates` | 未有準確上載日期嘅片，逐條用 yt-dlp 攞 `upload_date`，然後將今日嘅清單 append 落每個頻道嘅 CSV | 每條停 3 秒；連續 3 次撞 YouTube「Sign in to confirm you're not a bot」就停手，嗰次餘下嘅片記 `NOT_ATTEMPTED`，下星期再試 |

`/shorts` 冇攞。`approx_timestamp_utc` 係由「N days ago」推出嚟嘅大約時間，**唔係**準確上載時間；準確日期喺 `upload_date` 欄，
攞唔到就係空白，`upload_date_source` 會寫 `FAILED: <原因>`。

## 頻道對照（做一次）

`~/data/forward-snapshots/youtube/channel_map.tsv`，由 `forward_snapshot.py resolve` 產生，每行都寫咗點搵到、證據係乜：

- CryptoKrios 10 個：CryptoKrios creator 頁自己嘅 `youtubeUrl`
- YouTuberStocks 10 個：BullVox 排名文章嘅連結 → `/youtuber/<slug>/` profile 頁顯示嘅 `youtube.com/@handle`。
  `@elartedeinvertir` 同 `@FelixFriends` 喺 YouTube 係 404，所以改用嗰個 profile 頁列出嘅片 ID，
  經 YouTube oEmbed 睇上載者（3 條片全部同一個先接受）→ `@Artedeinvertir`、`@FelixPrehn`
- **Financial Education：UNRESOLVED，唔會影。** BullVox profile 頁 404，手頭冇任何片 ID 或者 handle，冇估
- 提阿非羅大人TiaBTC：`KOL準確度-原始收集.md` 記低嘅 channel ID `UCy2h-yNK9OF1kXDtT3AlF3Q`

每個解到嘅 URL 都用 yt-dlp 實際開過一次，`channel_id` 同 `channel_title_seen` 係 YouTube 當時返嘅值。重做：`resolve --force`。

## 擺喺邊

```
~/data/forward-snapshots/
  LEDGER.tsv                          每次 run 每個 source 一行
  <source>/<YYYY-MM-DD>/              日期係 UTC；raw 檔全部 .gz（gzip 原 bytes，冇改內容）+ MANIFEST.json
  <source>/<日期>.attempt-HHMMSS/     同一日之前失敗嗰次（保留，唔刪）
  youtube/channel_map.tsv             頻道對照
  youtube/videos/<key>.csv            每個頻道一個，append-only
  youtube_upload_dates/upload_dates.tsv  已攞到嘅準確上載日期（cache，唔會重複問 YouTube）
  logs/<YYYY-MM-DD>.log               完整 log（每個 request、每個決定、每個錯）
```

`MANIFEST.json` 逐個檔記低 URL、HTTP status、攞嘅時間、raw bytes 同 raw sha256。Ledger 嘅 `manifest_sha256` 係成個 MANIFEST.json 嘅 sha256。

## Ledger 點睇

欄：`timestamp_utc  source  status  files  bytes  manifest_sha256  dir  error`

- `OK`：全部 request 成功
- `EMPTY`：request 成功但真係冇嘢（例如一個 channel 都冇解到）
- `FAILED`：有任何 request 失敗、磁碟唔夠、或者程式出錯。`error` 欄寫真嘅錯誤（HTTP code、curl／yt-dlp 訊息）。
  **攞唔到永遠記 FAILED，唔會記 EMPTY。** 有部分檔都照存，可以睇 MANIFEST.json

```bash
python3 ~/MyGithub/ai-research-engine/tools/forward_snapshot.py status      # 每個 source 最近一行
column -t -s$'\t' ~/data/forward-snapshots/LEDGER.tsv | less -S
zcat ~/data/forward-snapshots/polymarket/<日期>/leaderboard_pnl_week_p1.json.gz | head -c 500
```

## 手動 run

```bash
python3 ~/MyGithub/ai-research-engine/tools/forward_snapshot.py run                    # 全部
python3 ~/MyGithub/ai-research-engine/tools/forward_snapshot.py run --only etoro       # 一個或幾個（逗號分隔）
python3 ~/MyGithub/ai-research-engine/tools/forward_snapshot.py run --only etoro --force   # 今日已經 OK 都重新攞
systemctl --user start forward-snapshot.service                                        # 經 systemd 跑一次
```

同一日再 run：已經 `OK`／`EMPTY` 嘅 source 會跳過、唔加 ledger 行；之前 `FAILED` 嘅會重試，舊嗰份改名做 `.attempt-*` 保留。
一個 source 壞咗唔會阻住其他（四組平行跑，YouTube 兩步係先後）。有 lock file，兩個 run 唔會同時行。
磁碟剩低少過 20 GB 就唔攞，每個 source 記一行 FAILED。

QA：`python3 ~/MyGithub/ai-research-engine/tools/forward_snapshot_qa.py`（用臨時目錄，唔掂真 ledger；Polymarket 只攞 3 頁）。
測咗：磁碟唔夠、upstream 404 → FAILED、失敗後重試、manifest sha256、同日重跑唔重複、YouTube 冇清單 → FAILED、0 個頻道 → EMPTY、兩個 run 同時開。

## 排程

`forward-snapshot.timer`：逢星期一 09:00（本地時間），`Persistent=true`（部機嗰陣熄咗，開機會補跑）。
`forward-snapshot.service`：`Type=oneshot`，`Nice=10`，`TimeoutStartSec=4h`。Unit 檔正本喺 `tools/systemd/`，複製咗去 `~/.config/systemd/user/`。

```bash
systemctl --user list-timers forward-snapshot.timer
journalctl --user -u forward-snapshot.service -n 50
```

## 停用

```bash
systemctl --user disable --now forward-snapshot.timer      # 停排程（數據唔郁）
systemctl --user enable --now forward-snapshot.timer       # 開返
```

## 備份

**冇同步去任何地方。** Reddit archive 嘅 sync（`reddit_archive_sync.sh`）係 `~/data/reddit-archive` 自己嘅 git repo
（私人 repo `ithiria894/reddit-archive`），淨係 push 嗰個目錄嘅 `.zst`。要將 forward-snapshots 加入去，就要將另一個
project 嘅數據塞入 reddit 嗰個 repo，或者開一個新 repo，兩樣都唔係「加一個 folder」咁簡單，所以冇做。
要備份嘅話，建議開一個新私人 repo `forward-snapshots`，用同一個 sync 寫法。

## 已知限制

- eToro 排行嘅「default sort」係用返之前成功嗰條 query（`-gain`，一年）；未核對過 eToro 網頁 UI 本身預設係咪一樣。
- YouTube 準確上載日期：2026-11-11 呢部機嘅 IP 開單條片會被要求登入（bot check），flat-playlist 就冇事。我哋唔登入、唔用 cookies，
  所以攞唔到嗰陣日期欄留空，下星期再試。
- CryptoKrios 每個頻道只顯示最新最多 5 個預測，一星期講多過 5 個就會漏。
