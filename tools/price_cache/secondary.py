"""Free secondary price sources, stored apart from Yahoo under secondary/<source>/ with their own provenance.

- kaggle:<owner>/<dataset>  public historical datasets (incl. symbols since delisted), imported from the
  downloaded zip in <root>/raw/kaggle/<owner>__<dataset>/ (members are read in place, never extracted).
- fmp  Financial Modeling Prep free tier (key from env FMP_API_KEY, or the stdout of the command in
  env PRICE_CACHE_FMP_KEY_CMD, e.g. a password-manager lookup; the key is never logged),
  capped per UTC day.
Nothing here is ever merged into Yahoo bars; get(..., source="any") appends rows with a `source` column.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

import polars as pl

import price_cache as pc

# ----------------------------------------------------------------------------------------------- Kaggle
# Per-dataset adapters: (zip member filter, member -> symbol, frame builder). Column meanings verified
# against Yahoo on overlapping symbols (see README "Sources" for the measured ratios).


def _boris_members(z: zipfile.ZipFile) -> Iterator[tuple[str, str]]:
    for n in z.namelist():  # zip directory listing (I/O)
        if n.endswith(".us.txt") and ("/Stocks/" in n or "/ETFs/" in n):
            yield n, Path(n).name[: -len(".us.txt")].upper()


def _boris_frame(raw: bytes) -> pl.DataFrame:
    df = pl.read_csv(io.BytesIO(raw), try_parse_dates=False, infer_schema_length=0)
    return df.select(
        pl.col("Date").str.to_date("%Y-%m-%d").alias("date"),
        *[pl.col(c).cast(pl.Float64).alias(c.lower()) for c in ("Open", "High", "Low", "Close", "Volume")],
    )


def _jackson_members(z: zipfile.ZipFile) -> Iterator[tuple[str, str]]:
    for n in z.namelist():
        if n.endswith(".csv") and (n.startswith("stocks/") or n.startswith("etfs/")):
            yield n, Path(n).stem.upper()


def _jackson_frame(raw: bytes) -> pl.DataFrame:
    df = pl.read_csv(io.BytesIO(raw), infer_schema_length=0)
    return df.select(
        pl.col("Date").str.to_date("%Y-%m-%d").alias("date"),
        *[pl.col(c).cast(pl.Float64).alias(c.lower()) for c in ("Open", "High", "Low", "Close", "Volume")],
        pl.col("Adj Close").cast(pl.Float64).alias("adjclose"),
    )


KAGGLE: dict[str, dict[str, Any]] = {
    "borismarjanovic/price-volume-data-for-all-us-stocks-etfs": {
        "members": _boris_members, "frame": _boris_frame, "version_date": "2017-11-16",
        "note": "Close is ALREADY split+dividend adjusted per dataset description; stored in close (see README)",
    },
    "jacksoncrow/stock-market-dataset": {
        "members": _jackson_members, "frame": _jackson_frame, "version_date": "2020-04-02",
        "note": "yfinance download of NASDAQ-traded symbols as of 2020-04-01; Close + Adj Close",
    },
}


def _zip_for(ref: str) -> Path:
    d = pc.root() / "raw" / "kaggle" / ref.replace("/", "__")
    zs = sorted(d.glob("*.zip"))
    if not zs:
        raise FileNotFoundError(f"no zip in {d}; run: kaggle datasets download -d {ref} -p {d}")
    return zs[0]


def kaggle_import(ref: str, only_missing: bool = False, frame_fn: Callable[[bytes], pl.DataFrame] | None = None
                  ) -> dict[str, Any]:
    """Import one Kaggle dataset as source kaggle:<ref>, one fetch row per member file. Re-runnable."""
    lg = pc.log()
    if ref == "ehallmar/daily-historical-stock-prices-1970-2018":
        return _ehallmar_import(ref, only_missing)
    cfg = KAGGLE[ref]
    src = f"kaggle:{ref}"
    zp = _zip_for(ref)
    zsha = pc.sha256_file(zp)
    fetched_at = datetime.fromisoformat(cfg["version_date"]).replace(tzinfo=timezone.utc)
    have_yahoo = _yahoo_1d_symbols() if only_missing else set()
    with pc.db() as con:
        done = {r[0] for r in con.execute("SELECT path FROM fetches WHERE source=? AND state='done'", (src,))}
    stats: dict[str, int] = {}
    t0 = time.time()
    lg.info("kaggle_import %s zip=%s sha256=%s only_missing=%s", ref, zp, zsha, only_missing)
    with zipfile.ZipFile(zp) as z:
        members = list(cfg["members"](z))
        for i, (m, sym) in enumerate(members, 1):  # loop over archive members (I/O)
            path = f"{zp}::{m}"
            if path in done:
                stats["already"] = stats.get("already", 0) + 1
                continue
            if only_missing and sym in have_yahoo:
                stats["skip_has_yahoo"] = stats.get("skip_has_yahoo", 0) + 1
                continue
            raw = z.read(m)
            try:
                df = (frame_fn or cfg["frame"])(raw) if raw.strip() else pl.DataFrame()
            except Exception as e:  # noqa: BLE001 - malformed member, logged + counted
                lg.warning("kaggle %s member %s parse error %r", ref, m, e)
                stats["parse_error"] = stats.get("parse_error", 0) + 1
                continue
            if df.height:
                df = df.filter(pl.col("close").is_not_null()).unique(subset=["date"], keep="last").sort("date")
            status = "ok" if df.height else "empty"
            parsed = pc.Parsed(status, sym, "1d", df if df.height else None,
                               {"currency": "USD", "exchange": "US (Kaggle " + ref + ")", "granularity": "1d", "has_events": None})
            pc.store(sym, "1d", src, parsed, {
                "requested_symbol": sym, "origin": "import", "import_source": src, "path": path,
                "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "fetched_at_utc": pc.iso(fetched_at),
                "fetched_at_basis": "dataset_version", "status": status, "n_rows": df.height,
                "first_key": str(df["date"].min()) if df.height else None, "last_key": str(df["date"].max()) if df.height else None,
                "cover_start": str(df["date"].min()) if df.height else None, "cover_end": str(df["date"].max()) if df.height else None,
                "note": f"zip_sha256={zsha} {cfg['note']}"})
            stats[status] = stats.get(status, 0) + 1
            if i % 1000 == 0:
                lg.info("kaggle_import %s %d/%d %s (%.0fs)", ref, i, len(members), stats, time.time() - t0)
    lg.info("kaggle_import %s done %s in %.0fs", ref, stats, time.time() - t0)
    return {"ref": ref, "members": len(members), "stats": stats, "seconds": round(time.time() - t0, 1)}


def _ehallmar_import(ref: str, only_missing: bool) -> dict[str, Any]:
    """One 2 GB long CSV (ticker, open, close, adj_close, low, high, volume, date). Vectorised split by ticker."""
    lg = pc.log()
    src = f"kaggle:{ref}"
    zp = _zip_for(ref)
    zsha = pc.sha256_file(zp)
    fetched_at = datetime(2018, 8, 26, tzinfo=timezone.utc)
    t0 = time.time()
    with zipfile.ZipFile(zp) as z:
        name = next(n for n in z.namelist() if n.endswith("historical_stock_prices.csv"))
        with z.open(name) as fh:
            df = pl.read_csv(fh, infer_schema_length=0)
    df = df.select(
        pl.col("ticker").str.to_uppercase().alias("symbol"), pl.col("date").str.to_date("%Y-%m-%d"),
        *[pl.col(c).cast(pl.Float64) for c in ("open", "high", "low", "close")],
        pl.col("adj_close").cast(pl.Float64).alias("adjclose"), pl.col("volume").cast(pl.Float64),
    ).filter(pl.col("close").is_not_null())
    lg.info("ehallmar read %d rows %d tickers in %.0fs", df.height, df["symbol"].n_unique(), time.time() - t0)
    if only_missing:
        df = df.filter(~pl.col("symbol").is_in(list(_yahoo_1d_symbols())))
    with pc.db() as con:
        done = {r[0] for r in con.execute("SELECT path FROM fetches WHERE source=? AND state='done'", (src,))}
    stats: dict[str, int] = {}
    for (sym,), g in df.sort(["symbol", "date"]).group_by("symbol", maintain_order=True):  # per-symbol write (I/O)
        path = f"{zp}::{name}#{sym}"
        if path in done:
            stats["already"] = stats.get("already", 0) + 1
            continue
        g = g.drop("symbol").unique(subset=["date"], keep="last").sort("date")
        parsed = pc.Parsed("ok", sym, "1d", g, {"currency": "USD", "exchange": "NYSE/NASDAQ (Kaggle ehallmar)", "granularity": "1d", "has_events": None})
        pc.store(sym, "1d", src, parsed, {
            "requested_symbol": sym, "origin": "import", "import_source": src, "path": path, "sha256": zsha,
            "size": None, "fetched_at_utc": pc.iso(fetched_at), "fetched_at_basis": "dataset_version", "status": "ok",
            "n_rows": g.height, "first_key": str(g["date"].min()), "last_key": str(g["date"].max()),
            "cover_start": str(g["date"].min()), "cover_end": str(g["date"].max()), "note": f"zip_sha256={zsha}"})
        stats["ok"] = stats.get("ok", 0) + 1
    lg.info("kaggle_import %s done %s in %.0fs", ref, stats, time.time() - t0)
    return {"ref": ref, "stats": stats, "seconds": round(time.time() - t0, 1)}


def _yahoo_1d_symbols() -> set[str]:
    with pc.db() as con:
        return {r[0] for r in con.execute(
            "SELECT DISTINCT symbol FROM fetches WHERE source='yahoo' AND interval='1d' AND status='ok' AND state='done'")}


# ----------------------------------------------------------------------------------------------- FMP
FMP_DAILY_CAP = 245  # free tier = 250 calls/day; margin for manual probes
FMP_LIMITER = pc.RateLimiter("fmp", rate=1.0)


def _fmp_key() -> str | None:
    k = os.environ.get("FMP_API_KEY")
    if k:
        return k.strip()
    cmd = os.environ.get("PRICE_CACHE_FMP_KEY_CMD")
    if not cmd:
        return None
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return out.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _fmp_calls_today() -> int:
    today = pc.utcnow().strftime("%Y-%m-%d")
    with pc.db() as con:
        return con.execute("SELECT COUNT(*) FROM requests WHERE service='fmp' AND substr(ts_utc,1,10)=?", (today,)).fetchone()[0]


def fmp_fill(symbols: list[str], limit: int = 20) -> dict[str, Any]:
    """Fetch full EOD history from FMP for symbols with no Yahoo 1d bars (default: Yahoo-404 symbols)."""
    lg = pc.log()
    key = _fmp_key()
    if not key:
        return {"error": "no FMP key: set FMP_API_KEY or PRICE_CACHE_FMP_KEY_CMD"}
    if not symbols:
        with pc.db() as con:
            symbols = [r[0] for r in con.execute(
                "SELECT DISTINCT symbol FROM fetches WHERE source='yahoo' AND status='not_found' AND symbol NOT IN "
                "(SELECT symbol FROM fetches WHERE source='yahoo' AND status='ok') AND symbol NOT IN "
                "(SELECT symbol FROM fetches WHERE source='fmp' AND status IN ('ok','not_in_plan','empty')) ORDER BY symbol")]
    out: dict[str, str] = {}
    for s in symbols[:limit]:  # loop over API calls (I/O)
        used = _fmp_calls_today()
        if used >= FMP_DAILY_CAP:
            lg.warning("fmp daily cap reached (%d/%d) -> stop", used, FMP_DAILY_CAP)
            out["_stopped"] = f"daily cap {used}/{FMP_DAILY_CAP}"
            break
        sym = pc.canon(s)
        url = f"https://financialmodelingprep.com/stable/historical-price-eod/full?symbol={sym}&apikey={key}"
        shown = url.replace(key, "<key>")
        FMP_LIMITER.acquire()
        t0 = time.time()
        try:
            st, body = pc.http_get(url)
        except Exception as e:  # noqa: BLE001
            pc.log_request(service="fmp", url=shown, symbol=sym, interval="1d", attempt=1, http_status=None, bytes=0,
                           elapsed_ms=int((time.time() - t0) * 1000), error=repr(e)[:300])
            out[sym] = f"error {e!r}"
            continue
        pc.log_request(service="fmp", url=shown, symbol=sym, interval="1d", attempt=1, http_status=st, bytes=len(body),
                       elapsed_ms=int((time.time() - t0) * 1000), error=None if st == 200 else body[:200].decode(errors="replace"))
        lg.info("fmp GET %s -> HTTP %s %dB", shown, st, len(body))
        fetched_at = pc.utcnow()
        raw = pc.root() / "raw" / "fmp" / f"{pc.qname(sym)}_{fetched_at:%Y%m%dT%H%M%S}Z.json"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(body)
        status, df = "error", None
        if st == 429:  # daily quota exhausted: record nothing so the symbol is retried tomorrow, and stop
            lg.warning("fmp HTTP 429 (daily limit) at %s -> stop", sym)
            out[sym] = "HTTP 429 -> stopped (retry tomorrow)"
            break
        if st == 402:
            status = "not_in_plan"
        elif st == 200:
            rows = json.loads(body)
            if isinstance(rows, list) and rows:
                df = pl.DataFrame(rows).select(
                    pl.col("date").str.to_date("%Y-%m-%d"),
                    *[pl.col(c).cast(pl.Float64) for c in ("open", "high", "low", "close", "volume")]).sort("date")
                df, _, _, _ = pc.finalize(df, "1d", fetched_at, None, None)
                status = "ok" if df.height else "empty"
            else:
                status = "empty"
        parsed = pc.Parsed(status, sym, "1d", df, {"currency": None, "exchange": "FMP", "granularity": "1d", "has_events": None})
        pc.store(sym, "1d", "fmp", parsed, {
            "requested_symbol": sym, "origin": "network", "import_source": "fmp", "path": str(raw),
            "sha256": hashlib.sha256(body).hexdigest(), "size": len(body), "fetched_at_utc": pc.iso(fetched_at),
            "fetched_at_basis": "network", "status": status, "url": shown, "n_rows": 0 if df is None else df.height,
            "first_key": str(df["date"].min()) if df is not None and df.height else None,
            "last_key": str(df["date"].max()) if df is not None and df.height else None,
            "cover_start": str(df["date"].min()) if df is not None and df.height else None,
            "cover_end": str(df["date"].max()) if df is not None and df.height else None,
            "note": "close is unadjusted EOD close (FMP historical-price-eod/full)"})
        out[sym] = f"HTTP {st} -> {status}"
    return {"calls_today": _fmp_calls_today(), "results": out}
