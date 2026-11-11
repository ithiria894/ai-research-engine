"""Read-only importers: bring every existing on-disk price download into the shared cache.

Never writes to, moves or deletes the source folders. Re-runnable: a file is skipped when the ledger already
has the same path with the same size+mtime (or the same sha256). Files modified within --min-age-min minutes
are treated as still being written and skipped (a later run picks them up).
"""
from __future__ import annotations

import fnmatch
import gzip
import json
import os
import time
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

import polars as pl

import price_cache as pc

HOME = Path.home()


@dataclass
class Source:
    name: str
    globs: list[Path | str]
    kind: str = "yahoo_json"  # yahoo_json | binance_klines
    name_fn: Callable[[str], str | None] | None = None  # filename -> requested symbol (None = unknown/mangled)
    plain_names: bool = False  # filename-derived name is a real ticker -> register as alias
    events_requested: bool | None = True
    req_start: date | None = None  # period1 the study used (None = unknown -> first bar)
    ledger: Callable[[], dict[str, list[str]]] | None = None  # requested-name -> fetched_at ISO strings
    ledger_key: str = "plain"  # ledger names vs file names: plain | quote (file = URL-quoted ticker)


def _strip(fname: str, prefixes: tuple[str, ...] = (), suffixes: tuple[str, ...] = (".json.gz", ".json", ".404")) -> str:
    for s in suffixes:
        if fname.endswith(s):
            fname = fname[: -len(s)]
            break
    for p in prefixes:
        if fname.startswith(p):
            fname = fname[len(p):]
    return fname


# ----------------------------------------------------------------------------------------------- local config
# Which folders to import is machine-specific, so the list lives next to the data, not in this repo:
#   $PRICE_CACHE_SOURCES  or  <cache root>/import_sources.json      (format: import_sources.example.json)


def config_path() -> Path:
    return Path(os.environ.get("PRICE_CACHE_SOURCES", str(pc.root() / "import_sources.json"))).expanduser()


def load_config() -> dict[str, Any]:
    p = config_path()
    if not p.exists():
        pc.log().warning("no import config at %s -> nothing to import (see import_sources.example.json)", p)
        return {"sources": [], "discover": {}, "referenced": []}
    return json.loads(p.read_text())


def _xp(s: str) -> Path:
    return Path(os.path.expandvars(s)).expanduser()


def _name_fn(mode: str | None) -> Callable[[str], str | None] | None:
    """Filename -> requested ticker: plain (strip .json/.json.gz/.404), unquote, strip_prefix:<p>, or None."""
    if not mode:
        return None
    if mode == "plain":
        return lambda f: _strip(f)
    if mode == "unquote":
        return lambda f: urllib.parse.unquote(_strip(f))
    if mode.startswith("strip_prefix:"):
        pre = mode.split(":", 1)[1]
        return lambda f: _strip(f, (pre,))
    raise ValueError(f"unknown names mode {mode!r}")


def _ledger_fn(spec: dict[str, Any] | None) -> Callable[[], dict[str, list[str]]] | None:
    """A study's own fetch log -> {name: [fetched_at, ...]}. types: table (csv/tsv) | json_global."""
    if not spec:
        return None

    def load() -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        if spec["type"] == "json_global":
            p = _xp(spec["path"])
            t = json.loads(p.read_text()).get(spec.get("field", "fetched_at_utc")) if p.exists() else None
            return {"*": [t]} if t else {}
        sep = spec.get("sep", ",")
        for ps in spec["paths"]:
            p = _xp(ps)
            if not p.exists():
                continue
            d = pl.read_csv(p, separator=sep, infer_schema_length=0, quote_char=None if sep == "\t" else '"')
            d = d.select(pl.col(spec.get("symbol_col", "symbol")).alias("s"),
                         pl.col(spec.get("time_col", "fetched_at_utc")).alias("t")).drop_nulls()
            names = d["s"].to_list()
            if spec.get("key") == "quote":
                names = [urllib.parse.quote(x, safe="") for x in names]  # small ledger
            for s, t in zip(names, d["t"].to_list()):
                out.setdefault(s, []).append(t)
        return out

    return load


def sources_from_config(cfg: dict[str, Any]) -> list[Source]:
    out = []
    for s in cfg.get("sources", []):
        rs = s.get("req_start")
        out.append(Source(
            name=s["name"], globs=[_xp(g) for g in s["globs"]], kind=s.get("kind", "yahoo_json"),
            name_fn=_name_fn(s.get("names")), plain_names=bool(s.get("names_are_tickers", False)),
            events_requested=s.get("events_requested", True),
            req_start=(pc.EPOCH_START if rs == "listing" else date.fromisoformat(rs)) if rs else None,
            ledger=_ledger_fn(s.get("ledger")), ledger_key=(s.get("ledger") or {}).get("key", "plain")))
    return out


def _read_bytes(p: Path) -> bytes:
    b = p.read_bytes()
    return gzip.decompress(b) if p.name.endswith(".gz") or b[:2] == b"\x1f\x8b" else b


def _iter_source_files(src: Source) -> Iterator[Path]:
    for g in src.globs:
        g = Path(g)
        yield from sorted(g.parent.glob(g.name))


DEFAULT_SKIP_DIRS = {"price-cache", ".git", "node_modules", "__pycache__"}


def _discover(known: set[str], dcfg: dict[str, Any], globs: list[str]) -> list[tuple[Source, Path]]:
    """Any other Yahoo chart JSON under the configured trees -> import source discovered:<dir>.
    Files matching a configured source glob are never 'discovered' (they belong to that source)."""
    roots: list[Path] = [_xp(r) for r in dcfg.get("roots", [])]
    for g in dcfg.get("dir_globs", []):  # e.g. "~/data/*/yahoo*"
        base, _, pat = g.partition("*")
        roots += [q for q in _xp(base).glob("*" + pat) if q.is_dir()]
    own = pc.root().resolve()
    roots = [q for q in roots if not q.resolve().is_relative_to(own)]  # never re-import the cache's own raw files
    skip = DEFAULT_SKIP_DIRS | set(dcfg.get("skip_dirs", []))
    label_base = _xp(dcfg.get("label_base", "~"))
    out: list[tuple[Source, Path]] = []
    seen: set[str] = set()
    for r in roots:
        for dp, dn, fn in os.walk(r):  # filesystem walk (I/O)
            dn[:] = [d for d in dn if d not in skip]
            for f in fn:
                if not (f.endswith(".json") or f.endswith(".json.gz")):
                    continue
                p = Path(dp) / f
                sp = str(p)
                if sp in known or sp in seen or any(fnmatch.fnmatch(sp, g) for g in globs):
                    continue
                seen.add(sp)
                try:
                    if p.stat().st_size > 50_000_000:
                        continue
                    with (gzip.open(p, "rb") if f.endswith(".gz") else open(p, "rb")) as fh:
                        head = fh.read(400)
                except OSError:
                    continue
                if b'"chart"' not in head:
                    continue
                rel = str(Path(dp).relative_to(label_base)) if Path(dp).is_relative_to(label_base) else dp
                out.append((Source(f"discovered:{rel}", [], events_requested=None), p))
    return out


def _fetched_at(src: Source, p: Path, requested: str | None, ledgers: dict[str, dict[str, list[str]]]) -> tuple[datetime, str]:
    mt = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
    led = ledgers.get(src.name) or {}
    cands = led.get(requested or "", []) or led.get(_strip(p.name), []) or led.get("*", [])
    best = None
    for t in cands:  # few entries per symbol
        try:
            d = pc.parse_iso(t)
        except ValueError:
            continue
        if d is not None and abs((d - mt).total_seconds()) <= 2 * 3600 and (best is None or abs((d - mt).total_seconds()) < abs((best - mt).total_seconds())):
            best = d
    return (best, "ledger") if best else (mt, "mtime")


def _symbol_from_url(obj: Any) -> str | None:
    if isinstance(obj, dict) and isinstance(obj.get("url"), str) and "/chart/" in obj["url"]:
        return urllib.parse.unquote(obj["url"].split("/chart/")[1].split("?")[0])
    return None


def _parse_binance(body: bytes, fetched_at: datetime) -> tuple[pl.DataFrame, int, str | None, str | None]:
    rows = json.loads(body)
    if not rows:
        return pl.DataFrame(), 0, None, None
    df = pl.DataFrame(rows, orient="row", schema=[f"c{i}" for i in range(len(rows[0]))])
    df = df.select(
        pl.from_epoch(pl.col("c0").cast(pl.Int64), time_unit="ms").dt.replace_time_zone("UTC").dt.cast_time_unit("us").alias("ts"),
        *[pl.col(f"c{i}").cast(pl.Float64).alias(n) for i, n in ((1, "open"), (2, "high"), (3, "low"), (4, "close"), (5, "volume"))],
        pl.from_epoch(pl.col("c6").cast(pl.Int64), time_unit="ms").dt.replace_time_zone("UTC").alias("_close_time"),
    )
    n0 = df.height
    df = df.filter(pl.col("_close_time") < pl.lit(fetched_at)).drop("_close_time")
    if not df.height:
        return df, n0, None, None
    return df, n0 - df.height, pc.iso(df["ts"].min()), pc.iso(df["ts"].max() + timedelta(hours=1))


def _already(con, p: Path) -> tuple[bool, str | None]:
    st = p.stat()
    rows = con.execute("SELECT size, mtime, sha256, state FROM fetches WHERE path=?", (str(p),)).fetchall()
    for r in rows:
        if r["state"] == "done" and r["size"] == st.st_size and r["mtime"] is not None and abs(r["mtime"] - st.st_mtime) < 1e-3:
            return True, r["sha256"]
    if rows:
        sha = pc.sha256_file(p)
        if any(r["sha256"] == sha and r["state"] == "done" for r in rows):
            return True, sha
        return False, sha
    return False, None


def import_file(src: Source, p: Path, ledgers: dict[str, dict[str, list[str]]], sha: str | None = None) -> dict[str, Any]:
    lg = pc.log()
    body = _read_bytes(p)
    raw_sha = sha or pc.sha256_file(p)
    st = p.stat()
    requested = src.name_fn(p.name) if src.name_fn else None
    fetched_at, basis = _fetched_at(src, p, _strip(p.name) if src.ledger_key == "quote" else requested, ledgers)
    base = {"origin": "import", "import_source": src.name, "path": str(p), "sha256": raw_sha, "size": st.st_size,
            "mtime": st.st_mtime, "fetched_at_utc": pc.iso(fetched_at), "fetched_at_basis": basis}
    if src.kind == "binance_klines":
        sym = p.name.split("_")[1]
        df, dropped, cs, ce = _parse_binance(body, fetched_at)
        parsed = pc.Parsed("ok" if df.height else "empty", sym, "1h", df,
                           {"currency": sym[-4:] if sym.endswith("USDT") else None, "exchange": "Binance spot",
                            "instrument_type": "CRYPTOCURRENCY", "timezone": "UTC", "granularity": "1h", "has_events": None})
        fid = pc.store(sym, "1h", "binance", parsed, {**base, "requested_symbol": sym, "status": parsed.status,
                                                     "n_rows": df.height, "n_dropped_provisional": dropped,
                                                     "cover_start": cs, "cover_end": ce,
                                                     "first_key": cs, "last_key": str(df["ts"].max()) if df.height else None})
        return {"symbol": sym, "status": parsed.status, "interval": "1h", "fetch_id": fid, "source": "binance"}
    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        obj = None
    if obj is None:
        parsed = pc.Parsed("error", note="non-json body")
    elif isinstance(obj, dict) and "chart" not in obj:
        parsed = pc.Parsed("error", note=f"not a chart object: {json.dumps(obj)[:200]}")
        requested = requested or _symbol_from_url(obj)
    else:
        parsed = pc.parse_chart(obj, events_requested=src.events_requested)
    if p.name.endswith(".404") and parsed.status == "error":
        parsed.status = "not_found"
    sym = parsed.symbol or (pc.canon(requested) if requested else None)
    if sym is None:
        lg.warning("import %s: cannot determine symbol (status=%s note=%s) -> skipped", p, parsed.status, parsed.note)
        return {"symbol": None, "status": "unknown_symbol", "path": str(p)}
    interval = parsed.interval or "1d"
    fetch = {**base, "requested_symbol": requested, "status": parsed.status, "note": parsed.note}
    if parsed.status == "ok":
        assert parsed.df is not None
        df, dropped, cs, ce = pc.finalize(parsed.df, interval, fetched_at, parsed.info.get("first_trade_epoch"),
                                          src.req_start if interval != "1h" else None)
        parsed.df = df
        k = pc.key_col(interval)
        if not df.height:
            parsed.status = "empty"
        fetch.update(status=parsed.status, n_rows=df.height, n_dropped_provisional=dropped, cover_start=cs, cover_end=ce,
                     first_key=str(df[k].min()) if df.height else None, last_key=str(df[k].max()) if df.height else None)
    if src.plain_names and requested and pc.canon(requested) != sym:
        pc.add_alias(requested, sym, src.name)
    if interval not in pc.INTERVALS:
        lg.warning("import %s: granularity %s not supported -> recorded only", p, interval)
        parsed.status, parsed.df = "unsupported_interval", None
        fetch["status"] = parsed.status
    fid = pc.store(sym, interval if interval in pc.INTERVALS else "1d", "yahoo", parsed, fetch)
    return {"symbol": sym, "status": parsed.status, "interval": interval, "fetch_id": fid, "source": "yahoo"}


def import_existing(min_age_min: float = 10.0, only: str | None = None, discover: bool = True) -> dict[str, Any]:
    lg = pc.log()
    t0 = time.time()
    cutoff = time.time() - min_age_min * 60
    lg.info("import-existing start min_age_min=%s only=%s discover=%s", min_age_min, only, discover)
    cfg = load_config()
    srcs = sources_from_config(cfg)
    lg.info("import config %s: %d sources", config_path(), len(srcs))
    ledgers = {s.name: (s.ledger() if s.ledger else {}) for s in srcs}
    todo: list[tuple[Source, Path]] = []
    known: set[str] = set()
    for s in srcs:
        for p in _iter_source_files(s):
            known.add(str(p))
            todo.append((s, p))
    if discover:
        disc = _discover(known, cfg.get("discover", {}), [str(g) for s in srcs for g in s.globs])
        lg.info("discovery found %d extra chart JSON files in %d dirs", len(disc), len({s.name for s, _ in disc}))
        todo += disc
    if only:
        todo = [(s, p) for s, p in todo if s.name == only]
    summary: dict[str, dict[str, int]] = {}
    skipped_fresh: dict[str, int] = {}
    # oldest first so that in the common case the newer fetch is the one being merged in
    todo.sort(key=lambda sp: sp[1].stat().st_mtime)
    for i, (s, p) in enumerate(todo, 1):  # loop over files = I/O
        try:
            if p.stat().st_mtime > cutoff:
                skipped_fresh[s.name] = skipped_fresh.get(s.name, 0) + 1
                continue
            with pc.db() as con:
                done, sha = _already(con, p)
                con.execute("DELETE FROM fetches WHERE path=? AND state='pending'", (str(p),))
            if done:
                summary.setdefault(s.name, {}).setdefault("already_imported", 0)
                summary[s.name]["already_imported"] += 1
                continue
            r = import_file(s, p, ledgers, sha)
            summary.setdefault(s.name, {}).setdefault(r["status"], 0)
            summary[s.name][r["status"]] += 1
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the import
            lg.exception("import %s %s failed: %r", s.name, p, e)
            summary.setdefault(s.name, {}).setdefault("exception", 0)
            summary[s.name]["exception"] += 1
        if i % 500 == 0:
            lg.info("import progress %d/%d (%.0fs)", i, len(todo), time.time() - t0)
    res = {"files_seen": len(todo), "by_source": summary, "skipped_modified_last_%dmin" % min_age_min: skipped_fresh,
           "seconds": round(time.time() - t0, 1)}
    lg.info("import-existing done %s", json.dumps(res, ensure_ascii=False))
    return res


# ----------------------------------------------------------------------------------------------- missing report
def referenced_symbols() -> dict[str, list[str]]:
    """Symbols each study asked for, read-only from the input lists named in the config's `referenced`."""
    out: dict[str, set[str]] = {}
    for r in load_config().get("referenced", []):
        p = _xp(r["path"])
        acc = out.setdefault(r["study"], set())
        acc |= set(r.get("extra", []))
        if not p.exists():
            pc.log().warning("referenced list missing: %s", p)
            continue
        col = r["column"]
        s = (pl.read_parquet(p, columns=[col])[col] if p.suffix == ".parquet" else
             pl.read_csv(p, infer_schema_length=0, separator=r.get("sep", ","))[col])
        if r.get("explode"):
            s = s.explode()
        acc |= set(s.drop_nulls().cast(pl.Utf8).to_list())
    return {k: sorted(v) for k, v in out.items()}


def referenced_groups() -> pl.DataFrame:
    """For entries with `group_col` (one event/idea -> several candidate tickers): long frame study, group, requested."""
    frames = []
    for r in load_config().get("referenced", []):
        if not r.get("group_col"):
            continue
        p = _xp(r["path"])
        if not p.exists():
            continue
        cols = [r["group_col"], r["column"]] + ([r["date_col"]] if r.get("date_col") else [])
        d = pl.read_parquet(p, columns=cols) if p.suffix == ".parquet" else pl.read_csv(p, infer_schema_length=0, separator=r.get("sep", ","), columns=cols)
        if r.get("explode"):
            d = d.explode(r["column"])
        dt = pl.col(r["date_col"]).cast(pl.Utf8).str.slice(0, 10).str.to_date(strict=False) if r.get("date_col") else pl.lit(None, pl.Date)
        frames.append(d.select(pl.lit(r["study"]).alias("study"), pl.col(r["group_col"]).cast(pl.Utf8).alias("group"),
                               pl.col(r["column"]).cast(pl.Utf8).alias("requested"), dt.alias("event_date"))
                      .drop_nulls(["group", "requested"]))
    return pl.concat(frames) if frames else pl.DataFrame(schema={"study": pl.Utf8, "group": pl.Utf8, "requested": pl.Utf8, "event_date": pl.Date})


def missing_report(out_path: str | None = None) -> dict[str, Any]:
    refs = referenced_symbols()
    with pc.db() as con:
        f = pl.read_database("SELECT symbol, interval, source, status, import_source FROM fetches WHERE state='done'", con,
                             infer_schema_length=None)
        al = pl.read_database("SELECT alias, symbol FROM aliases", con, infer_schema_length=None)
    have_1d = set(f.filter((pl.col("status") == "ok") & (pl.col("source") == "yahoo") & (pl.col("interval") == "1d"))["symbol"].to_list())
    have_any = set(f.filter(pl.col("status") == "ok")["symbol"].to_list())
    secondary = set(f.filter((pl.col("status") == "ok") & (pl.col("source") != "yahoo") & (pl.col("interval") == "1d"))["symbol"].to_list())
    nf = set(f.filter((pl.col("status") == "not_found") & (pl.col("source") == "yahoo"))["symbol"].to_list())
    tried = set(f.filter(pl.col("source") == "yahoo")["symbol"].to_list())
    amap = dict(al.iter_rows()) if al.height else {}
    rows = []
    for study, syms in refs.items():  # 3 studies; body vectorised below
        d = pl.DataFrame({"study": study, "requested": syms}).with_columns(
            pl.col("requested").str.strip_chars().str.to_uppercase().replace(amap).alias("symbol"))
        d = d.with_columns(
            pl.col("symbol").is_in(list(have_1d)).alias("has_yahoo_1d"),
            pl.col("symbol").is_in(list(have_any)).alias("has_any_bars"),
            pl.col("symbol").is_in(list(secondary)).alias("has_secondary_1d"),
            pl.col("symbol").is_in(list(nf)).alias("yahoo_404"),
            pl.col("symbol").is_in(list(tried)).alias("yahoo_attempted"),
        )
        rows.append(d)
    rep = pl.concat(rows) if rows else pl.DataFrame()
    summ = (rep.group_by("study").agg(
        pl.len().alias("referenced"), pl.col("has_yahoo_1d").sum().alias("have_yahoo_1d"),
        (~pl.col("has_yahoo_1d") & pl.col("has_secondary_1d")).sum().alias("missing_yahoo_but_secondary"),
        (~pl.col("has_yahoo_1d") & ~pl.col("has_secondary_1d")).sum().alias("missing_all"),
        (~pl.col("has_yahoo_1d") & pl.col("yahoo_404")).sum().alias("missing_yahoo_404"),
        (~pl.col("has_yahoo_1d") & ~pl.col("yahoo_attempted")).sum().alias("missing_never_fetched"),
    ).sort("study")) if rep.height else pl.DataFrame()
    g = referenced_groups()
    gsum = pl.DataFrame()
    if g.height:
        with pc.db() as con:
            spans = pl.read_database("SELECT symbol, source, first_key, last_key FROM fetches WHERE status='ok' AND interval='1d' AND state='done'",
                                     con, infer_schema_length=None)
        spans = spans.with_columns(pl.col("first_key").str.slice(0, 10).str.to_date(strict=False), pl.col("last_key").str.slice(0, 10).str.to_date(strict=False),
                                   (pl.col("source") == "yahoo").alias("is_y"))
        sp = spans.group_by(["symbol", "is_y"]).agg(pl.col("first_key").min().alias("a"), pl.col("last_key").max().alias("b"))
        ysp = sp.filter(pl.col("is_y")).select("symbol", pl.col("a").alias("ya"), pl.col("b").alias("yb"))
        ssp = sp.filter(~pl.col("is_y")).select("symbol", pl.col("a").alias("sa"), pl.col("b").alias("sb"))
        g = (g.with_columns(pl.col("requested").str.strip_chars().str.to_uppercase().replace(amap).alias("symbol"))
             .join(ysp, on="symbol", how="left").join(ssp, on="symbol", how="left")
             .with_columns(pl.col("ya").is_not_null().alias("y"), pl.col("sa").is_not_null().alias("s"),
                           pl.col("event_date").is_between(pl.col("ya"), pl.col("yb")).fill_null(False).alias("y_on_date"),
                           pl.col("event_date").is_between(pl.col("sa"), pl.col("sb")).fill_null(False).alias("s_on_date")))
        gsum = (g.group_by(["study", "group"]).agg(
                    pl.col("y").any(), (pl.col("y") | pl.col("s")).any().alias("ys"),
                    pl.col("event_date").is_not_null().any().alias("has_date"),
                    pl.col("y_on_date").any().alias("yd"), (pl.col("y_on_date") | pl.col("s_on_date")).any().alias("ysd"),
                    pl.col("symbol").is_in(list(tried)).any().alias("t"))
                .group_by("study").agg(pl.len().alias("groups"), pl.col("y").sum().alias("groups_with_yahoo_1d"),
                                       pl.col("ys").sum().alias("groups_with_yahoo_or_secondary"),
                                       pl.col("has_date").sum().alias("groups_with_date"),
                                       pl.col("yd").sum().alias("groups_yahoo_covers_event_date"),
                                       pl.col("ysd").sum().alias("groups_yahoo_or_secondary_covers_event_date"),
                                       (~pl.col("t")).sum().alias("groups_no_candidate_fetched_yet")).sort("study"))
    outd = pc.root() / "reports"
    outd.mkdir(parents=True, exist_ok=True)
    p = Path(out_path) if out_path else outd / f"missing_{pc.utcnow():%Y%m%dT%H%M}Z.csv"
    rep.filter(~pl.col("has_yahoo_1d")).sort(["study", "symbol"]).write_csv(p)
    pc.log().info("missing-report written %s", p)
    return {"summary": summ.to_dicts(), "group_level": gsum.to_dicts(), "detail_csv": str(p)}
