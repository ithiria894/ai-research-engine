"""Coverage numbers for the cache, straight from the ledger. Writes reports/coverage_summary.json.

Usage: python3 analysis/coverage_summary.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import price_cache as pc  # noqa: E402


def main() -> None:
    with pc.db() as con:
        f = pl.read_database("SELECT symbol, interval, source, import_source, status, first_key, last_key FROM fetches "
                             "WHERE state='done'", con, infer_schema_length=None)
        nconf = con.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0]
    y = f.filter(pl.col("source") == "yahoo")
    yok = y.filter(pl.col("status") == "ok")
    per_import = (y.group_by("import_source").agg(
        pl.len().alias("files"), (pl.col("status") == "ok").sum().alias("ok_files"),
        (pl.col("status") == "not_found").sum().alias("404_files"), (pl.col("status") == "empty").sum().alias("empty_files"),
        pl.col("symbol").filter(pl.col("status") == "ok").n_unique().alias("ok_symbols")).sort("import_source"))
    ok_syms = set(yok["symbol"])
    nf_only = set(y.filter(pl.col("status") == "not_found")["symbol"]) - ok_syms
    multi = yok.filter(pl.col("interval") == "1d").group_by("symbol").agg(pl.len().alias("n")).filter(pl.col("n") >= 2)
    sec = f.filter((pl.col("source") != "yahoo") & (pl.col("status") == "ok") & (pl.col("interval") == "1d"))
    sec_per = (sec.group_by("source").agg(
        pl.col("symbol").n_unique().alias("symbols"),
        pl.col("symbol").filter(~pl.col("symbol").is_in(list(ok_syms))).n_unique().alias("symbols_without_yahoo"),
        pl.col("symbol").filter(pl.col("symbol").is_in(list(nf_only))).n_unique().alias("yahoo_404_symbols_covered"),
        pl.col("first_key").min().alias("first"), pl.col("last_key").max().alias("last")).sort("source"))
    gained = sec.filter(pl.col("symbol").is_in(list(nf_only)))["symbol"].n_unique()
    out = {
        "yahoo_symbols_with_bars": {iv: yok.filter(pl.col("interval") == iv)["symbol"].n_unique() for iv in pc.INTERVALS},
        "yahoo_symbols_with_any_bars": len(ok_syms),
        "yahoo_404_or_empty_only_symbols": len(nf_only),
        "symbols_1d_imported_from_2plus_files": multi.height,
        "per_import_source": per_import.to_dicts(),
        "secondary_per_source": sec_per.to_dicts(),
        "yahoo_404_symbols_covered_by_any_secondary": gained,
        "conflicts": nconf,
        "size_mb": {k: round(v / 2**20, 1) for k, v in pc.status()["size_bytes"].items()},
    }
    (pc.root() / "reports").mkdir(exist_ok=True)
    (pc.root() / "reports" / "coverage_summary.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
