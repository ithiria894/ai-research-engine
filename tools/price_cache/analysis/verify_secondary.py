"""Check what each secondary source's `close` / `adjclose` really is, by comparing with Yahoo on shared symbols.

For every symbol that has both Yahoo 1d bars and secondary 1d bars, compute per-symbol median of
secondary.close / yahoo.close and secondary.close / yahoo.adjclose on overlapping dates. A source whose close
is dividend-adjusted has ratio-to-adjclose near a constant per symbol (equal to 1 only if the dividend history
since the dataset's snapshot is empty), so we report the share of symbols within 1 % of each.
Also reports coverage gained: symbols with secondary data but no Yahoo bars.
Usage: python3 analysis/verify_secondary.py   (reads ~/data/price-cache, writes reports/verify_secondary.csv)
"""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import price_cache as pc  # noqa: E402


def main() -> None:
    r = pc.root()
    ysyms = {p.stem for p in (r / "bars" / "1d").glob("*.parquet")}
    rows = []
    for sdir in sorted((r / "secondary").glob("*")):  # a handful of sources
        files = sorted((sdir / "1d").glob("*.parquet"))
        shared = [p for p in files if p.stem in ysyms]
        only = [p for p in files if p.stem not in ysyms]
        if shared:
            sec = pl.concat([pl.read_parquet(p, columns=["date", "close", "adjclose"]).with_columns(pl.lit(p.stem).alias("q"))
                             for p in shared], how="diagonal_relaxed")  # file reads (I/O)
            yah = pl.concat([pl.read_parquet(r / "bars" / "1d" / f"{p.stem}.parquet", columns=["date", "close", "adjclose"])
                             .with_columns(pl.lit(p.stem).alias("q")) for p in shared])
            j = sec.join(yah, on=["q", "date"], suffix="_y")
            per = j.group_by("q").agg(
                pl.len().alias("n_overlap"),
                (pl.col("close") / pl.col("close_y")).median().alias("r_close_vs_yclose"),
                (pl.col("close") / pl.col("adjclose_y")).median().alias("r_close_vs_yadj"),
                (pl.col("adjclose") / pl.col("adjclose_y")).median().alias("r_adj_vs_yadj"),
                # dispersion of the ratio inside one symbol: ~0 when the series are the same up to a constant
                ((pl.col("close") / pl.col("adjclose_y")).std() / (pl.col("close") / pl.col("adjclose_y")).mean()).alias("cv_close_vs_yadj"),
                ((pl.col("close") / pl.col("close_y")).std() / (pl.col("close") / pl.col("close_y")).mean()).alias("cv_close_vs_yclose"),
            ).filter(pl.col("n_overlap") >= 250)
            s = per.select(
                pl.len().alias("n_symbols_overlap>=250d"),
                ((pl.col("r_close_vs_yclose") - 1).abs() < 0.01).mean().alias("share_close≈yahoo_close(1%)"),
                ((pl.col("r_close_vs_yadj") - 1).abs() < 0.01).mean().alias("share_close≈yahoo_adjclose(1%)"),
                pl.col("cv_close_vs_yclose").median().alias("median_cv_vs_yclose"),
                pl.col("cv_close_vs_yadj").median().alias("median_cv_vs_yadj"),
                ((pl.col("r_adj_vs_yadj") - 1).abs() < 0.01).mean().alias("share_adj≈yahoo_adj(1%)"),
            ).to_dicts()[0]
        else:
            s = {}
        rows.append({"source_dir": sdir.name, "files": len(files), "shared_with_yahoo": len(shared),
                     "only_in_secondary": len(only), **s})
    out = pl.DataFrame(rows)
    (r / "reports").mkdir(exist_ok=True)
    out.write_csv(r / "reports" / "verify_secondary.csv")
    with pl.Config(tbl_cols=20, tbl_width_chars=250, fmt_str_lengths=60):
        print(out)


if __name__ == "__main__":
    main()
