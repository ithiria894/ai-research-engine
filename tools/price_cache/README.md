# price_cache: one shared local price store for all investment research

Every study used to download its own Yahoo history into its own folder. The same ticker was fetched
three or four times, and several agents hit Yahoo at once and got 429s. This tool keeps one copy of each
symbol's bars on disk and sends every new Yahoo request through one rate limiter that all processes on
the machine share.

No paid sources. Code lives here; data lives in `~/data/price-cache/`.

## Conflict rule (decided before the first import)

1. When two fetches of the same symbol and interval have bars on the same date, compare `adjclose`
   (`close` if either side has no adjclose). A difference above **0.5 %** is a conflict.
2. Every conflict date is written to the ledger and exported to `conflicts/conflicts.parquet`, with
   **both values**, both fetch ids, both fetch times, and the winning fetch id. A summary line goes to
   the log.
3. The **newer fetch wins** that date.
4. Yahoo rescales all history before an ex-dividend date (and splits rescale `close` too), so two
   honest fetches made a month apart disagree by a constant factor. Before stitching, the older side is
   rescaled onto the newer fetch's basis using the per-date ratio on the overlapping dates (rolling
   median over 11 dates, nearest-date lookup). Each conflict row therefore also carries
   `rel_diff_after_rebase` and `kind`: `scale` means the gap disappears after rebasing (a corporate
   action between the two fetches), `value` means the numbers really disagree. Both kinds are kept.
5. If two fetches do not overlap at all they are stitched without rebasing and the log says
   `no overlap`.

## For agents: paste this into briefs

> Price data: do NOT call Yahoo (or yfinance) directly and do not save your own copy of price history.
> Use the shared cache: `import os, sys; sys.path.insert(0, os.path.expanduser("~/MyGithub/ai-research-engine/tools/price_cache")); from price_cache import get, bulk_get`.
> `get("AAPL", "2015-01-01", "2024-12-31")` returns a polars DataFrame with columns
> date, open, high, low, close, adjclose, volume, dividends, splits, fetch_id (`pandas=True` for pandas).
> It reads `~/data/price-cache/` and only downloads date ranges nobody has fetched yet, through a
> machine-wide limit of 1 request per second. `bulk_get([...])` does many symbols. `offline=True` never
> touches the network. A Yahoo 404 is remembered for 30 days (you get an empty frame). For symbols Yahoo
> does not have, `get(sym, source="any")` adds rows from free secondary sources, tagged in a `source`
> column; never mix them into Yahoo numbers without saying so. CLI: `python3 .../price_cache.py get SYM`.

## Library

```python
import os, sys; sys.path.insert(0, os.path.expanduser("~/MyGithub/ai-research-engine/tools/price_cache"))
from price_cache import get, bulk_get

df = get("SPY", "2000-01-01", "2026-11-10")              # 1d, Yahoo only
wk = get("XIU.TO", interval="1wk")                        # 1d / 1wk / 1mo / 1h
h  = get("^GSPC", "2026-10-01", interval="1h")            # Yahoo keeps ~730 days of 1h
d  = bulk_get(["AAPL", "MSFT", "BRK-B"], "2010-01-01")   # {symbol: frame}
lf = bulk_get(["AAPL", "MSFT"], "2010-01-01", long=True)  # one frame with a symbol column
x  = get("SOMEDELISTED", source="any")                    # Yahoo + secondary rows, `source` column
```

What `get` does, step by step:

1. Upper-cases the symbol and looks it up in the alias table (`BRK.B` style names a study requested
   that Yahoo returned under another symbol).
2. Takes a per-symbol file lock. If another process is fetching the same symbol, this one waits and then
   finds the data already there, so a ticker is never downloaded twice at the same time.
3. Works out which part of `[start, end]` no recorded fetch covers. Each fetch covers from its requested
   start (or from 1900 when the first bar is the listing date) to the day before it was made. A fetch
   less than 12 hours old counts as covering up to now. A gap made only of a weekend is ignored for
   non-crypto symbols. A Yahoo 404 in the last 30 days means no fetch.
4. If there is a gap, it makes one request spanning all gaps plus 21 days of padding into cached data, so
   the new and old adjustment bases can be reconciled. The request waits for a token from the
   machine-wide limiter. A 429 makes every process pause (30 s, doubling, max 10 min). 5xx and network
   errors back off on their own. query1 and query2 alternate between attempts, up to 7 attempts.
5. The raw response is saved gzip under `raw/yahoo/<interval>/<symbol>/<time>.json.gz`, parsed, its
   still-open bar dropped (today's daily bar, this week's weekly bar, the current hour), merged with the
   conflict rule above, and written atomically.
6. Returns the requested slice.

## CLI

```
cd ~/MyGithub/ai-research-engine/tools/price_cache
python3 price_cache.py import-existing [--min-age-min 10] [--only NAME] [--no-discover]
python3 price_cache.py status            # counts, sizes, conflicts; also refreshes meta.parquet
python3 price_cache.py get SPY --start 2020-01-01 [--interval 1d] [--offline] [--source any]
python3 price_cache.py missing-report    # symbols the studies referenced that have no Yahoo 1d bars
python3 price_cache.py export-meta
python3 price_cache.py kaggle-import borismarjanovic/price-volume-data-for-all-us-stocks-etfs [--only-missing]
python3 price_cache.py fmp-fill [--limit 20] [SYMBOL ...]   # needs FMP_API_KEY or PRICE_CACHE_FMP_KEY_CMD
```

`import-existing` reads the list of folders from `<cache root>/import_sources.json` (or
`$PRICE_CACHE_SOURCES`). That file is machine-specific and stays out of this repo; the format is in
`import_sources.example.json`. Each source says which globs to read, how a file name maps to a ticker,
which `period1` the study requested (so coverage starts at the right date), whether it asked for
dividend/split events, and where the study's own fetch log is (for the true `fetched_at`; file mtime
otherwise). A `discover` block walks extra trees for any other Yahoo chart JSON and imports it as
`discovered:<dir>`. A `referenced` block lists each study's input symbol lists for `missing-report`.

`import-existing` is read-only towards the source folders and safe to re-run. It skips files already
imported (same path with same size and mtime, or same sha256) and files modified in the last 10 minutes,
because other agents may still be writing them. Run it again later to pick those up.

## Layout of `~/data/price-cache/`

| Path | What |
|---|---|
| `bars/<interval>/<symbol>.parquet` | Yahoo bars, one file per symbol. Names are URL-quoted (`^GSPC` becomes `%5EGSPC`, `GC=F` becomes `GC%3DF`). Daily key is the exchange-local `date`; hourly key is `ts` (UTC). |
| `secondary/<source>/<interval>/<symbol>.parquet` | Non-Yahoo sources (`binance`, `kaggle__<owner>__<dataset>`, `fmp`). Kept apart from Yahoo files. |
| `ledger.sqlite` | Source of truth: `fetches` (every imported file and network fetch: path, sha256, size, mtime, fetched_at, coverage, currency, exchange), `requests` (every HTTP request, status, bytes, ms), `conflicts`, `aliases`. SQLite in WAL mode because many processes write at once and Parquet cannot be appended safely. |
| `meta.parquet` | Snapshot, one row per symbol x interval x source: first/last date, latest fetched_at, all original file paths and their sha256, currency, exchange, conflict count. Refreshed by `status`, `import-existing`, `export-meta`. |
| `fetches.parquet`, `conflicts/conflicts.parquet` | Snapshots of the ledger tables. |
| `raw/` | Raw bodies of fetches this tool made itself (gzip), plus downloaded Kaggle archives. Imported files are not copied; the ledger keeps their original path and sha256. |
| `.lock`, `.ratelimit.json` | Machine-wide limiter (flock + token bucket state). |
| `locks/` | Per-symbol locks. |
| `logs/price_cache-YYYY-MM-DD.log` | Every get, gap decision, HTTP request, merge, conflict and import. |
| `reports/` | `missing-report` output. |

Columns of a daily bar file: `date, open, high, low, close, adjclose, volume, dividends, splits,
fetch_id`. `close` is Yahoo's split-adjusted close, `adjclose` is split and dividend adjusted.
`dividends` is the cash amount on the ex-date and `splits` the split ratio (0 when none). Both are null
when the original request did not ask for events. `fetch_id` points at the `fetches` row each bar came
from.

Settings: `PRICE_CACHE_ROOT` (default `~/data/price-cache`), `PRICE_CACHE_RATE_PER_S` (default 1.0),
`PRICE_CACHE_QUIET=1` (warnings only on stderr), `PRICE_CACHE_SOURCES` (import config path),
`FMP_API_KEY` or `PRICE_CACHE_FMP_KEY_CMD` (a command that prints the key).

## Sources

Every non-Yahoo row lives under `secondary/<source>/` with its own ledger rows (source name, file or
zip member, sha256, dataset version date as `fetched_at`). `get()` returns Yahoo only unless you pass
`source="any"`, and then each row says where it came from.

| Source | What it is | Notes |
|---|---|---|
| `yahoo` | v8 chart API, query1/query2, `User-Agent: Mozilla/5.0` | The canonical series. |
| `binance` | public spot klines (1h) imported from earlier downloads | Crypto pairs such as BTCUSDT. No adjclose. |
| `kaggle:borismarjanovic/price-volume-data-for-all-us-stocks-etfs` | "Huge Stock Market Dataset", US stocks + ETFs, ends 2017-11-10 | Its `close` behaves like an adjusted close on a 2017 basis: against Yahoo, the ratio to Yahoo `adjclose` varies less within a symbol (median CV 0.013) than the ratio to Yahoo `close` (0.033). `adjclose` is left null. |
| `kaggle:jacksoncrow/stock-market-dataset` | NASDAQ-traded stocks + ETFs as of 2020-04-01 (yfinance) | `close` equals Yahoo `close` for 83 % of 3,038 shared symbols (CV 0.0). `adjclose` is on the 2020 basis, so it only matches today's Yahoo `adjclose` for 27 %. Rebase it before you mix it with Yahoo. |
| `kaggle:ehallmar/daily-historical-stock-prices-1970-2018` | NYSE + NASDAQ, 1970 to 2018-08-24 | `close` equals Yahoo `close` for 82 % of 2,487 shared symbols. Same stale-basis caveat for `adjclose`. |
| `fmp` | Financial Modeling Prep free tier, `historical-price-eod/full` | 250 calls/day (a 429 "Limit Reach" came at about call 250). The free plan returns only about 5 years (from 2021-11-12) and answers 402 for most delisted symbols. |

Kaggle files are matched to Yahoo symbols by ticker string only. A ticker that was reused by a different
company after the dataset was made matches the wrong history, so check the name or dates before you
rely on a secondary-only series. `analysis/verify_secondary.py` recomputes the ratios above.

## Coverage after the first import (2026-11-11)

Measured with `analysis/coverage_summary.py` and `missing-report`.

- Imported 21,266 existing Yahoo files from 10 configured local folders: 9,120 with bars, 11,414 Yahoo
  404 bodies (kept as negative cache), 732 empty results. 7,412 symbols have daily bars, 13 weekly, 43
  monthly, 11 hourly. Plus 8 Binance hourly chunk files (2 pairs).
- 1,430 symbols had daily bars in two or more of those files, so studies had downloaded them more than
  once. The cache now holds each of them once.
- Overlap check: 908 merges shared 3.9 million dates. **0 conflicts** over 0.5 %. An independent
  re-read of the original files (`analysis/crosscheck_raw_overlaps.py`, 300 symbols / 329 file pairs,
  1.4 million shared dates) agrees: worst difference 0.0002 %. That is expected because all of these
  downloads were made within about two days of each other.
- 10,024 symbols are only known as Yahoo 404 or empty. Free secondary sources cover 2,209 of them:
  Kaggle boris 1,909, ehallmar 1,623, jacksoncrow 1,444 (overlapping), FMP 2.
- For an event study with several candidate tickers per event, `missing-report` counts events whose
  date falls inside a candidate's data span. On the largest study (371,153 events) that went from
  199,560 with Yahoo alone to 273,143 with Yahoo or secondary data.
- Size on disk 3.2 GB: bars 473 MB, secondary 1.2 GB, Kaggle zips 1.5 GB, ledger 34 MB.
- Some folders were still being written during the import. The files modified in the last 10 minutes
  were skipped, and a re-run picks them up.

## Tests

```
cd ~/MyGithub/ai-research-engine/tools/price_cache && python3 -m pytest -q tests/
```

No test touches the network. By default they generate Yahoo-format SPY and QQQ files; set
`PRICE_CACHE_TEST_REAL_FILES=/path/yahoo_SPY.json,/path/yahoo_QQQ.json` to run the same checks on real
downloads. They import those two symbols into a temporary root and check
the schema and meta. They check that a second `get` makes zero network calls, that a missing range is
fetched once and then served from cache, that a 404 is negatively cached, and that a 429 retries on the
other host. They check that a rebase and a value conflict are both recorded, that an older import after
a newer one keeps the newer basis, and that 5 processes x 4 requests never get two tokens closer than
1/rate. They check a config-driven `import-existing`: a file modified in the last 10 minutes is
skipped and picked up on the next run, a re-run imports nothing, and a 404 body becomes a negative-cache
entry. A Kaggle-format zip lands under `secondary/` only, and `source="any"` tags its rows. They also check that 4 processes asking for the same missing symbol cause exactly one download.
I mutation-checked the limiter, rebase and lock tests: removing the limiter sleep or flipping the rebase
side makes them fail.
