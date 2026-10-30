#!/usr/bin/env python3
"""Research library: full-text index over past run folders (spec section 8).

Commands:
  library.py index [ROOT ...]       (re)index run folders under ROOTs (default $RESEARCH_RUNS_DIR)
  library.py search QUERY [--limit N]
  library.py list

The SQLite DB ($RESEARCH_LIBRARY_DB, default ~/.local/share/research-engine/library.sqlite) is a
cache: run folders are the record, and `index` rebuilds the DB from them at any time.
Past findings are dated context for a new question, never fresh evidence.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from typing import NoReturn

RUNS_DIR = Path(os.environ.get("RESEARCH_RUNS_DIR", Path.home() / "MyGithub/research-runs"))
DB = Path(os.environ.get("RESEARCH_LIBRARY_DB", Path.home() / ".local/share/research-engine/library.sqlite"))
TEXT_EXT = {".txt", ".md", ".json", ".html", ".htm", ".xml", ".csv"}
MAX_DOC = 2_000_000


def log(event: str, **details: object) -> None:
    print("library-log " + json.dumps({"event": event, **details}, ensure_ascii=False), file=sys.stderr)


def die(message: str) -> NoReturn:
    print(f"library: {message}", file=sys.stderr)
    raise SystemExit(1)


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS runs(run TEXT PRIMARY KEY, path TEXT, date TEXT, query TEXT)")
    # trigram tokenizer handles Chinese/Korean text that has no spaces between words.
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(run UNINDEXED, kind UNINDEXED, "
                "name UNINDEXED, body, tokenize='trigram')")
    return con


def strip_html(text: str) -> str:
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))


def cmd_index(roots: list[Path]) -> None:
    con = connect()
    runs = sorted({q.parent for root in roots if root.exists() for q in root.rglob("query.md")})
    log("entry", command="index", roots=[str(r) for r in roots], runs=len(runs))
    con.execute("DELETE FROM docs"); con.execute("DELETE FROM runs")
    docs = 0
    for run in runs:
        name = run.name
        date = name[:10] if re.match(r"\d{4}-\d{2}-\d{2}", name) else ""
        query = (run / "query.md").read_text(encoding="utf-8", errors="replace").strip()
        con.execute("INSERT INTO runs VALUES (?,?,?,?)", (name, str(run), date, query))
        files = [(run / "query.md", "query"), (run / "report.md", "report"), (run / "ledger.jsonl", "ledger"),
                 (run / "plan.md", "plan")]
        files += [(p, "evidence") for p in sorted((run / "evidence").glob("*")) if p.suffix in TEXT_EXT
                  and not p.name.endswith(".meta.json")] if (run / "evidence").exists() else []
        for path, kind in files:
            if not path.exists():
                continue
            body = path.read_bytes()[:MAX_DOC].decode("utf-8", "replace")
            if path.suffix in {".html", ".htm", ".xml"}:
                body = strip_html(body)
            con.execute("INSERT INTO docs VALUES (?,?,?,?)", (name, kind, path.name, body))
            docs += 1
    con.commit()
    log("state_change", indexed_runs=len(runs), indexed_docs=docs, db=str(DB))
    print(json.dumps({"runs": len(runs), "docs": docs, "db": str(DB)}, ensure_ascii=False))


def cmd_search(query: str, limit: int) -> None:
    if not DB.exists():
        die(f"no library yet; run: library.py index  (db {DB})")
    con = connect()
    terms = [t for t in re.split(r"\s+", query.strip()) if t]
    if not terms:
        die("QUERY must not be empty")
    # trigram FTS needs >= 3 characters per term. Shorter terms use instr(): on a trigram table
    # LIKE/GLOB with < 3 chars silently match nothing (verified 2026-10-30, SQLite 3.37).
    long_terms = [t for t in terms if len(t) >= 3]
    short_terms = [t for t in terms if len(t) < 3]
    sql = "SELECT d.run, r.date, r.query, d.kind, d.name, snippet(docs, 3, '[', ']', '…', 12) FROM docs d JOIN runs r ON r.run = d.run"
    where, params = [], []
    if long_terms:
        where.append("docs MATCH ?"); params.append(" AND ".join('"' + t.replace('"', '""') + '"' for t in long_terms))
    for t in short_terms:
        where.append("instr(lower(d.body), lower(?)) > 0"); params.append(t)
    sql += " WHERE " + " AND ".join(where) + " ORDER BY r.date DESC LIMIT ?"
    rows = con.execute(sql, params + [limit]).fetchall()
    log("decision", command="search", query=query, hits=len(rows))
    print(json.dumps({"query": query, "count": len(rows), "note": "past runs are dated context, not fresh evidence",
                      "hits": [{"run": r[0], "date": r[1], "original_question": r[2], "kind": r[3], "file": r[4],
                                "snippet": r[5]} for r in rows]}, ensure_ascii=False, indent=2))


def cmd_list() -> None:
    if not DB.exists():
        die(f"no library yet; run: library.py index  (db {DB})")
    rows = connect().execute("SELECT run, date, query FROM runs ORDER BY date DESC").fetchall()
    print(json.dumps([{"run": r[0], "date": r[1], "question": r[2][:200]} for r in rows], ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("index"); p.add_argument("roots", nargs="*")
    p = sub.add_parser("search"); p.add_argument("query"); p.add_argument("--limit", type=int, default=10)
    sub.add_parser("list")
    a = parser.parse_args()
    if a.cmd == "index":
        cmd_index([Path(r).expanduser() for r in a.roots] or [RUNS_DIR])
    elif a.cmd == "search":
        if not 1 <= a.limit <= 200:
            die("--limit must be between 1 and 200")
        cmd_search(a.query, a.limit)
    else:
        cmd_list()


if __name__ == "__main__":
    main()
