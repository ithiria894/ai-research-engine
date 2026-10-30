#!/usr/bin/env python3
"""OpenSanctions sanctions/PEP lookup from the public bulk data, kept on this machine.

Commands:
  opensanctions.py update [--force]     download the latest `default` targets.simple.csv and index it
  opensanctions.py search QUERY [--limit N] [--schema S] [--country CC]
  opensanctions.py status

Why bulk instead of the API (2026-10-30): the hosted API needs paid credits (our trial
key is "disabled", 0 credits), while data.opensanctions.org publishes the same data for
free under CC BY-NC 4.0 (non-commercial use). yente, the official self-hosted API, needs a
resident Elasticsearch, so we index the official CSV artifact in SQLite instead.

Data lives in $OPENSANCTIONS_DIR (default ~/.local/share/research-engine/data/opensanctions):
  <version>/targets.simple.csv   the official artifact, SHA-1 checked against index.json
  <version>/targets.sqlite       FTS5 trigram index over name, aliases and identifiers
  current                        text file naming the active version
Only the active version is kept; an older version directory is removed after a new one
has been downloaded, verified and indexed. Everything is rebuildable with `update --force`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
from typing import NoReturn
import urllib.error
import urllib.request

INDEX_URL = "https://data.opensanctions.org/datasets/latest/default/index.json"
RESOURCE = "targets.simple.csv"
DATA_DIR = Path(os.environ.get("OPENSANCTIONS_DIR",
                               Path.home() / ".local/share/research-engine/data/opensanctions"))
USER_AGENT = "research-engine/1.0 (non-commercial research)"
LICENSE = "CC BY-NC 4.0, https://www.opensanctions.org/licensing/"
COLUMNS = ["id", "schema", "name", "aliases", "birth_date", "countries", "addresses", "identifiers",
           "sanctions", "phones", "emails", "program_ids", "dataset", "first_seen", "last_seen",
           "last_change"]


def log(event: str, **details: object) -> None:
    print("opensanctions-log " + json.dumps({"event": event, **details}, ensure_ascii=False), file=sys.stderr)


def die(message: str, reason: str = "error", code: int = 1) -> NoReturn:
    log("failure", reason=reason, message=message)
    print(f"opensanctions: [{reason}] {message}", file=sys.stderr)
    raise SystemExit(code)


def http_reason(status: int) -> str:
    if status == 429:
        return "rate-limited"
    if status in (401, 403):
        return "blocked"
    return "error"


def fetch_index() -> dict:
    log("external_call", url=INDEX_URL)
    request = urllib.request.Request(INDEX_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        die(f"HTTP {exc.code} from {INDEX_URL}", http_reason(exc.code))
    except (urllib.error.URLError, TimeoutError) as exc:
        die(f"cannot reach {INDEX_URL}: {exc}", "unreachable")
    except json.JSONDecodeError as exc:
        die(f"index.json is not JSON: {exc}", "schema-drift")


def current_version() -> str | None:
    marker = DATA_DIR / "current"
    return marker.read_text().strip() if marker.exists() else None


def download(url: str, dest: Path, size: int, sha1: str) -> None:
    log("external_call", url=url, expected_bytes=size)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest, written, started = hashlib.sha1(), 0, time.time()
    partial = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
                digest.update(chunk)
                written += len(chunk)
    except urllib.error.HTTPError as exc:
        partial.unlink(missing_ok=True)
        die(f"HTTP {exc.code} downloading {url}", http_reason(exc.code))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        partial.unlink(missing_ok=True)
        die(f"download failed after {written} bytes: {exc}", "timeout" if isinstance(exc, TimeoutError) else "unreachable")
    log("state_change", downloaded_bytes=written, seconds=round(time.time() - started, 1))
    if written != size or digest.hexdigest() != sha1:
        partial.unlink(missing_ok=True)
        die(f"checksum mismatch: got {written} bytes sha1 {digest.hexdigest()}, index says {size} / {sha1}",
            "parse-error")
    partial.rename(dest)


def build_index(csv_path: Path, db_path: Path) -> int:
    partial = db_path.with_suffix(".sqlite.part")
    partial.unlink(missing_ok=True)
    con = sqlite3.connect(partial)
    con.execute(f"CREATE TABLE targets({', '.join(c + ' TEXT' for c in COLUMNS)})")
    # trigram: names come in Latin, Cyrillic, Arabic and CJK scripts with no common word boundary.
    con.execute("CREATE VIRTUAL TABLE names USING fts5(name, aliases, identifiers, content='targets', "
                "content_rowid='rowid', tokenize='trigram')")
    csv.field_size_limit(1 << 30)
    rows = 0
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != COLUMNS:
            partial.unlink(missing_ok=True)
            die(f"CSV header changed: {header}", "schema-drift")
        batch = []
        for row in reader:
            batch.append(row)
            if len(batch) == 50_000:
                con.executemany(f"INSERT INTO targets VALUES ({','.join('?' * len(COLUMNS))})", batch)
                rows += len(batch)
                batch.clear()
        if batch:
            con.executemany(f"INSERT INTO targets VALUES ({','.join('?' * len(COLUMNS))})", batch)
            rows += len(batch)
    con.execute("INSERT INTO names(rowid, name, aliases, identifiers) SELECT rowid, name, aliases, identifiers FROM targets")
    con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
    con.commit()
    con.close()
    partial.rename(db_path)
    log("state_change", indexed_rows=rows, db=str(db_path))
    return rows


def cmd_update(force: bool) -> None:
    index = fetch_index()
    version = index.get("version")
    resource = next((r for r in index.get("resources", []) if r.get("name") == RESOURCE), None)
    if not version or not resource or not resource.get("url") or not resource.get("checksum"):
        die(f"index.json has no {RESOURCE} with url+checksum (keys: {sorted(index)})", "schema-drift")
    active = current_version()
    log("entry", command="update", remote_version=version, local_version=active, force=force)
    if active == version and not force and (DATA_DIR / version / "targets.sqlite").exists():
        log("decision", action="skip", why="already at remote version")
        print(json.dumps({"status": "up-to-date", "version": version}, ensure_ascii=False))
        return
    work = DATA_DIR / version
    work.mkdir(parents=True, exist_ok=True)
    csv_path, db_path = work / RESOURCE, work / "targets.sqlite"
    if force or not csv_path.exists():
        download(resource["url"], csv_path, int(resource["size"]), resource["checksum"])
    rows = build_index(csv_path, db_path)
    con = sqlite3.connect(db_path)
    con.executemany("INSERT OR REPLACE INTO meta VALUES (?, ?)", [
        ("version", version), ("updated_at", str(index.get("updated_at"))), ("source_url", resource["url"]),
        ("sha1", resource["checksum"]), ("rows", str(rows)), ("license", LICENSE)])
    con.commit()
    con.close()
    (DATA_DIR / "current").write_text(version + "\n")
    log("state_change", current_before=active, current_after=version)
    for old in DATA_DIR.iterdir():
        if old.is_dir() and old.name != version:
            log("state_change", removed_old_version=old.name)
            shutil.rmtree(old)
    print(json.dumps({"status": "updated", "version": version, "rows": rows,
                      "db_bytes": db_path.stat().st_size}, ensure_ascii=False))


def open_db() -> tuple[sqlite3.Connection, dict]:
    version = current_version()
    db_path = DATA_DIR / version / "targets.sqlite" if version else None
    if not db_path or not db_path.exists():
        die(f"no local OpenSanctions data yet; run: opensanctions.py update  (dir {DATA_DIR})", "unconfigured")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    meta = dict(con.execute("SELECT key, value FROM meta"))
    return con, meta


def cmd_search(query: str, limit: int, schema: str | None, country: str | None) -> None:
    query = query.strip()
    if not query:
        die("QUERY must not be empty")
    con, meta = open_db()
    terms = query.split()
    long_terms = [t for t in terms if len(t) >= 3]
    short_terms = [t for t in terms if len(t) < 3]
    where, params = [], []
    sql = "SELECT t.* FROM targets t"
    if long_terms:
        sql += " JOIN names ON names.rowid = t.rowid"
        where.append("names MATCH ?")
        params.append(" AND ".join('"' + t.replace('"', '""') + '"' for t in long_terms))
    for t in short_terms:  # trigram MATCH silently matches nothing below 3 characters
        where.append("instr(lower(t.name || ' ' || t.aliases || ' ' || t.identifiers), lower(?)) > 0")
        params.append(t)
    if schema:
        where.append("t.schema = ?")
        params.append(schema)
    if country:
        where.append("(';' || t.countries || ';') LIKE ?")
        params.append(f"%;{country.lower()};%")
    # Exact name first, then names containing the whole query; order only, nothing is dropped.
    sql += (" WHERE " + " AND ".join(where) +
            " ORDER BY lower(t.name) = lower(?) DESC, instr(lower(t.name), lower(?)) > 0 DESC LIMIT ?")
    rows = con.execute(sql, params + [query, query, limit]).fetchall()
    log("decision", command="search", query=query, schema=schema, country=country, hits=len(rows),
        version=meta.get("version"))
    print(json.dumps({
        "status": "ok" if rows else "empty",
        "query": query,
        "data_version": meta.get("version"),
        "data_updated_at": meta.get("updated_at"),
        "license": meta.get("license"),
        "note": "substring match on name/aliases/identifiers; a hit is a name match, not an identity match",
        "count": len(rows),
        "results": [dict(zip(COLUMNS, row)) for row in rows],
    }, ensure_ascii=False, indent=2))


def cmd_status() -> None:
    con, meta = open_db()
    rows = con.execute("SELECT count(*) FROM targets").fetchone()[0]
    print(json.dumps({"dir": str(DATA_DIR), **meta, "rows_in_db": rows}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("update")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--schema", help="e.g. Person, Company, Vessel")
    p.add_argument("--country", help="ISO code as used by OpenSanctions, e.g. ru, cn, hk")
    sub.add_parser("status")
    args = parser.parse_args()
    if args.cmd == "update":
        cmd_update(args.force)
    elif args.cmd == "search":
        if not 1 <= args.limit <= 500:
            die("--limit must be between 1 and 500")
        cmd_search(args.query, args.limit, args.schema, args.country)
    else:
        cmd_status()


if __name__ == "__main__":
    main()
