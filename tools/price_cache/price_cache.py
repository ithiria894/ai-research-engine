#!/usr/bin/env python3
"""Shared machine-wide price cache (daily first; weekly/monthly/hourly supported).

One Parquet per symbol per interval under ~/data/price-cache/bars/<interval>/, a SQLite ledger
(ledger.sqlite: every fetch / import / HTTP request / conflict), and exported snapshots meta.parquet,
fetches.parquet, conflicts/conflicts.parquet. Missing date ranges are fetched from the Yahoo chart API
through ONE rate limiter shared by every process on the machine (flock on ~/data/price-cache/.lock +
token bucket, default 1 request/second total).

Library:  from price_cache import get, bulk_get
CLI:      python3 price_cache.py import-existing | status | get SYMBOL | export-meta | missing-report
Root can be overridden with env PRICE_CACHE_ROOT (tests use this). See README.md.
"""
from __future__ import annotations

import argparse
import fcntl
import gzip
import hashlib
import json
import logging
import os
import random
import sqlite3
import sys
import time
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import polars as pl

# ----------------------------------------------------------------------------------------------- config
UA = "Mozilla/5.0"  # 2026-11-10: a long Chrome UA string got HTTP 429 where plain "Mozilla/5.0" got 200
HOSTS = ("query1", "query2")
CONFLICT_REL = 0.005  # > 0.5 % disagreement on adjclose (close when no adjclose) = conflict
MAX_AGE_HOURS = 12.0  # a fetch younger than this counts as covering "up to now" (stops re-fetching today's bar)
NOT_FOUND_RETRY_DAYS = 30  # a Yahoo 404 is trusted this long before we ask again
PAD_DAYS = 21  # gap fetches extend this far into cached data so new/old adjustment bases can be reconciled
MAX_ATTEMPTS = 7
INTERVALS = ("1d", "1wk", "1mo", "1h")
EPOCH_START = date(1900, 1, 1)
PRICE_COLS = ["open", "high", "low", "close", "adjclose"]
DAILY_SCHEMA: dict[str, Any] = {
    "date": pl.Date, "open": pl.Float64, "high": pl.Float64, "low": pl.Float64, "close": pl.Float64,
    "adjclose": pl.Float64, "volume": pl.Float64, "dividends": pl.Float64, "splits": pl.Float64,
    "fetch_id": pl.Int64,
}
HOURLY_SCHEMA: dict[str, Any] = {"ts": pl.Datetime("us", "UTC"), **{k: v for k, v in DAILY_SCHEMA.items() if k != "date"}}


def root() -> Path:
    """Cache root, re-read from env on every call so tests can point it elsewhere."""
    return Path(os.environ.get("PRICE_CACHE_ROOT", "~/data/price-cache")).expanduser()


def rate_per_s() -> float:
    return float(os.environ.get("PRICE_CACHE_RATE_PER_S", "1.0"))


def key_col(interval: str) -> str:
    return "ts" if interval == "1h" else "date"


def schema_for(interval: str) -> dict[str, Any]:
    return HOURLY_SCHEMA if interval == "1h" else DAILY_SCHEMA


def norm_interval(g: str | None) -> str | None:
    if g is None:
        return None
    return {"60m": "1h", "1h": "1h", "1d": "1d", "1wk": "1wk", "1mo": "1mo", "5d": "5d", "3mo": "3mo"}.get(g, g)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def to_date(x: Any) -> date | None:
    if x is None:
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


def canon(symbol: str) -> str:
    return symbol.strip().upper()


def qname(symbol: str) -> str:
    """Reversible filesystem-safe name: ^GSPC -> %5EGSPC, GC=F -> GC%3DF."""
    return urllib.parse.quote(symbol, safe="")


def source_slug(source: str) -> str:
    return source.replace(":", "__").replace("/", "__")


def bars_path(symbol: str, interval: str, source: str = "yahoo") -> Path:
    if source == "yahoo":
        return root() / "bars" / interval / f"{qname(symbol)}.parquet"
    return root() / "secondary" / source_slug(source) / interval / f"{qname(symbol)}.parquet"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------------------------------------------------------------------------- logging
_LOG: logging.Logger | None = None
_LOG_ROOT: Path | None = None


def log() -> logging.Logger:
    """One logger per process; file under <root>/logs/price_cache-YYYY-MM-DD.log (append, multi-process safe)."""
    global _LOG, _LOG_ROOT
    if _LOG is not None and _LOG_ROOT == root():
        return _LOG
    d = root() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger(f"price_cache:{root()}")
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    for h in list(lg.handlers):
        lg.removeHandler(h)
    fh = logging.FileHandler(d / f"price_cache-{utcnow():%Y-%m-%d}.log")
    fh.setFormatter(logging.Formatter("%(asctime)s pid=%(process)d %(levelname)s %(message)s"))
    lg.addHandler(fh)
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING if os.environ.get("PRICE_CACHE_QUIET") else logging.INFO)
    sh.setFormatter(logging.Formatter("price_cache %(levelname)s %(message)s"))
    lg.addHandler(sh)
    _LOG, _LOG_ROOT = lg, root()
    return lg


# ----------------------------------------------------------------------------------------------- ledger
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS fetches (
  fetch_id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL, requested_symbol TEXT, interval TEXT, source TEXT NOT NULL, origin TEXT NOT NULL,
  import_source TEXT, path TEXT, sha256 TEXT, size INTEGER, mtime REAL,
  fetched_at_utc TEXT, fetched_at_basis TEXT, status TEXT NOT NULL, state TEXT NOT NULL,
  n_rows INTEGER, n_dropped_provisional INTEGER, first_key TEXT, last_key TEXT, cover_start TEXT, cover_end TEXT,
  currency TEXT, exchange TEXT, exchange_code TEXT, instrument_type TEXT, timezone TEXT, long_name TEXT,
  has_events INTEGER, granularity TEXT, url TEXT, imported_at_utc TEXT, note TEXT
);
CREATE INDEX IF NOT EXISTS ix_f_sym ON fetches(symbol, interval, source);
CREATE INDEX IF NOT EXISTS ix_f_path ON fetches(path);
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts_utc TEXT, pid INTEGER, service TEXT, url TEXT, symbol TEXT,
  interval TEXT, attempt INTEGER, http_status INTEGER, bytes INTEGER, elapsed_ms INTEGER, error TEXT
);
CREATE TABLE IF NOT EXISTS conflicts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, interval TEXT, source TEXT, key TEXT, field TEXT,
  value_existing REAL, value_new REAL, fetch_id_existing INTEGER, fetch_id_new INTEGER,
  fetched_at_existing TEXT, fetched_at_new TEXT, rel_diff_raw REAL, rel_diff_after_rebase REAL,
  kind TEXT, winner_fetch_id INTEGER, detected_at_utc TEXT
);
CREATE INDEX IF NOT EXISTS ix_c_sym ON conflicts(symbol, interval);
CREATE TABLE IF NOT EXISTS aliases (alias TEXT PRIMARY KEY, symbol TEXT NOT NULL, source TEXT, created_at_utc TEXT);
"""


_DDL_DONE: dict[str, bool] = {}


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    root().mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(root() / "ledger.sqlite", timeout=300, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA busy_timeout=300000")
        if _DDL_DONE.get(str(root())) is None:  # schema + WAL once per process per root
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(LEDGER_DDL)
            _DDL_DONE[str(root())] = True
        yield con
    finally:
        con.close()


def insert_row(con: sqlite3.Connection, table: str, row: dict[str, Any]) -> int:
    cols = ",".join(row)
    q = ",".join("?" * len(row))
    cur = con.execute(f"INSERT INTO {table} ({cols}) VALUES ({q})", list(row.values()))
    return int(cur.lastrowid)


def resolve(symbol: str) -> str:
    s = canon(symbol)
    with db() as con:
        r = con.execute("SELECT symbol FROM aliases WHERE alias=?", (s,)).fetchone()
    return r["symbol"] if r else s


def add_alias(alias: str, symbol: str, source: str) -> None:
    a, s = canon(alias), canon(symbol)
    if a == s:
        return
    with db() as con:
        con.execute("INSERT OR IGNORE INTO aliases(alias, symbol, source, created_at_utc) VALUES (?,?,?,?)",
                    (a, s, source, iso(utcnow())))


# ----------------------------------------------------------------------------------------------- locks + limiter
@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def symbol_lock(symbol: str, interval: str, source: str = "yahoo"):
    """Per-symbol read-modify-write lock; also stops two processes fetching the same symbol at once."""
    return file_lock(root() / "locks" / source_slug(source) / interval / f"{qname(symbol)}.lock")


class RateLimiter:
    """Machine-wide token bucket. State lives in <root>/.ratelimit.json, guarded by flock on <root>/.lock.

    acquire() holds the lock while it sleeps, so every process queues behind it: total request rate across
    all processes is <= rate (default 1/s), burst <= `burst`. penalize() sets a shared pause after a 429.
    """

    def __init__(self, service: str = "yahoo", rate: float | None = None, burst: float = 1.0):
        self.service, self.rate, self.burst = service, rate, burst

    @property
    def _rate(self) -> float:
        return self.rate if self.rate is not None else rate_per_s()

    def _state_path(self) -> Path:
        return root() / ".ratelimit.json"

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self._state_path().read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, st: dict[str, Any]) -> None:
        tmp = self._state_path().with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(st))
        os.replace(tmp, self._state_path())

    def acquire(self) -> float:
        with file_lock(root() / ".lock"):
            st = self._read()
            s = st.get(self.service, {})
            now = time.time()
            pause = float(s.get("pause_until", 0.0))
            if pause > now:
                log().warning("ratelimit %s: shared 429 pause, sleeping %.1fs", self.service, pause - now)
                time.sleep(pause - now)
                now = time.time()
            tokens = min(self.burst, float(s.get("tokens", self.burst)) + (now - float(s.get("ts", now))) * self._rate)
            if tokens < 1.0:
                wait = (1.0 - tokens) / self._rate
                time.sleep(wait)
                now = time.time()
                tokens = 1.0
            s.update(tokens=tokens - 1.0, ts=now, pause_until=pause, last_pid=os.getpid())
            st[self.service] = s
            self._write(st)
            return now

    def penalize(self, seconds: float) -> None:
        with file_lock(root() / ".lock"):
            st = self._read()
            s = st.get(self.service, {})
            s["pause_until"] = max(float(s.get("pause_until", 0.0)), time.time() + seconds)
            st[self.service] = s
            self._write(st)
        log().warning("ratelimit %s: penalized %.0fs (all processes pause)", self.service, seconds)


YAHOO_LIMITER = RateLimiter("yahoo")

# ----------------------------------------------------------------------------------------------- HTTP
NETWORK_CALLS = 0  # per-process counter (tests assert on it)


def http_get(url: str, timeout: float = 40.0) -> tuple[int, bytes]:
    """The single network primitive. Tests monkeypatch this."""
    import requests  # local import keeps library import cheap

    global NETWORK_CALLS
    NETWORK_CALLS += 1
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    return r.status_code, r.content


def log_request(**kw: Any) -> None:
    with db() as con:
        insert_row(con, "requests", {"ts_utc": iso(utcnow()), "pid": os.getpid(), **kw})


class FetchError(RuntimeError):
    pass


def yahoo_request(symbol: str, interval: str, p1: int, p2: int) -> tuple[int, bytes, str]:
    """GET one chart range through the shared limiter, retrying 429 (shared pause) / 5xx / network errors."""
    q = urllib.parse.quote(symbol, safe="")
    params = f"period1={p1}&period2={p2}&interval={interval}&events=div%2Csplits&includeAdjustedClose=true"
    last = ""
    for attempt in range(MAX_ATTEMPTS):
        host = HOSTS[attempt % 2]
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{q}?{params}"
        YAHOO_LIMITER.acquire()
        t0 = time.time()
        try:
            status, body = http_get(url)
        except Exception as e:  # noqa: BLE001 - network layer, logged + retried
            last = repr(e)
            log_request(service="yahoo", url=url, symbol=symbol, interval=interval, attempt=attempt + 1,
                        http_status=None, bytes=0, elapsed_ms=int((time.time() - t0) * 1000), error=last[:500])
            wait = min(300.0, 5.0 * 2**attempt)
            log().warning("yahoo %s %s attempt %d network error %s -> sleep %.0fs", symbol, interval, attempt + 1, last, wait)
            time.sleep(wait)
            continue
        ms = int((time.time() - t0) * 1000)
        log_request(service="yahoo", url=url, symbol=symbol, interval=interval, attempt=attempt + 1,
                    http_status=status, bytes=len(body), elapsed_ms=ms, error=None)
        log().info("yahoo GET %s -> HTTP %s %dB %dms (attempt %d)", url, status, len(body), ms, attempt + 1)
        if status in (200, 404):
            return status, body, url
        last = f"HTTP {status}: {body[:200]!r}"
        if status == 429:
            wait = min(600.0, 30.0 * 2**attempt) * (1 + random.random() * 0.2)
            YAHOO_LIMITER.penalize(wait)
        else:
            wait = min(300.0, 5.0 * 2**attempt)
            log().warning("yahoo %s HTTP %s -> sleep %.0fs", symbol, status, wait)
            time.sleep(wait)
    raise FetchError(f"yahoo {symbol} {interval}: gave up after {MAX_ATTEMPTS} attempts; last={last}")


# ----------------------------------------------------------------------------------------------- parsing
@dataclass
class Parsed:
    status: str  # ok | not_found | empty | error
    symbol: str | None = None
    interval: str | None = None
    df: pl.DataFrame | None = None
    info: dict[str, Any] = field(default_factory=dict)
    note: str = ""


def _local_key(epoch_col: pl.Expr, tz: str, interval: str) -> pl.Expr:
    dt = pl.from_epoch(epoch_col, time_unit="s").dt.replace_time_zone("UTC")
    if interval == "1h":
        return dt.dt.cast_time_unit("us")
    return dt.dt.convert_time_zone(tz).dt.date()


def _events_frame(ev: dict[str, Any] | None, tz: str, interval: str, kind: str) -> pl.DataFrame | None:
    if not ev:
        return None
    df = pl.DataFrame(list(ev.values()), infer_schema_length=None)
    if df.is_empty() or "date" not in df.columns:
        return None
    k = key_col(interval)
    if kind == "dividends":
        return (df.with_columns(_local_key(pl.col("date"), tz, interval).alias(k), pl.col("amount").cast(pl.Float64))
                .group_by(k).agg(pl.col("amount").sum().alias("dividends")))
    num = pl.col("numerator").cast(pl.Float64) if "numerator" in df.columns else pl.lit(None, pl.Float64)
    den = pl.col("denominator").cast(pl.Float64) if "denominator" in df.columns else pl.lit(None, pl.Float64)
    return (df.with_columns(_local_key(pl.col("date"), tz, interval).alias(k), (num / den).alias("splits"))
            .group_by(k).agg(pl.col("splits").product()))


def parse_chart(obj: Any, events_requested: bool | None = True) -> Parsed:
    """Yahoo v8 chart JSON -> bars frame keyed by exchange-local date (or UTC ts for 1h)."""
    if not isinstance(obj, dict) or "chart" not in obj:
        return Parsed("error", note="not a chart object")
    ch = obj["chart"] or {}
    if ch.get("error"):
        err = ch["error"] or {}
        code = str(err.get("code"))
        return Parsed("not_found" if code == "Not Found" else "error", note=f"{code}: {err.get('description')}"[:300])
    res = ch.get("result") or []
    if not res:
        return Parsed("empty", note="result empty")
    r = res[0]
    m = r.get("meta") or {}
    interval = norm_interval(m.get("dataGranularity")) or "1d"
    tz = m.get("exchangeTimezoneName") or "UTC"
    info = {
        "symbol": canon(m["symbol"]) if m.get("symbol") else None, "currency": m.get("currency"),
        "exchange": m.get("fullExchangeName"), "exchange_code": m.get("exchangeName"),
        "instrument_type": m.get("instrumentType"), "timezone": tz,
        "long_name": m.get("longName") or m.get("shortName"), "first_trade_epoch": m.get("firstTradeDate"),
        "granularity": interval,
    }
    ts = r.get("timestamp") or []
    if not ts:
        return Parsed("empty", info["symbol"], interval, None, info, "no timestamps")
    ind = r.get("indicators") or {}
    q = (ind.get("quote") or [{}])[0] or {}
    adj = ((ind.get("adjclose") or [{}])[0] or {}).get("adjclose")
    n = len(ts)

    def col(name: str, vals: list | None) -> pl.Series:
        return pl.Series(name, vals if vals is not None and len(vals) == n else [None] * n, dtype=pl.Float64, strict=False)

    k = key_col(interval)
    try:
        df = pl.DataFrame([pl.Series("t", ts, dtype=pl.Int64), col("open", q.get("open")), col("high", q.get("high")),
                           col("low", q.get("low")), col("close", q.get("close")), col("adjclose", adj),
                           col("volume", q.get("volume"))])
        df = df.with_columns(_local_key(pl.col("t"), tz, interval).alias(k))
    except Exception as e:  # noqa: BLE001 - bad tz name etc.
        return Parsed("error", info["symbol"], interval, None, info, f"parse error {e!r}"[:300])
    ev = r.get("events") or {}
    has_events = bool(ev) or bool(events_requested)
    fill = 0.0 if has_events else None
    for kind in ("dividends", "splits"):
        e = _events_frame(ev.get(kind), tz, interval, kind)
        if e is not None:
            df = df.join(e, on=k, how="left").with_columns(pl.col(kind).fill_null(fill))
        else:
            df = df.with_columns(pl.lit(fill, pl.Float64).alias(kind))
    df = (df.filter(pl.col("close").is_not_null()).sort(k).unique(subset=[k], keep="last", maintain_order=True)
          .drop("t"))
    info["has_events"] = 1 if has_events else None
    return Parsed("ok" if df.height else "empty", info["symbol"], interval, df, info)


# ----------------------------------------------------------------------------------------------- coverage
def finalize(df: pl.DataFrame, interval: str, fetched_at: datetime, first_trade_epoch: int | None,
             req_start: date | datetime | None = None, req_end: date | datetime | None = None
             ) -> tuple[pl.DataFrame, int, str | None, str | None]:
    """Drop provisional (not yet closed) bars and compute the date range this fetch is authoritative for.

    1d : bars dated after fetched_at(UTC date) - 1 day are provisional.   1wk/1mo: the period must have ended.
    1h : bars whose hour had not finished at fetched_at are provisional.
    cover_start = 1900-01-01 when the first bar is at the listing date (nothing earlier exists), else the
    requested start (network) or first bar (imports, request unknown).
    """
    n0 = df.height
    if interval == "1h":
        cut = fetched_at.astimezone(timezone.utc)
        if req_end is not None:
            cut = min(cut, req_end if isinstance(req_end, datetime) else datetime.combine(req_end, datetime.min.time(), timezone.utc))
        df = df.filter((pl.col("ts") + pl.duration(hours=1)) <= cut)
        cover_end = iso(cut)
        if req_start is not None:
            cover_start = iso(req_start if isinstance(req_start, datetime) else datetime.combine(req_start, datetime.min.time(), timezone.utc))
        else:
            cover_start = iso(df["ts"].min()) if df.height else None
        return df, n0 - df.height, cover_start, cover_end
    ce = fetched_at.astimezone(timezone.utc).date() - timedelta(days=1)
    if req_end is not None:
        ce = min(ce, to_date(req_end))
    nxt = ce + timedelta(days=1)
    if interval == "1d":
        df = df.filter(pl.col("date") <= ce)
    elif interval == "1wk":
        df = df.filter((pl.col("date") + pl.duration(days=7)) <= pl.lit(nxt))
    else:  # 1mo and anything coarser
        df = df.filter(pl.col("date").dt.offset_by("1mo") <= pl.lit(nxt))
    cs: date | None
    if df.height:
        first = df["date"].min()
        ftd = None
        if first_trade_epoch:
            ftd = datetime.fromtimestamp(int(first_trade_epoch), timezone.utc).date()
        if ftd is not None and first <= ftd + timedelta(days=7):
            cs = EPOCH_START
        elif req_start is not None:
            cs = min(to_date(req_start), first)
        else:
            cs = first
    else:
        cs = to_date(req_start) if req_start is not None else None
    return df, n0 - df.height, (cs.isoformat() if cs else None), ce.isoformat()


# ----------------------------------------------------------------------------------------------- merge
def _empty(interval: str) -> pl.DataFrame:
    return pl.DataFrame(schema=schema_for(interval))


def conform(df: pl.DataFrame, interval: str) -> pl.DataFrame:
    sch = schema_for(interval)
    out = df.with_columns([pl.lit(None, t).alias(c) for c, t in sch.items() if c not in df.columns])
    return out.select([pl.col(c).cast(t, strict=False) for c, t in sch.items()])


def merge_series(E: pl.DataFrame | None, N: pl.DataFrame, interval: str, fetch_times: dict[int, str],
                 t_new: str) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    """Merge new fetch N into existing series E. Newer fetch wins on overlapping dates.

    Adjustment bases differ between fetches (a dividend/split after the older fetch rescales Yahoo's history),
    so the older side is first rescaled onto the newer side's basis using per-date ratios on the overlap
    (rolling median 11, nearest-date as-of join). Conflicts are computed on the raw stored values.
    Returns (merged, conflicts, info).
    """
    k = key_col(interval)
    N = conform(N, interval)
    info: dict[str, Any] = {"overlap": 0, "conflicts": 0, "rebased_side": None, "ratio_close_med": 1.0, "ratio_adj_med": 1.0}
    if E is None or E.is_empty():
        return N.sort(k), pl.DataFrame(), info
    E = conform(E, interval)
    ft = pl.DataFrame({"fetch_id": list(fetch_times.keys()), "_t": list(fetch_times.values())},
                      schema={"fetch_id": pl.Int64, "_t": pl.Utf8})
    E = E.join(ft, on="fetch_id", how="left").with_columns(pl.col("_t").fill_null(""))
    N = N.with_columns(pl.lit(t_new).alias("_t"))
    t_e_max = E["_t"].max() or ""
    new_is_basis = t_new >= t_e_max
    ov = E.join(N, on=k, how="inner", suffix="_n").sort(k)
    info["overlap"] = ov.height
    conflicts = pl.DataFrame()
    if ov.height:
        ref = "adjclose" if ov.select(pl.col("adjclose").is_not_null() & pl.col("adjclose_n").is_not_null()).to_series().any() else "close"
        ov = ov.with_columns(
            (pl.col("close_n") / pl.col("close")).alias("_rc"),
            pl.when(pl.col("adjclose").is_not_null() & pl.col("adjclose_n").is_not_null() & (pl.col("adjclose") != 0))
            .then(pl.col("adjclose_n") / pl.col("adjclose")).otherwise(pl.col("close_n") / pl.col("close")).alias("_ra"),
        ).with_columns(
            pl.col("_rc").rolling_median(11, min_samples=1, center=True).alias("_rcs"),
            pl.col("_ra").rolling_median(11, min_samples=1, center=True).alias("_ras"),
        )
        info["ratio_close_med"] = float(ov["_rc"].median() or 1.0)
        info["ratio_adj_med"] = float(ov["_ra"].median() or 1.0)
        refE, refN = (pl.col("adjclose"), pl.col("adjclose_n")) if ref == "adjclose" else (pl.col("close"), pl.col("close_n"))
        rs = pl.col("_ras") if ref == "adjclose" else pl.col("_rcs")
        def rel(a: pl.Expr, b: pl.Expr) -> pl.Expr:  # |b/a - 1|; 0 when both are 0, inf when only a is 0
            return (pl.when((a == 0) & (b == 0)).then(0.0).when(a == 0).then(float("inf"))
                    .otherwise(((b / a) - 1).abs()).fill_nan(float("inf")))
        c = ov.with_columns(
            rel(refE, refN).alias("rel_diff_raw"),
            rel(refE * rs, refN).alias("rel_diff_after_rebase"),
        ).filter(pl.col("rel_diff_raw").is_not_null() & (pl.col("rel_diff_raw") > CONFLICT_REL))
        if c.height:
            conflicts = c.select(
                pl.col(k).cast(pl.Utf8).alias("key"), pl.lit(ref).alias("field"),
                refE.alias("value_existing"), refN.alias("value_new"),
                pl.col("fetch_id").alias("fetch_id_existing"), pl.col("fetch_id_n").alias("fetch_id_new"),
                pl.col("_t").alias("fetched_at_existing"), pl.col("_t_n").alias("fetched_at_new"),
                "rel_diff_raw", "rel_diff_after_rebase",
                pl.when(pl.col("rel_diff_after_rebase") <= CONFLICT_REL).then(pl.lit("scale")).otherwise(pl.lit("value")).alias("kind"),
                pl.when(pl.col("_t_n") >= pl.col("_t")).then(pl.col("fetch_id_n")).otherwise(pl.col("fetch_id")).alias("winner_fetch_id"),
            )
        info["conflicts"] = conflicts.height
        ratios = ov.select(k, "_rcs", "_ras")
        side = "E" if new_is_basis else "N"
        info["rebased_side"] = side
        tgt = E if side == "E" else N
        tgt = tgt.sort(k).join_asof(ratios.sort(k), on=k, strategy="nearest")
        rc = pl.col("_rcs") if side == "E" else 1 / pl.col("_rcs")
        ra = pl.col("_ras") if side == "E" else 1 / pl.col("_ras")
        # snap float noise so identical-basis merges never touch values
        rc = pl.when((rc - 1).abs() < 1e-7).then(1.0).otherwise(rc)
        ra = pl.when((ra - 1).abs() < 1e-7).then(1.0).otherwise(ra)
        tgt = tgt.with_columns(
            *[(pl.col(cn) * rc).alias(cn) for cn in ("open", "high", "low", "close", "dividends")],
            (pl.col("adjclose") * ra).alias("adjclose"),
            (pl.col("volume") / rc).alias("volume"),
        ).drop("_rcs", "_ras")
        if side == "E":
            E = tgt
        else:
            N = tgt
    else:
        log().warning("merge %s: no overlap between existing and new fetch; stitched without rebase", interval)
        info["rebased_side"] = "none(no_overlap)"
    merged = (pl.concat([E, N], how="diagonal_relaxed").sort([k, "_t"])
              .unique(subset=[k], keep="last", maintain_order=True).drop("_t"))
    return conform(merged, interval).sort(k), conflicts, info


def write_parquet_atomic(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    df.write_parquet(tmp, compression="zstd", statistics=True)
    os.replace(tmp, path)


def read_bars(symbol: str, interval: str = "1d", source: str = "yahoo") -> pl.DataFrame:
    p = bars_path(symbol, interval, source)
    return pl.read_parquet(p) if p.exists() else _empty(interval)


def store(symbol: str, interval: str, source: str, parsed: Parsed | None, fetch: dict[str, Any],
          locked: bool = False) -> int:
    """Record a fetch in the ledger and merge its bars (if any) into the symbol's Parquet. Returns fetch_id."""
    symbol = canon(symbol)
    ctx = symbol_lock(symbol, interval, source) if not locked else _null_ctx()
    with ctx:
        row = {"symbol": symbol, "interval": interval, "source": source, "state": "pending",
               "imported_at_utc": iso(utcnow()), **fetch}
        if parsed is not None:
            row.update({k: parsed.info.get(k) for k in ("currency", "exchange", "exchange_code", "instrument_type",
                                                      "timezone", "long_name", "has_events", "granularity")})
        with db() as con:
            fid = insert_row(con, "fetches", row)
        if parsed is not None and parsed.status == "ok" and parsed.df is not None and parsed.df.height:
            N = parsed.df.with_columns(pl.lit(fid, pl.Int64).alias("fetch_id"))
            p = bars_path(symbol, interval, source)
            E = pl.read_parquet(p) if p.exists() else None
            with db() as con:
                ids = [] if E is None else E["fetch_id"].unique().drop_nulls().to_list()
                times = {int(r["fetch_id"]): r["fetched_at_utc"] or "" for r in con.execute(
                    f"SELECT fetch_id, fetched_at_utc FROM fetches WHERE fetch_id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
            merged, conf, info = merge_series(E, N, interval, times, fetch.get("fetched_at_utc") or "")
            write_parquet_atomic(merged, p)
            with db() as con:
                if conf.height:
                    now = iso(utcnow())
                    con.execute("BEGIN")
                    con.executemany(
                        "INSERT INTO conflicts(symbol, interval, source, key, field, value_existing, value_new, "
                        "fetch_id_existing, fetch_id_new, fetched_at_existing, fetched_at_new, rel_diff_raw, "
                        "rel_diff_after_rebase, kind, winner_fetch_id, detected_at_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [(symbol, interval, source, *r, now) for r in conf.iter_rows()])
                    con.execute("COMMIT")
                    log().warning("CONFLICT %s %s %s: %d dates differ >%.1f%% (kinds %s) fetch %s vs %s; newer wins",
                                  source, symbol, interval, conf.height, CONFLICT_REL * 100,
                                  dict(conf["kind"].value_counts().iter_rows()), conf["fetch_id_existing"].unique().to_list(), fid)
                con.execute("UPDATE fetches SET state='done', note=COALESCE(note,'') || ? WHERE fetch_id=?",
                            (f" merge:overlap={info['overlap']} conflicts={info['conflicts']} rebased={info['rebased_side']}"
                             f" rc={info['ratio_close_med']:.6g} ra={info['ratio_adj_med']:.6g} total_rows={merged.height}", fid))
            log().info("stored %s %s %s fetch_id=%d rows_new=%d total=%d overlap=%d conflicts=%d rebased=%s",
                       source, symbol, interval, fid, N.height, merged.height, info["overlap"], info["conflicts"], info["rebased_side"])
        else:
            with db() as con:
                con.execute("UPDATE fetches SET state='done' WHERE fetch_id=?", (fid,))
            log().info("recorded %s %s %s fetch_id=%d status=%s (no bars)", source, symbol, interval, fid, row.get("status"))
        return fid


@contextmanager
def _null_ctx() -> Iterator[None]:
    yield


# ----------------------------------------------------------------------------------------------- get
def _coverage(symbol: str, interval: str, source: str = "yahoo") -> list[sqlite3.Row]:
    with db() as con:
        return con.execute(
            "SELECT * FROM fetches WHERE symbol=? AND interval=? AND source=? AND state='done' ORDER BY fetched_at_utc",
            (symbol, interval, source)).fetchall()


def _subtract(want: tuple[Any, Any], have: list[tuple[Any, Any]], step: timedelta) -> list[tuple[Any, Any]]:
    """Interval arithmetic on closed [a, b] ranges (dates: step=1 day; ts: step=1 hour)."""
    out = [want]
    for a, b in sorted(have):
        nxt = []
        for x, y in out:
            if b < x or a > y:
                nxt.append((x, y))
                continue
            if a > x:
                nxt.append((x, a - step))
            if b < y:
                nxt.append((b + step, y))
        out = nxt
    return [(x, y) for x, y in out if x <= y]


def missing_ranges(symbol: str, interval: str, start: Any, end: Any, max_age_hours: float = MAX_AGE_HOURS
                   ) -> tuple[list[tuple[Any, Any]], str | None]:
    """Ranges of [start, end] not covered by any recorded fetch. Second value: 'not_found' if negatively cached."""
    rows = _coverage(symbol, interval)
    now = utcnow()
    nf = [r for r in rows if r["status"] in ("not_found",)]
    ok = [r for r in rows if r["status"] in ("ok", "empty") and r["cover_start"] and r["cover_end"]]
    if nf and not ok:
        last = parse_iso(nf[-1]["fetched_at_utc"])
        if last and now - last < timedelta(days=NOT_FOUND_RETRY_DAYS):
            return [], "not_found"
    hourly = interval == "1h"
    conv = (lambda s: parse_iso(s)) if hourly else (lambda s: to_date(s))
    have = [(conv(r["cover_start"]), conv(r["cover_end"])) for r in ok]
    fresh = [r for r in ok if (parse_iso(r["fetched_at_utc"]) or datetime.min.replace(tzinfo=timezone.utc)) > now - timedelta(hours=max_age_hours)]
    if hourly:
        a = start if isinstance(start, datetime) else datetime.combine(to_date(start), datetime.min.time(), timezone.utc)
        b = end if isinstance(end, datetime) else datetime.combine(to_date(end), datetime.max.time(), timezone.utc).replace(microsecond=0)
        b = min(b, now)
        step = timedelta(hours=1)
        if fresh:
            have.append((min(conv(r["cover_start"]) for r in fresh), b))
    else:
        a, b = to_date(start), min(to_date(end), now.date())
        step = timedelta(days=1)
        if fresh:
            have.append((max(conv(r["cover_end"]) for r in fresh), b))
    if a > b:
        return [], None
    gaps = _subtract((a, b), have, step)
    if not hourly and gaps:
        crypto = any((r["instrument_type"] or "").upper() == "CRYPTOCURRENCY" for r in ok)
        if not crypto:  # a gap made only of Saturdays/Sundays cannot contain an equity bar
            gaps = [(x, y) for x, y in gaps if not ((y - x).days <= 1 and x.weekday() >= 5 and y.weekday() >= 5)]
    return gaps, None


def _epoch(d: Any, end: bool = False) -> int:
    if isinstance(d, datetime):
        return int(d.timestamp())
    dd = to_date(d) + (timedelta(days=1) if end else timedelta(0))
    return int(datetime.combine(dd, datetime.min.time(), timezone.utc).timestamp())


def fetch_yahoo(symbol: str, interval: str, start: Any, end: Any) -> int:
    """Network fetch of [start, end] (caller holds the symbol lock). Raw body kept gzip under <root>/raw/yahoo/."""
    now = utcnow()
    p1 = _epoch(start)
    p2 = min(_epoch(end, end=True), int(now.timestamp()))
    if interval == "1h":
        p1 = max(p1, int((now - timedelta(days=729)).timestamp()))
    status, body, url = yahoo_request(symbol, interval, p1, p2)
    fetched_at = utcnow()
    raw = root() / "raw" / "yahoo" / interval / qname(symbol) / f"{fetched_at:%Y%m%dT%H%M%S%f}Z.json.gz"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(gzip.compress(body, mtime=0))
    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        obj = None
    parsed = parse_chart(obj, events_requested=True) if obj is not None else Parsed("error", note="non-json body")
    if status == 404 and parsed.status not in ("not_found",):
        parsed = Parsed("not_found", note=parsed.note or "HTTP 404")
    fetch: dict[str, Any] = {"requested_symbol": symbol, "origin": "network", "import_source": "network",
                             "path": str(raw), "sha256": hashlib.sha256(body).hexdigest(), "size": len(body),
                             "fetched_at_utc": iso(fetched_at), "fetched_at_basis": "network", "status": parsed.status,
                             "url": url, "note": parsed.note}
    target_interval = interval
    if parsed.status == "ok":
        assert parsed.df is not None
        if parsed.interval != interval:
            log().warning("yahoo %s asked %s got granularity %s; storing under %s", symbol, interval, parsed.interval, parsed.interval)
            target_interval = parsed.interval or interval
        rs = datetime.fromtimestamp(p1, timezone.utc) if interval == "1h" else datetime.fromtimestamp(p1, timezone.utc).date()
        re_ = datetime.fromtimestamp(p2, timezone.utc) if interval == "1h" else datetime.fromtimestamp(p2, timezone.utc).date()
        df, dropped, cs, ce = finalize(parsed.df, target_interval, fetched_at, parsed.info.get("first_trade_epoch"), rs, re_)
        parsed.df = df
        k = key_col(target_interval)
        fetch.update(n_rows=df.height, n_dropped_provisional=dropped, cover_start=cs, cover_end=ce,
                     first_key=str(df[k].min()) if df.height else None, last_key=str(df[k].max()) if df.height else None)
        if parsed.symbol and parsed.symbol != canon(symbol):
            add_alias(symbol, parsed.symbol, "network")
    elif parsed.status == "empty":
        fetch.update(n_rows=0, cover_start=datetime.fromtimestamp(p1, timezone.utc).date().isoformat(),
                     cover_end=(fetched_at.date() - timedelta(days=1)).isoformat())
    return store(symbol, target_interval, "yahoo", parsed, fetch, locked=(target_interval == interval))


def _coerce_range(start: Any, end: Any, interval: str) -> tuple[Any, Any]:
    if interval == "1h":
        def dt(x: Any, default: datetime) -> datetime:
            if x is None:
                return default
            if isinstance(x, datetime):
                return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
            return datetime.combine(to_date(x), datetime.min.time(), timezone.utc)
        now = utcnow()
        return dt(start, now - timedelta(days=729)), dt(end, now)
    return (to_date(start) if start is not None else EPOCH_START), (to_date(end) if end is not None else utcnow().date())


def get(symbol: str, start: Any = None, end: Any = None, interval: str = "1d", *, offline: bool = False,
        max_age_hours: float = MAX_AGE_HOURS, source: str = "yahoo", pandas: bool = False):
    """Bars for [start, end] (inclusive). Reads the cache; fetches only missing ranges from Yahoo.

    source="yahoo" (default) returns Yahoo-only data. source="any" appends secondary-source rows (Kaggle /
    FMP / Binance) for dates Yahoo lacks, with a `source` column; never mixed silently.
    offline=True never touches the network. Returns polars (pandas=True for pandas).
    """
    if interval not in INTERVALS:
        raise ValueError(f"interval must be one of {INTERVALS}")
    sym = resolve(symbol)
    a, b = _coerce_range(start, end, interval)
    lg = log()
    lg.info("get %s(%s) %s..%s %s offline=%s source=%s", symbol, sym, a, b, interval, offline, source)
    if not offline:
        with symbol_lock(sym, interval):
            gaps, flag = missing_ranges(sym, interval, a, b, max_age_hours)
            if flag == "not_found":
                lg.info("get %s: Yahoo 404 within %d days -> no fetch", sym, NOT_FOUND_RETRY_DAYS)
            elif gaps:
                lo = min(g[0] for g in gaps)
                hi = max(g[1] for g in gaps)
                pad = timedelta(days=PAD_DAYS)
                lg.info("get %s %s: gaps=%s -> one request %s..%s (pad %dd)", sym, interval,
                        [(str(x), str(y)) for x, y in gaps], lo - pad, hi + pad, PAD_DAYS)
                fetch_yahoo(sym, interval, lo - pad if lo != EPOCH_START else lo, hi + pad)
            else:
                lg.info("get %s %s: cache covers request, 0 network calls", sym, interval)
    k = key_col(interval)
    df = read_bars(sym, interval).filter(pl.col(k).is_between(a, b))
    if source == "any":
        df = df.with_columns(pl.lit("yahoo").alias("source"))
        with db() as con:
            slug2src = {source_slug(r[0]): r[0] for r in con.execute("SELECT DISTINCT source FROM fetches WHERE source!='yahoo'")}
        for p in sorted((root() / "secondary").glob(f"*/{interval}/{qname(sym)}.parquet")):
            src = slug2src.get(p.parts[-3], p.parts[-3])
            extra = pl.read_parquet(p).filter(pl.col(k).is_between(a, b)).join(df.select(k), on=k, how="anti")
            if extra.height:
                lg.info("get %s: +%d rows from secondary %s", sym, extra.height, src)
                df = pl.concat([df, extra.with_columns(pl.lit(src).alias("source"))], how="diagonal_relaxed")
        df = df.sort(k)
    elif source != "yahoo":
        df = read_bars(sym, interval, source).filter(pl.col(k).is_between(a, b))
    return df.to_pandas() if pandas else df


def bulk_get(symbols: Iterable[str], start: Any = None, end: Any = None, interval: str = "1d", *, long: bool = False,
             **kw: Any):
    """get() for many symbols, sequentially (the shared limiter caps the rate anyway). Errors are logged, not raised.

    long=False -> {symbol: DataFrame}; long=True -> one polars frame with a `symbol` column.
    """
    out: dict[str, Any] = {}
    errors: dict[str, str] = {}
    syms = list(dict.fromkeys(canon(s) for s in symbols))
    log().info("bulk_get n=%d %s..%s %s", len(syms), start, end, interval)
    for i, s in enumerate(syms, 1):  # loop over symbols = I/O, body is vectorised
        try:
            out[s] = get(s, start, end, interval, **kw)
        except Exception as e:  # noqa: BLE001 - keep going, report at the end
            errors[s] = repr(e)
            log().error("bulk_get %s failed: %r", s, e)
        if i % 100 == 0:
            log().info("bulk_get progress %d/%d errors=%d", i, len(syms), len(errors))
    if errors:
        log().warning("bulk_get finished with %d errors: %s", len(errors), list(errors)[:20])
    if long:
        frames = [pl.DataFrame(d) if not isinstance(d, pl.DataFrame) else d for d in out.values()]
        return pl.concat([f.with_columns(pl.lit(s).alias("symbol")) for s, f in zip(out, frames)], how="diagonal_relaxed") if frames else _empty(interval)
    return out


# ----------------------------------------------------------------------------------------------- snapshots / status
def export_meta() -> dict[str, Path]:
    """Write meta.parquet (one row per symbol x interval x source), fetches.parquet, conflicts/conflicts.parquet."""
    with db() as con:
        f = pl.read_database("SELECT * FROM fetches", con, infer_schema_length=None)
        c = pl.read_database("SELECT * FROM conflicts", con, infer_schema_length=None)
    r = root()
    if f.height:
        f = f.with_columns(pl.col("fetched_at_utc").cast(pl.Utf8))
        okf = f.filter(pl.col("status") == "ok")
        m = (f.sort("fetched_at_utc").group_by(["symbol", "interval", "source"]).agg(
            pl.col("status").filter(pl.col("status") == "ok").len().alias("n_ok_fetches"),
            pl.len().alias("n_fetches"),
            pl.col("status").last().alias("last_status"),
            pl.col("fetched_at_utc").max().alias("fetched_at_utc"),
            pl.col("path").alias("original_paths"), pl.col("sha256").alias("sha256s"),
            pl.col("import_source").unique().alias("import_sources"),
            pl.col("currency").drop_nulls().last().alias("currency"),
            pl.col("exchange").drop_nulls().last().alias("exchange"),
            pl.col("instrument_type").drop_nulls().last().alias("instrument_type"),
            pl.col("long_name").drop_nulls().last().alias("long_name"),
        ))
        span = okf.group_by(["symbol", "interval", "source"]).agg(
            pl.col("first_key").min().alias("first_date"), pl.col("last_key").max().alias("last_date"))
        m = m.join(span, on=["symbol", "interval", "source"], how="left")
        if c.height:
            m = m.join(c.group_by(["symbol", "interval", "source"]).agg(pl.len().alias("n_conflicts")),
                       on=["symbol", "interval", "source"], how="left")
        else:
            m = m.with_columns(pl.lit(0).alias("n_conflicts"))
        m = m.with_columns(pl.col("n_conflicts").fill_null(0),
                           pl.when(pl.col("n_ok_fetches") > 0).then(pl.lit("ok")).otherwise(pl.col("last_status")).alias("status"))
        write_parquet_atomic(m.sort(["symbol", "interval", "source"]), r / "meta.parquet")
        write_parquet_atomic(f, r / "fetches.parquet")
    (r / "conflicts").mkdir(parents=True, exist_ok=True)
    if c.height:
        write_parquet_atomic(c, r / "conflicts" / "conflicts.parquet")
    return {"meta": r / "meta.parquet", "fetches": r / "fetches.parquet", "conflicts": r / "conflicts" / "conflicts.parquet"}


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def status() -> dict[str, Any]:
    r = root()
    with db() as con:
        rows = con.execute("SELECT source, interval, status, COUNT(DISTINCT symbol) n_sym, COUNT(*) n_fetch "
                           "FROM fetches WHERE state='done' GROUP BY 1,2,3 ORDER BY 1,2,3").fetchall()
        byimp = con.execute("SELECT import_source, status, COUNT(DISTINCT symbol) n_sym, COUNT(*) n_files "
                            "FROM fetches WHERE state='done' GROUP BY 1,2 ORDER BY 1,2").fetchall()
        conf = con.execute("SELECT kind, COUNT(*) n, COUNT(DISTINCT symbol) n_sym FROM conflicts GROUP BY 1").fetchall()
        pend = con.execute("SELECT COUNT(*) FROM fetches WHERE state='pending'").fetchone()[0]
        nreq = con.execute("SELECT COUNT(*), SUM(http_status=429) FROM requests").fetchone()
    files = {f"bars/{iv}": len(list((r / 'bars' / iv).glob('*.parquet'))) for iv in INTERVALS}
    sec = {p.name: len(list(p.rglob("*.parquet"))) for p in (r / "secondary").glob("*")} if (r / "secondary").exists() else {}
    return {
        "root": str(r), "parquet_files": files, "secondary_files": sec,
        "size_bytes": {"bars": dir_size(r / "bars"), "secondary": dir_size(r / "secondary"), "raw": dir_size(r / "raw"),
                       "ledger": sum(p.stat().st_size for p in r.glob("ledger.sqlite*")), "total": dir_size(r)},
        "by_source_interval_status": [dict(x) for x in rows],
        "by_import_source": [dict(x) for x in byimp],
        "conflicts": [dict(x) for x in conf], "pending": pend,
        "network_requests": nreq[0], "http_429": nreq[1] or 0,
    }


# ----------------------------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="price_cache.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("import-existing", help="import every known on-disk Yahoo/Binance download (re-runnable)")
    a.add_argument("--min-age-min", type=float, default=10.0, help="skip files modified more recently (still being written)")
    a.add_argument("--only", default=None, help="only this import source name")
    a.add_argument("--no-discover", action="store_true", help="skip the generic chart-JSON discovery walk")
    sp.add_parser("status", help="counts, sizes, conflicts")
    sp.add_parser("export-meta", help="rewrite meta.parquet / fetches.parquet / conflicts parquet from the ledger")
    g = sp.add_parser("get", help="print bars for a symbol (fetches missing ranges unless --offline)")
    g.add_argument("symbol")
    g.add_argument("--start")
    g.add_argument("--end")
    g.add_argument("--interval", default="1d", choices=INTERVALS)
    g.add_argument("--offline", action="store_true")
    g.add_argument("--source", default="yahoo")
    mr = sp.add_parser("missing-report", help="symbols referenced by current studies that have no bars")
    mr.add_argument("--out", default=None)
    k = sp.add_parser("kaggle-import", help="import a Kaggle historical-price dataset as source kaggle:<ref>")
    k.add_argument("ref")
    k.add_argument("--only-missing", action="store_true", help="only symbols with no Yahoo bars")
    fm = sp.add_parser("fmp-fill", help="fill symbols Yahoo lacks from Financial Modeling Prep free tier")
    fm.add_argument("--limit", type=int, default=20)
    fm.add_argument("symbols", nargs="*")
    ns = ap.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if ns.cmd == "import-existing":
        import importers
        res = importers.import_existing(min_age_min=ns.min_age_min, only=ns.only, discover=not ns.no_discover)
        export_meta()
        print(json.dumps(res, indent=1, default=str))
    elif ns.cmd == "status":
        export_meta()
        print(json.dumps(status(), indent=1, default=str))
    elif ns.cmd == "export-meta":
        print(json.dumps({k2: str(v) for k2, v in export_meta().items()}, indent=1))
    elif ns.cmd == "get":
        df = get(ns.symbol, ns.start, ns.end, ns.interval, offline=ns.offline, source=ns.source)
        with pl.Config(tbl_rows=12, tbl_cols=12):
            print(df.head(5))
            print(df.tail(5))
        print(f"rows={df.height} network_calls_this_process={NETWORK_CALLS}")
    elif ns.cmd == "missing-report":
        import importers
        print(json.dumps(importers.missing_report(ns.out), indent=1, default=str))
    elif ns.cmd == "kaggle-import":
        import secondary
        print(json.dumps(secondary.kaggle_import(ns.ref, only_missing=ns.only_missing), indent=1, default=str))
        export_meta()
    elif ns.cmd == "fmp-fill":
        import secondary
        print(json.dumps(secondary.fmp_fill(ns.symbols, limit=ns.limit), indent=1, default=str))
        export_meta()
    return 0


if __name__ == "__main__":
    sys.exit(main())
