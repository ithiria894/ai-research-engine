"""E2E-ish tests for the shared price cache. Every test runs against a throw-away PRICE_CACHE_ROOT.

Run: cd tools/price_cache && python3 -m pytest -q tests/
No test touches the real network: price_cache.http_get is replaced by fakes that count calls.
"""
from __future__ import annotations

import json
import os
import multiprocessing as mp
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import polars as pl
import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import importers  # noqa: E402
import price_cache as pc  # noqa: E402

# Two known symbols. By default synthetic Yahoo-format files are generated; set PRICE_CACHE_TEST_REAL_FILES to a
# comma list of real SPY and QQQ chart JSON downloads to run the same checks against real data.
REAL_ENV = os.environ.get("PRICE_CACHE_TEST_REAL_FILES")


@pytest.fixture()
def root(tmp_path, monkeypatch):
    r = tmp_path / "cache"
    monkeypatch.setenv("PRICE_CACHE_ROOT", str(r))
    monkeypatch.setenv("PRICE_CACHE_QUIET", "1")
    monkeypatch.setenv("PRICE_CACHE_RATE_PER_S", "50")
    pc.NETWORK_CALLS = 0
    return r


def chart_json(symbol: str, days: list[date], closes: list[float], adj: list[float] | None = None,
               divs: dict[date, float] | None = None, first_trade: date | None = None) -> bytes:
    """Minimal Yahoo v8 chart body (NYSE-like: bars at 14:30 UTC)."""
    ts = [int(datetime(d.year, d.month, d.day, 14, 30, tzinfo=timezone.utc).timestamp()) for d in days]
    res = {"meta": {"symbol": symbol, "currency": "USD", "exchangeName": "PCX", "fullExchangeName": "NYSEArca",
                    "instrumentType": "ETF", "exchangeTimezoneName": "America/New_York", "dataGranularity": "1d",
                    "firstTradeDate": int(datetime.combine(first_trade or days[0], datetime.min.time(), timezone.utc).timestamp()) + 52200},
           "timestamp": ts,
           "indicators": {"quote": [{"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1000] * len(ts)}],
                          "adjclose": [{"adjclose": adj or closes}]}}
    if divs:
        res["events"] = {"dividends": {str(t): {"amount": a, "date": int(datetime(d.year, d.month, d.day, 14, 30, tzinfo=timezone.utc).timestamp())}
                                       for (d, a), t in zip(divs.items(), range(len(divs)))}}
    return json.dumps({"chart": {"result": [res], "error": None}}).encode()


def bdays(a: date, b: date) -> list[date]:
    s = pl.date_range(a, b, "1d", eager=True)
    return s.filter(s.dt.weekday() <= 5).to_list()


def write_known_files(d: Path) -> list[Path]:
    if REAL_ENV:
        out = []
        for f in REAL_ENV.split(","):
            shutil.copy2(f, d / Path(f).name)
            out.append(d / Path(f).name)
        return out
    days = bdays(date(1999, 3, 10), date(2026, 11, 6))
    n = len(days)
    out = []
    for s, base in (("SPY", 120.0), ("QQQ", 50.0)):
        closes = [base + i * 0.05 for i in range(n)]
        divs = {days[i]: 0.5 for i in range(60, n, 63)}  # quarterly
        p = d / f"yahoo_{s}.json"
        p.write_bytes(chart_json(s, days, closes, adj=[c * 0.9 for c in closes], divs=divs, first_trade=days[0]))
        out.append(p)
    return out


def import_real(tmp_path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    write_known_files(src_dir)
    src = importers.Source("test-src", [src_dir / "yahoo_*.json"], req_start=pc.EPOCH_START)
    for p in sorted(src_dir.glob("*.json")):
        importers.import_file(src, p, {})


# ------------------------------------------------------------------------------------------------ tests
def test_import_two_known_symbols_schema_and_meta(root, tmp_path):
    import_real(tmp_path)
    for s in ("SPY", "QQQ"):
        df = pc.read_bars(s)
        assert df.schema == pl.Schema(pc.DAILY_SCHEMA), df.schema
        assert df.height > 6000
        assert df["date"].is_sorted() and df["date"].n_unique() == df.height
        assert df.filter(pl.col("close").is_null()).height == 0
        assert df["dividends"].sum() > 0  # SPY/QQQ pay dividends; events were parsed
        assert df["date"].max() < pc.utcnow().date()  # today's provisional bar never stored
    m = pl.read_parquet(pc.export_meta()["meta"])
    assert set(m["symbol"]) == {"SPY", "QQQ"}
    row = m.filter(pl.col("symbol") == "SPY").row(0, named=True)
    assert row["currency"] == "USD" and row["source"] == "yahoo" and row["first_date"][:4] in ("1993", "1999")
    assert row["sha256s"][0] == pc.sha256_file(tmp_path / "src" / "yahoo_SPY.json")


def test_reimport_is_noop(root, tmp_path):
    import_real(tmp_path)
    with pc.db() as con:
        n0 = con.execute("SELECT COUNT(*) FROM fetches").fetchone()[0]
        for p in (tmp_path / "src").glob("*.json"):
            done, _ = importers._already(con, p)
            assert done
    assert n0 == 2


def test_second_get_makes_zero_network_calls(root, tmp_path, monkeypatch):
    import_real(tmp_path)
    calls = []

    def boom(url, timeout=40.0):
        calls.append(url)
        raise AssertionError("network must not be touched")

    monkeypatch.setattr(pc, "http_get", boom)
    a = pc.get("SPY", "2015-01-01", "2020-12-31")
    b = pc.get("spy", "2015-01-01", "2020-12-31")  # case-insensitive, same answer
    assert calls == [] and a.height > 1500 and a.equals(b)


def test_missing_range_fetched_once_then_cached(root, monkeypatch):
    days = bdays(date(2020, 1, 1), date(2020, 3, 31))
    calls = []

    def fake(url, timeout=40.0):
        calls.append(url)
        return 200, chart_json("ZZZT", days, [100.0 + i for i in range(len(days))], first_trade=date(2020, 1, 2))

    monkeypatch.setattr(pc, "http_get", fake)
    d1 = pc.get("ZZZT", "2020-01-01", "2020-03-31")
    d2 = pc.get("ZZZT", "2020-01-01", "2020-03-31")
    d3 = pc.get("ZZZT", "2020-02-01", "2020-02-28")
    assert len(calls) == 1, calls
    assert d1.height == len(days) and d1.equals(d2) and d3.height < d1.height
    assert "events=div%2Csplits" in calls[0] and "interval=1d" in calls[0]
    with pc.db() as con:
        assert con.execute("SELECT COUNT(*) FROM requests WHERE http_status=200").fetchone()[0] == 1
    raw = list((root / "raw" / "yahoo" / "1d").rglob("*.json.gz"))
    assert len(raw) == 1


def test_404_is_negatively_cached(root, monkeypatch):
    calls = []

    def fake(url, timeout=40.0):
        calls.append(url)
        return 404, b'{"chart":{"result":null,"error":{"code":"Not Found","description":"No data found, symbol may be delisted"}}}'

    monkeypatch.setattr(pc, "http_get", fake)
    assert pc.get("DEADCO", "2010-01-01", "2010-12-31").height == 0
    assert pc.get("DEADCO", "2010-01-01", "2010-12-31").height == 0
    assert len(calls) == 1


def test_429_retries_with_shared_pause(root, monkeypatch):
    days = bdays(date(2021, 1, 4), date(2021, 1, 29))
    seq = [429, 200]
    monkeypatch.setattr(pc, "MAX_ATTEMPTS", 3)
    monkeypatch.setattr(pc.YAHOO_LIMITER, "penalize", lambda s: None)  # don't sleep 30 s in a unit test

    def fake(url, timeout=40.0):
        st = seq.pop(0)
        return st, (b"Too Many Requests" if st == 429 else chart_json("RTRY", days, [1.0] * len(days)))

    monkeypatch.setattr(pc, "http_get", fake)
    assert pc.get("RTRY", "2021-01-04", "2021-01-29").height == len(days)
    with pc.db() as con:
        sts = [r[0] for r in con.execute("SELECT http_status FROM requests ORDER BY id")]
        urls = [r[0] for r in con.execute("SELECT url FROM requests ORDER BY id")]
    assert sts == [429, 200] and "query1" in urls[0] and "query2" in urls[1]


def test_merge_rebase_and_conflicts(root):
    """Old fetch, then a dividend, then a new fetch: Yahoo rescales old adjclose by 0.98.
    Expect: scale-type conflicts logged, older-only rows rebased onto the new basis, newer wins; plus one
    genuine bad value (kind=value)."""
    days = bdays(date(2022, 1, 3), date(2022, 6, 30))
    n = len(days)
    old_close = [100.0] * n
    old = pc.parse_chart(json.loads(chart_json("RBS", days, old_close, first_trade=date(2022, 1, 3))))
    # new fetch only covers March-June (gap fill), adjclose 2% lower; one bad print on day 100
    sub = days[40:]
    new_adj = [98.0] * len(sub)
    new_adj[60] = 120.0
    new = pc.parse_chart(json.loads(chart_json("RBS", sub, [100.0] * len(sub), adj=new_adj, first_trade=date(2022, 1, 3))))
    t_old, t_new = "2022-07-01T00:00:00.000000Z", "2022-08-01T00:00:00.000000Z"
    pc.store("RBS", "1d", "yahoo", old, {"origin": "test", "status": "ok", "fetched_at_utc": t_old})
    pc.store("RBS", "1d", "yahoo", new, {"origin": "test", "status": "ok", "fetched_at_utc": t_new})
    df = pc.read_bars("RBS")
    assert df.height == n
    first40 = df.head(40)["adjclose"]
    assert ((first40 - 98.0).abs() < 1e-9).all(), first40  # older-only rows rebased to the new basis
    assert df.filter(pl.col("date") == sub[60])["adjclose"].item() == 120.0  # newer wins
    with pc.db() as con:
        kinds = dict(con.execute("SELECT kind, COUNT(*) FROM conflicts WHERE symbol='RBS' GROUP BY 1").fetchall())
    assert kinds.get("value") == 1 and kinds.get("scale") == len(sub) - 1, kinds
    pc.export_meta()
    c = pl.read_parquet(root / "conflicts" / "conflicts.parquet")
    assert {"value_existing", "value_new", "winner_fetch_id"} <= set(c.columns)


def test_older_import_after_newer_keeps_newer_basis(root):
    days = bdays(date(2023, 1, 2), date(2023, 2, 28))
    newer = pc.parse_chart(json.loads(chart_json("ORD", days[20:], [50.0] * (len(days) - 20), first_trade=date(2023, 1, 2))))
    older = pc.parse_chart(json.loads(chart_json("ORD", days, [50.0] * len(days), adj=[51.0] * len(days), first_trade=date(2023, 1, 2))))
    pc.store("ORD", "1d", "yahoo", newer, {"origin": "test", "status": "ok", "fetched_at_utc": "2023-03-02T00:00:00.000000Z"})
    pc.store("ORD", "1d", "yahoo", older, {"origin": "test", "status": "ok", "fetched_at_utc": "2023-03-01T00:00:00.000000Z"})
    df = pc.read_bars("ORD")
    assert df.height == len(days) and ((df["adjclose"] - 50.0).abs() < 1e-9).all()


def _acquire_many(root_s: str, n: int, q) -> None:
    import os
    os.environ["PRICE_CACHE_ROOT"] = root_s
    os.environ["PRICE_CACHE_RATE_PER_S"] = "5"  # 0.2 s spacing
    os.environ["PRICE_CACHE_QUIET"] = "1"
    sys.path.insert(0, str(HERE))
    import price_cache as p2
    out = []
    for _ in range(n):
        out.append(p2.YAHOO_LIMITER.acquire())
    q.put(out)


def test_lock_prevents_concurrent_bursts(root):
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    procs = [ctx.Process(target=_acquire_many, args=(str(root), 4, q)) for _ in range(5)]
    t0 = time.time()
    for p in procs:
        p.start()
    stamps = sorted(s for _ in procs for s in q.get(timeout=60))
    for p in procs:
        p.join(30)
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert len(stamps) == 20
    assert min(gaps) >= 0.2 - 0.02, gaps  # never two grants closer than 1/rate across 5 processes
    assert stamps[-1] - stamps[0] >= 19 * 0.2 - 0.05
    assert time.time() - t0 < 60


def _concurrent_get(root_s: str, counter: str, q) -> None:
    import os
    os.environ["PRICE_CACHE_ROOT"] = root_s
    os.environ["PRICE_CACHE_RATE_PER_S"] = "50"
    os.environ["PRICE_CACHE_QUIET"] = "1"
    sys.path.insert(0, str(HERE))
    import price_cache as p2
    days = bdays(date(2019, 1, 2), date(2019, 2, 28))

    def fake(url, timeout=40.0):
        with open(counter, "a") as fh:
            fh.write(url + "\n")
        time.sleep(0.5)
        return 200, chart_json("CONC", days, [10.0] * len(days), first_trade=date(2019, 1, 2))

    p2.http_get = fake
    q.put(p2.get("CONC", "2019-01-02", "2019-02-28").height)


def test_concurrent_get_same_symbol_downloads_once(root, tmp_path):
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    counter = tmp_path / "calls.txt"
    procs = [ctx.Process(target=_concurrent_get, args=(str(root), str(counter), q)) for _ in range(4)]
    for p in procs:
        p.start()
    heights = [q.get(timeout=60) for _ in procs]
    for p in procs:
        p.join(30)
    assert len(set(heights)) == 1 and heights[0] > 30
    assert len(counter.read_text().splitlines()) == 1


def test_offline_never_fetches(root, monkeypatch):
    monkeypatch.setattr(pc, "http_get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("net")))
    assert pc.get("NOPE", "2020-01-01", "2020-02-01", offline=True).height == 0


def test_bad_interval_rejected(root):
    with pytest.raises(ValueError):
        pc.get("SPY", interval="5m")


def test_kaggle_secondary_kept_apart_and_tagged(root, monkeypatch):
    """A boris-format Kaggle zip imports under secondary/, never into Yahoo bars; source='any' tags rows."""
    import zipfile
    import secondary
    ref = "borismarjanovic/price-volume-data-for-all-us-stocks-etfs"
    d = root / "raw" / "kaggle" / ref.replace("/", "__")
    d.mkdir(parents=True)
    with zipfile.ZipFile(d / "x.zip", "w") as z:
        z.writestr("Data/Stocks/gone.us.txt", "Date,Open,High,Low,Close,Volume,OpenInt\r\n2015-01-02,1,1,1,1.5,10,0\r\n2015-01-05,1,1,1,1.6,10,0\r\n")
        z.writestr("Stocks/gone.us.txt", "duplicate copy, must be ignored")
    r = secondary.kaggle_import(ref)
    assert r["stats"] == {"ok": 1}
    assert secondary.kaggle_import(ref)["stats"] == {"already": 1}  # re-runnable
    monkeypatch.setattr(pc, "http_get", lambda url, timeout=40.0: (404, b'{"chart":{"result":null,"error":{"code":"Not Found","description":"x"}}}'))
    assert pc.get("GONE", "2015-01-01", "2015-01-31").height == 0  # Yahoo-only stays empty
    anyd = pc.get("GONE", "2015-01-01", "2015-01-31", source="any")
    assert anyd.height == 2 and set(anyd["source"]) == {f"kaggle:{ref}"}
    assert not pc.bars_path("GONE", "1d").exists()


def test_import_existing_from_config_skips_fresh_files_and_reruns(root, tmp_path):
    """Config-driven import: files written <10 min ago are skipped (an agent may still be writing them),
    old files import once, a re-run imports nothing new, and a 404 body becomes a negative-cache row."""
    import os as _os
    src_dir = tmp_path / "study"
    src_dir.mkdir()
    files = write_known_files(src_dir)
    (src_dir / "DEADCO.json").write_bytes(b'{"chart":{"result":null,"error":{"code":"Not Found","description":"x"}}}')
    old = time.time() - 3600
    for p in [*files, src_dir / "DEADCO.json"]:
        _os.utime(p, (old, old))
    fresh = src_dir / "yahoo_NEWX.json"
    fresh.write_bytes(chart_json("NEWX", bdays(date(2024, 1, 2), date(2024, 2, 1)), [1.0] * 23))
    root.mkdir(parents=True, exist_ok=True)
    (root / "import_sources.json").write_text(json.dumps({"sources": [
        {"name": "study", "globs": [str(src_dir / "*.json")], "names": "strip_prefix:yahoo_", "names_are_tickers": True,
         "req_start": "listing"}]}))
    r1 = importers.import_existing(min_age_min=10, discover=False)
    assert r1["by_source"]["study"] == {"ok": 2, "not_found": 1}
    assert r1["skipped_modified_last_10min"] == {"study": 1}
    r2 = importers.import_existing(min_age_min=10, discover=False)
    assert r2["by_source"]["study"] == {"already_imported": 3}
    _os.utime(fresh, (old, old))
    r3 = importers.import_existing(min_age_min=10, discover=False)
    assert r3["by_source"]["study"].get("ok") == 1  # the late file is picked up on the next run
    gaps, flag = pc.missing_ranges("DEADCO", "1d", date(2010, 1, 1), date(2010, 2, 1))
    assert flag == "not_found"


def test_zero_prices_are_not_conflicts(root):
    days = bdays(date(2001, 9, 3), date(2001, 9, 28))
    a = pc.parse_chart(json.loads(chart_json("ZERO", days, [0.0] * len(days))))
    b = pc.parse_chart(json.loads(chart_json("ZERO", days, [0.0] * len(days))))
    pc.store("ZERO", "1d", "yahoo", a, {"origin": "test", "status": "ok", "fetched_at_utc": "2001-10-01T00:00:00.000000Z"})
    pc.store("ZERO", "1d", "yahoo", b, {"origin": "test", "status": "ok", "fetched_at_utc": "2001-10-02T00:00:00.000000Z"})
    with pc.db() as con:
        assert con.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0] == 0


def test_discovery_ignores_cache_own_raw_files(root, tmp_path, monkeypatch):
    days = bdays(date(2021, 1, 4), date(2021, 1, 29))
    monkeypatch.setattr(pc, "http_get", lambda url, timeout=40.0: (200, chart_json("OWNR", days, [1.0] * len(days))))
    pc.get("OWNR", "2021-01-04", "2021-01-29")
    raw = next((root / "raw").rglob("*.json.gz"))
    import os as _os
    _os.utime(raw, (time.time() - 3600,) * 2)
    (root / "import_sources.json").write_text(json.dumps({"sources": [], "discover": {"dir_globs": [str(root) + "/raw/*"]}}))
    r = importers.import_existing(min_age_min=10)
    assert r["files_seen"] == 0, r
