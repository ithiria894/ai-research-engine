"""Independent check of the 0-conflict result: re-read the ORIGINAL files (not the cache) for symbols that
were imported from 2+ files, and compute max |adjclose_a/adjclose_b - 1| on shared dates with plain json +
polars, without using price_cache's merge code. Usage: python3 analysis/crosscheck_raw_overlaps.py [N]
"""
from __future__ import annotations

import gzip
import json
import sqlite3
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import price_cache as pc  # noqa: E402


def load(path: str) -> pl.DataFrame:
    b = Path(path).read_bytes()
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    r = json.loads(b)["chart"]["result"][0]
    tz = r["meta"]["exchangeTimezoneName"]
    adj = r["indicators"]["adjclose"][0]["adjclose"]
    return (pl.DataFrame({"t": r["timestamp"], "adj": pl.Series(adj, dtype=pl.Float64, strict=False)})
            .with_columns(pl.from_epoch("t").dt.replace_time_zone("UTC").dt.convert_time_zone(tz).dt.date().alias("d"))
            .drop_nulls("adj").unique("d", keep="last"))


def main(n: int) -> None:
    con = sqlite3.connect(pc.root() / "ledger.sqlite")
    rows = con.execute("""SELECT symbol, group_concat(path, '|') FROM fetches WHERE source='yahoo' AND status='ok'
                          AND interval='1d' AND origin='import' GROUP BY symbol HAVING COUNT(*) >= 2
                          ORDER BY symbol""").fetchall()
    step = max(1, len(rows) // n)
    out = []
    for sym, paths in rows[::step][:n]:  # sample spread across the alphabet (I/O per file)
        ps = paths.split("|")
        a = load(ps[0])
        for p in ps[1:]:
            j = a.join(load(p), on="d", suffix="_b")
            j = j.filter(pl.col("d") < pl.lit(pc.utcnow().date()))  # drop the open bar
            m = j.select(((pl.col("adj_b") / pl.col("adj")) - 1).abs().max()).item() if j.height else None
            out.append({"symbol": sym, "file_a": Path(ps[0]).parent.name, "file_b": Path(p).parent.name,
                        "n_shared": j.height, "max_rel_diff": m})
    df = pl.DataFrame(out)
    print(f"symbols with >=2 imported files: {len(rows)}; checked {df['symbol'].n_unique()} symbols / {df.height} pairs")
    print(df.select(pl.col("n_shared").sum(), (pl.col("max_rel_diff") > 0.005).sum().alias("pairs_over_0.5pct"),
                    pl.col("max_rel_diff").max().alias("worst")))
    print(df.sort("max_rel_diff", descending=True, nulls_last=True).head(5))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
