#!/usr/bin/env python3
"""Scholarly search first: one query, five sources, merged by DOI, with retraction flags.

Spec: docs/research-workflow-spec.md section 5.

Commands:
  scholar.py search QUERY [--limit N]      OpenAlex + Crossref + Semantic Scholar + arXiv + Europe PMC
  scholar.py fulltext DOI                  legal open-access copy: OpenAlex, Europe PMC, Unpaywall*
  scholar.py retraction DOI [DOI ...]      OpenAlex is_retracted per DOI

* Unpaywall needs a contact address; it runs only when RESEARCH_CONTACT_EMAIL is set, and is
  otherwise reported as SKIPPED/unconfigured. No address is ever invented.

Every output includes a "ledger" list in research_run.py's vocabulary (MATERIAL/EMPTY/FAILED +
reason) so a failed provider is never mistaken for "no papers exist".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, NoReturn

UA = "research-engine-scholar/1.0"
TIMEOUT = 30
KEYS_FILE = os.path.expanduser("~/.config/research-engine/keys.env")


def openalex_key() -> str | None:
    """OPENALEX_API_KEY from the environment, else from keys.env (spec section 5)."""
    if os.environ.get("OPENALEX_API_KEY"):
        return os.environ["OPENALEX_API_KEY"]
    try:
        with open(KEYS_FILE, encoding="utf-8") as handle:
            for line in handle:
                m = re.match(r"\s*(?:export\s+)?OPENALEX_API_KEY=(.*)", line)
                if m and m.group(1).strip().strip("'\""):
                    return m.group(1).strip().strip("'\"")
    except OSError:
        pass
    return None


def log(event: str, **details: object) -> None:
    print("scholar-log " + json.dumps({"event": event, **details}, ensure_ascii=False), file=sys.stderr)


def die(message: str) -> NoReturn:
    print(f"scholar: {message}", file=sys.stderr)
    raise SystemExit(1)


def http_reason(status: int) -> str:
    return {429: "rate-limited", 401: "auth-failed", 402: "quota-exhausted", 403: "blocked",
            408: "timeout", 504: "timeout"}.get(status, "unreachable" if status >= 500 else "error")


class ProviderError(Exception):
    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason


def get(url: str, accept_json: bool = True) -> Any:
    headers = {"User-Agent": UA}
    keyed = False
    if urllib.parse.urlsplit(url).hostname == "api.openalex.org" and (key := openalex_key()):
        headers["Authorization"] = f"Bearer {key}"
        keyed = True
    log("external_call", url=url.split("?")[0], openalex_key=keyed if "openalex" in url else None)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:200].decode("utf-8", "replace").strip()
        log("external_error", url=url.split("?")[0], http_status=exc.code, body=detail)
        raise ProviderError(http_reason(exc.code), f"HTTP {exc.code}: {detail}" if detail else f"HTTP {exc.code}") from exc
    except TimeoutError as exc:
        raise ProviderError("timeout", str(exc)) from exc
    except OSError as exc:
        raise ProviderError("timeout" if "timed out" in str(exc).lower() else "unreachable", str(exc)) from exc
    if not accept_json:
        return body
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ProviderError("schema-drift", f"expected JSON: {exc}") from exc


def norm_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    value = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", value)
    return value or None


def norm_title(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "").lower()
    return re.sub(r"[^\w]+", " ", value).strip()


# ---------------------------------------------------------------- providers

def openalex(q: str, n: int) -> list[dict]:
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({
        "search": q, "per-page": n,
        "select": "doi,title,publication_year,cited_by_count,is_retracted,open_access,primary_location"})
    out = []
    for w in get(url).get("results", []):
        out.append({"title": w.get("title"), "year": w.get("publication_year"), "doi": norm_doi(w.get("doi")),
                    "citations": w.get("cited_by_count"), "is_retracted": w.get("is_retracted"),
                    "oa_url": (w.get("open_access") or {}).get("oa_url"),
                    "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name")})
    return out


def crossref(q: str, n: int) -> list[dict]:
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode({
        "query": q, "rows": n, "select": "DOI,title,issued,is-referenced-by-count,container-title"})
    out = []
    for w in get(url).get("message", {}).get("items", []):
        year = ((w.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        out.append({"title": (w.get("title") or [None])[0], "year": year, "doi": norm_doi(w.get("DOI")),
                    "citations": w.get("is-referenced-by-count"), "venue": (w.get("container-title") or [None])[0]})
    return out


def semantic_scholar(q: str, n: int) -> list[dict]:
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode({
        "query": q, "limit": n, "fields": "title,year,externalIds,citationCount,openAccessPdf,venue"})
    out = []
    for w in get(url).get("data", []):
        out.append({"title": w.get("title"), "year": w.get("year"), "doi": norm_doi((w.get("externalIds") or {}).get("DOI")),
                    "citations": w.get("citationCount"), "oa_url": (w.get("openAccessPdf") or {}).get("url"),
                    "venue": w.get("venue")})
    return out


def arxiv(q: str, n: int) -> list[dict]:
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": f"all:{q}", "max_results": n})
    body = get(url, accept_json=False)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ProviderError("schema-drift", f"arXiv Atom unparsable: {exc}") from exc
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    out = []
    for e in root.findall("a:entry", ns):
        doi = e.findtext("x:doi", default=None, namespaces=ns)
        pub = e.findtext("a:published", default="", namespaces=ns)
        pdf = next((l.get("href") for l in e.findall("a:link", ns) if l.get("title") == "pdf"), None)
        out.append({"title": re.sub(r"\s+", " ", e.findtext("a:title", default="", namespaces=ns)).strip(),
                    "year": int(pub[:4]) if pub[:4].isdigit() else None, "doi": norm_doi(doi),
                    "oa_url": pdf, "arxiv_id": (e.findtext("a:id", default="", namespaces=ns) or "").rsplit("/", 1)[-1]})
    return out


def europe_pmc(q: str, n: int) -> list[dict]:
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode({
        "query": q, "format": "json", "pageSize": n})
    out = []
    for w in get(url).get("resultList", {}).get("result", []):
        pmcid = w.get("pmcid")
        out.append({"title": w.get("title"), "year": int(w["pubYear"]) if str(w.get("pubYear", "")).isdigit() else None,
                    "doi": norm_doi(w.get("doi")), "citations": w.get("citedByCount"), "venue": w.get("journalTitle"),
                    "oa_url": f"https://europepmc.org/article/PMC/{pmcid}" if pmcid and w.get("isOpenAccess") == "Y" else None})
    return out


PROVIDERS = {"openalex": openalex, "crossref": crossref, "semantic-scholar": semantic_scholar,
             "arxiv": arxiv, "europe-pmc": europe_pmc}


# ---------------------------------------------------------------- merge

def merge(per_source: dict[str, list[dict]]) -> list[dict]:
    merged: dict[str, dict] = {}
    for source, works in per_source.items():
        for w in works:
            if not w.get("title"):
                continue
            # Normalise here too: a provider that forgets to lowercase must not split one work in two.
            doi = norm_doi(w.get("doi"))
            w = {**w, "doi": doi}
            key = f"doi:{doi}" if doi else f"t:{norm_title(w['title'])}|{w.get('year')}"
            cur = merged.get(key)
            if cur is None:
                merged[key] = {**w, "sources": [source]}
                continue
            cur["sources"].append(source)
            for field in ("doi", "venue", "oa_url", "year", "arxiv_id"):
                cur[field] = cur.get(field) or w.get(field)
            if (w.get("citations") or 0) > (cur.get("citations") or 0):
                cur["citations"] = w["citations"]
            if cur.get("is_retracted") is None and w.get("is_retracted") is not None:
                cur["is_retracted"] = w["is_retracted"]
    return sorted(merged.values(), key=lambda w: (-(len(w["sources"])), -(w.get("citations") or 0)))


def retraction_flags(dois: list[str]) -> tuple[dict[str, bool | None], dict]:
    """Batch-check OpenAlex is_retracted for DOIs that came only from other providers."""
    flags: dict[str, bool | None] = {}
    if not dois:
        return flags, {"source": "openalex-retraction", "status": "SKIPPED", "reason": "not-relevant"}
    try:
        for i in range(0, len(dois), 50):
            chunk = dois[i:i + 50]
            url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
                {"filter": "doi:" + "|".join(chunk), "per-page": 50, "select": "doi,is_retracted"})
            for w in get(url).get("results", []):
                d = norm_doi(w.get("doi"))
                if d:
                    flags[d] = w.get("is_retracted")
    except ProviderError as exc:
        return flags, {"source": "openalex-retraction", "status": "FAILED", "reason": exc.reason, "note": str(exc)}
    return flags, {"source": "openalex-retraction", "status": "MATERIAL" if flags else "EMPTY", "items": len(flags)}


def cmd_search(q: str, n: int) -> int:
    log("entry", command="search", query=q, limit=n)
    per_source, ledger = {}, []
    for name, fn in PROVIDERS.items():
        try:
            works = fn(q, n)
            per_source[name] = works
            ledger.append({"source": name, "status": "MATERIAL" if works else "EMPTY", "items": len(works)})
        except ProviderError as exc:
            ledger.append({"source": name, "status": "FAILED", "reason": exc.reason, "note": str(exc)})
            log("external_error", source=name, reason=exc.reason, detail=str(exc))
    works = merge(per_source)
    unknown = [w["doi"] for w in works if w.get("doi") and w.get("is_retracted") is None]
    flags, row = retraction_flags(unknown)
    ledger.append(row)
    for w in works:
        if w.get("doi") in flags:
            w["is_retracted"] = flags[w["doi"]]
    retracted = sum(1 for w in works if w.get("is_retracted"))
    log("decision", merged=len(works), retracted=retracted,
        failed=[r["source"] for r in ledger if r["status"] == "FAILED"])
    print(json.dumps({"query": q, "count": len(works), "retracted_count": retracted, "ledger": ledger,
                      "works": works}, ensure_ascii=False, indent=2))
    return 0 if any(r["status"] in {"MATERIAL", "EMPTY"} for r in ledger[:-1]) else 1


def cmd_fulltext(doi: str) -> int:
    doi = norm_doi(doi) or die("DOI is required")
    log("entry", command="fulltext", doi=doi)
    ledger, found = [], None
    try:
        w = get(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}?select=open_access,best_oa_location,is_retracted")
        loc = w.get("best_oa_location") or {}
        url = loc.get("pdf_url") or loc.get("landing_page_url") or (w.get("open_access") or {}).get("oa_url")
        ledger.append({"source": "openalex", "status": "MATERIAL" if url else "EMPTY", "items": 1 if url else 0})
        found = found or ({"url": url, "via": "openalex", "is_retracted": w.get("is_retracted")} if url else None)
    except ProviderError as exc:
        ledger.append({"source": "openalex", "status": "FAILED", "reason": exc.reason, "note": str(exc)})
    try:
        r = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
            {"query": f'DOI:"{doi}"', "format": "json", "resultType": "core"}))
        hits = r.get("resultList", {}).get("result", [])
        urls = [u.get("url") for h in hits for u in (h.get("fullTextUrlList") or {}).get("fullTextUrl", [])
                if u.get("availabilityCode") in {"OA", "F"}]
        ledger.append({"source": "europe-pmc", "status": "MATERIAL" if urls else "EMPTY", "items": len(urls)})
        found = found or ({"url": urls[0], "via": "europe-pmc"} if urls else None)
    except ProviderError as exc:
        ledger.append({"source": "europe-pmc", "status": "FAILED", "reason": exc.reason, "note": str(exc)})
    email = os.environ.get("RESEARCH_CONTACT_EMAIL")
    if not email:
        ledger.append({"source": "unpaywall", "status": "SKIPPED", "reason": "unconfigured",
                       "note": "set RESEARCH_CONTACT_EMAIL to enable"})
    else:
        try:
            r = get(f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?" + urllib.parse.urlencode({"email": email}))
            loc = r.get("best_oa_location") or {}
            url = loc.get("url_for_pdf") or loc.get("url")
            ledger.append({"source": "unpaywall", "status": "MATERIAL" if url else "EMPTY", "items": 1 if url else 0})
            found = found or ({"url": url, "via": "unpaywall"} if url else None)
        except ProviderError as exc:
            ledger.append({"source": "unpaywall", "status": "FAILED", "reason": exc.reason, "note": str(exc)})
    log("decision", command="fulltext", found=bool(found), via=(found or {}).get("via"))
    print(json.dumps({"doi": doi, "fulltext": found, "ledger": ledger}, ensure_ascii=False, indent=2))
    return 0


def cmd_retraction(dois: list[str]) -> int:
    clean = [d for d in (norm_doi(x) for x in dois) if d]
    flags, row = retraction_flags(clean)
    print(json.dumps({"results": {d: flags.get(d) for d in clean}, "ledger": [row]}, ensure_ascii=False, indent=2))
    return 1 if row["status"] == "FAILED" else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("search"); p.add_argument("query"); p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("fulltext"); p.add_argument("doi")
    p = sub.add_parser("retraction"); p.add_argument("dois", nargs="+")
    a = parser.parse_args()
    if a.cmd == "search":
        if not a.query.strip():
            die("QUERY must not be empty")
        if not 1 <= a.limit <= 50:
            die("--limit must be between 1 and 50")
        raise SystemExit(cmd_search(a.query, a.limit))
    if a.cmd == "fulltext":
        raise SystemExit(cmd_fulltext(a.doi))
    raise SystemExit(cmd_retraction(a.dois))


if __name__ == "__main__":
    main()
