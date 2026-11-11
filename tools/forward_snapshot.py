#!/usr/bin/env python3
"""Weekly snapshot of volatile public data for the 2026-11-11 forward test (pre-registration in PersonalDoc:
financial/reports/investing/kol-research-2026-11/預先登記-2026-11-11.md, section 「要每星期影相嘅會消失來源」).

Sources (each independent; one failing never stops the others):
  etoro                 public rankings, first ETORO_PAGES x ETORO_PAGESIZE rows (same query as the working
                        hidden-gold-2026-11 fetch), plus each listed user's public gain history (monthly/yearly)
  polymarket            Data API v2 leaderboard, PNL board, time_period all/month/week, first 5,000 rows each
  cryptokrios           /creators list page + every /creators/<slug> page (each embeds latest <=5 calls)
  youtube_lists         per list-A channel: yt-dlp --flat-playlist of /videos and /streams tabs (latest 30)
  youtube_upload_dates  per-video exact upload date via yt-dlp for videos not yet dated; appends the
                        per-channel CSV (append-only) with today's rows

Layout : ~/data/forward-snapshots/<source>/<YYYY-MM-DD UTC>/  raw files (*.gz) + MANIFEST.json
         ~/data/forward-snapshots/LEDGER.tsv               one row per source per run
         ~/data/forward-snapshots/youtube/channel_map.tsv  name -> channel resolution (made once by `resolve`)
         ~/data/forward-snapshots/youtube/videos/<key>.csv append-only per channel
         ~/data/forward-snapshots/logs/<date>.log          full run log
Usage  : forward_snapshot.py resolve [--force]            # once: build channel_map.tsv
         forward_snapshot.py run [--only etoro,polymarket] [--force]
         forward_snapshot.py status
README : tools/forward_snapshot_README.md
"""
import argparse, csv, datetime as dt, fcntl, gzip, hashlib, html, io, json, logging, os, re, shutil
import subprocess, sys, tempfile, threading, time, traceback, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path.home() / "data" / "forward-snapshots"
LEDGER = ROOT / "LEDGER.tsv"
LEDGER_COLS = ["timestamp_utc", "source", "status", "files", "bytes", "manifest_sha256", "dir", "error"]
MIN_FREE_GB = 20
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
YTDLP = shutil.which("yt-dlp") or str(Path.home() / ".local/bin/yt-dlp")

# eToro: query copied from hidden-gold-2026-11/raw/INDEX.tsv (etoro_sapi_rankings.json, HTTP 200 on 2026-11-11).
# 6 pages x 100 = 600 users; each user's gain history is one more request at ~1.5 s spacing -> ~18 min.
ETORO_RANK = ("https://www.etoro.com/sapi/rankings/rankings/?blocked=false&bonusonly=false&copyblock=false"
              "&istestaccount=false&optin=true&page={page}&pagesize={ps}&period=OneYearAgo&sort=-gain"
              "&verified=true&isfund=false")
ETORO_GAIN = "https://www.etoro.com/sapi/userstats/gain/cid/{cid}/history"
ETORO_PAGES, ETORO_PAGESIZE, ETORO_PAUSE = 6, 100, 1.5
# Polymarket: same endpoint as hidden-gold-2026-11/scripts/pm_fetch.sh; 5 pages x 1000 per board via cursor.
PM_BASE = "https://data-api.polymarket.com/v2/leaderboard"
PM_PERIODS, PM_PAGES, PM_LIMIT, PM_PAUSE = ("all", "month", "week"), 5, 1000, 2.0
# CryptoKrios: same pages as kol-research-2026-11/逐個預測數據/scripts/ck_fetch_all_creators.sh (curl, 2 s spacing)
CK_BASE, CK_PAUSE = "https://cryptokrios.com", 2.0
CK_PREREG = ["stefan-stoean", "bitcoin-hoy", "crypto-world", "lexa-moon-crypto", "cryptosrus",
             "advance-crypto-trader", "crypto-le-trone", "cilinix-crypto", "moshin", "virtualbacon"]
# YouTube
YT_N, YT_TABS, YT_PAUSE, YT_VIDEO_PAUSE, YT_BOTCHECK_TRIP = 30, ("videos", "streams"), 3.0, 3.0, 3

# List A of the pre-registration, in its order. `how` says where the channel URL comes from (see cmd_resolve).
LIST_A = [
    # (list, name as written in the pre-registration, key, how, ref)
    *[("A-cryptokrios", n, s, "cryptokrios_youtubeUrl", s) for n, s in [
        ("Stefan Stoean", "stefan-stoean"), ("Bitcoin hoy", "bitcoin-hoy"), ("Crypto World", "crypto-world"),
        ("Lexa Moon Crypto", "lexa-moon-crypto"), ("CryptosRUs", "cryptosrus"),
        ("Advance Crypto Trader", "advance-crypto-trader"), ("Crypto Le Trone", "crypto-le-trone"),
        ("Cilinix Crypto", "cilinix-crypto"), ("Moshin", "moshin"), ("VirtualBacon", "virtualbacon")]],
    *[("A-youtuberstocks", n, "bv-" + s, "bullvox_article_link_then_profile_handle", s) for n, s in [
        ("FINANZFOKUS", "finanzfokus"), ("BWB – Business With Brian", "businesswithbrian"),
        ("Daniel Pronk", "danielpronk"), ("Aktienfinder", "aktienfinder"),
        ("Financial Education", "financialeducation"),
        ("Asymmetric Investing（Travis Hoium）", "asymmetricinvesting"), ("Arte de invertir", "elartedeinvertir"),
        ("Brian Stoffel", "brianstoffelyt"), ("Felix & Friends", "felixfriends"),
        ("Stealth Wealth Investing", "stealthwealthinvesting")]],
    ("A-chinese", "提阿非羅大人TiaBTC", "tiabtc", "channel_id_in_KOL準確度-原始收集.md", "TiaBTC"),
]
KOL_DIR = Path.home() / "MyGithub/PersonalDoc/financial/reports/investing/kol-research-2026-11"

_LOCK = threading.Lock()
log = logging.getLogger("fsnap")


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def iso(t=None):
    return (t or utcnow()).strftime("%Y-%m-%dT%H:%M:%SZ")


def setup_logging(day):
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s")
    log.setLevel(logging.DEBUG)
    for h in (logging.FileHandler(ROOT / "logs" / f"{day}.log"), logging.StreamHandler(sys.stderr)):
        h.setFormatter(fmt); log.addHandler(h)


# ---------------------------------------------------------------- HTTP via curl (same client as the working scripts)
def curl(url, timeout=60, tries=3, data=None, headers=()):
    """Return (http_code:int|None, body:bytes, error:str). Retries 429/5xx/network with 15/45 s backoff."""
    err = ""
    for t in range(1, tries + 1):
        with tempfile.NamedTemporaryFile() as tf:
            cmd = ["curl", "-sS", "-L", "--compressed", "--max-time", str(timeout), "-A", UA, "-o", tf.name,
                   "-w", "%{http_code}"]
            for h in headers: cmd += ["-H", h]
            if data is not None: cmd += ["--data-binary", data]
            t0 = time.time()
            p = subprocess.run(cmd + [url], capture_output=True, text=True)
            body = Path(tf.name).read_bytes()
        code = int(p.stdout) if p.stdout.strip().isdigit() and p.stdout.strip() != "000" else None
        el = time.time() - t0
        if p.returncode == 0 and code and code < 400:
            log.debug("GET %s -> %s %dB %.1fs (try %d)", url, code, len(body), el, t)
            return code, body, ""
        err = f"http={code} curl_rc={p.returncode} {p.stderr.strip()[:300]} body={body[:200]!r}"
        retry = code is None or code == 429 or code >= 500
        log.warning("GET %s failed (try %d/%d, %.1fs): %s%s", url, t, tries, el, err, " -> retry" if retry and t < tries else "")
        if not retry or t == tries:
            return code, body, err
        time.sleep(15 if t == 1 else 45)
    return None, b"", err


# ---------------------------------------------------------------- per-source run context / manifest / ledger
class Ctx:
    def __init__(self, source, day, d):
        self.source, self.day, self.dir, self.files, self.notes = source, day, d, [], {}

    def save(self, name, body, url="", http=None, compress=True):
        """Write raw bytes (gzip by default) and record them in the manifest."""
        path = self.dir / (name + (".gz" if compress else ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(body, mtime=0) if compress else body)
        rec = dict(file=str(path.relative_to(self.dir)), stored_bytes=path.stat().st_size, raw_bytes=len(body),
                   raw_sha256=hashlib.sha256(body).hexdigest(), url=url, http=http, fetched_at=iso())
        self.files.append(rec)
        return rec


def ledger_row(source, status, files=0, nbytes=0, msha="", d="", error=""):
    assert status in ("OK", "FAILED", "EMPTY"), status
    with _LOCK:
        new = not LEDGER.exists()
        with LEDGER.open("a", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            if new: w.writerow(LEDGER_COLS)
            w.writerow([iso(), source, status, files, nbytes, msha, d, re.sub(r"\s+", " ", error)[:2000]])
    log.info("LEDGER %s %s files=%s bytes=%s err=%s", source, status, files, nbytes, error[:300])


def run_source(source, fn, day, force):
    d = ROOT / source / day
    m = d / "MANIFEST.json"
    if m.exists() and not force:
        prev = json.loads(m.read_text())
        if prev.get("status") in ("OK", "EMPTY"):
            log.info("[%s] SKIP: %s already %s for %s (idempotent; use --force to refetch)", source, d, prev["status"], day)
            return prev["status"]
        log.info("[%s] previous attempt today was %s -> retrying", source, prev.get("status"))
    if d.exists():
        keep = d.with_name(f"{day}.attempt-{utcnow():%H%M%S}")
        d.rename(keep)
        log.info("[%s] moved earlier attempt %s -> %s (kept, not deleted)", source, d, keep)
    d.mkdir(parents=True)
    ctx, t0 = Ctx(source, day, d), utcnow()
    log.info("[%s] START -> %s", source, d)
    try:
        status, err = fn(ctx)
    except Exception as e:
        status, err = "FAILED", f"exception: {e!r} | {traceback.format_exc()[-1500:]}"
        log.exception("[%s] crashed", source)
    man = dict(source=source, snapshot_date_utc=day, started=iso(t0), finished=iso(), status=status, error=err,
               notes=ctx.notes, files=ctx.files)
    m.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    nbytes = sum(f["stored_bytes"] for f in ctx.files)
    ledger_row(source, status, len(ctx.files), nbytes, hashlib.sha256(m.read_bytes()).hexdigest(), str(d), err)
    log.info("[%s] END %s in %.0fs, %d files, %d bytes", source, status, (utcnow() - t0).total_seconds(), len(ctx.files), nbytes)
    return status


# ---------------------------------------------------------------- eToro
def src_etoro(ctx):
    users, fails, pages_ok = [], [], 0
    for page in range(1, ETORO_PAGES + 1):
        url = ETORO_RANK.format(page=page, ps=ETORO_PAGESIZE)
        code, body, err = curl(url)
        ctx.save(f"rankings_p{page:02d}.json", body, url, code)
        if err:
            fails.append(f"rankings p{page}: {err}"); log.error("[etoro] rankings page %d failed: %s", page, err)
            if err.startswith("http=429"):
                log.error("[etoro] rate-limited (429) after retries -> stop eToro for this run (politeness)"); break
        else:
            try:
                d = json.loads(body); items = d.get("Items") or []
                log.info("[etoro] rankings page %d: %d items, TotalRows=%s", page, len(items), d.get("TotalRows"))
                ctx.notes["TotalRows"] = d.get("TotalRows")
                users += [(it.get("CustomerId"), it.get("UserName")) for it in items]; pages_ok += 1
                if not items:
                    log.info("[etoro] page %d empty -> stop paging", page); break
            except Exception as e:
                fails.append(f"rankings p{page}: bad json {e!r}"); log.error("[etoro] page %d bad json: %r", page, e)
        time.sleep(2)
    log.info("[etoro] %d users listed on %d pages; fetching gain history at %.1fs spacing", len(users), pages_ok, ETORO_PAUSE)
    ok, c429 = 0, 0
    for i, (cid, uname) in enumerate(users, 1):
        if c429 >= 3:
            fails.append(f"gain {cid}: NOT_ATTEMPTED (3 consecutive 429)"); continue
        url = ETORO_GAIN.format(cid=cid)
        code, body, err = curl(url, timeout=30)
        ctx.save(f"gain/{cid}.json", body, url, code)
        if err or not body.strip().startswith(b"{"):
            fails.append(f"gain {cid} ({uname}): {err or 'non-json body'}")
            log.error("[etoro] gain %s (%s) failed: %s", cid, uname, err or body[:200])
            c429 = c429 + 1 if err.startswith("http=429") else 0
            if c429 == 3: log.error("[etoro] 3 consecutive 429 on gain history -> stop gain requests this run")
        else:
            ok += 1; c429 = 0
        if i % 50 == 0: log.info("[etoro] gain progress %d/%d ok=%d", i, len(users), ok)
        time.sleep(ETORO_PAUSE)
    ctx.notes.update(users_listed=len(users), gain_ok=ok, pages_ok=pages_ok,
                     query=ETORO_RANK.format(page="N", ps=ETORO_PAGESIZE))
    if fails:
        return "FAILED", f"{len(fails)} failures (pages_ok={pages_ok}/{ETORO_PAGES}, gain_ok={ok}/{len(users)}): " + " | ".join(fails[:10])
    return ("EMPTY", "rankings returned 0 users") if not users else ("OK", "")


# ---------------------------------------------------------------- Polymarket
def src_polymarket(ctx):
    fails, rows = [], {}
    for tp in PM_PERIODS:
        url, n = f"{PM_BASE}?time_period={tp}&sort_by=PNL&category=overall&limit={PM_LIMIT}", 0
        for page in range(1, PM_PAGES + 1):
            code, body, err = curl(url)
            ctx.save(f"leaderboard_pnl_{tp}_p{page}.json", body, url, code)
            if err:
                fails.append(f"{tp} p{page}: {err}"); log.error("[polymarket] %s p%d failed: %s", tp, page, err); break
            try:
                d = json.loads(body)
            except Exception as e:
                fails.append(f"{tp} p{page}: bad json {e!r}"); break
            n += len(d.get("data") or []); pg = d.get("pagination") or {}
            log.info("[polymarket] %s p%d: %d rows (cum %d) has_more=%s", tp, page, len(d.get("data") or []), n, pg.get("has_more"))
            if not pg.get("has_more") or not pg.get("next_cursor"):
                log.info("[polymarket] %s: no more pages after p%d", tp, page); break
            url = f"{PM_BASE}?cursor={pg['next_cursor']}"
            time.sleep(PM_PAUSE)
        rows[tp] = n
        time.sleep(PM_PAUSE)
    ctx.notes["rows_per_period"] = rows
    if fails:
        return "FAILED", f"rows={rows} | " + " | ".join(fails)
    return ("EMPTY", f"rows={rows}") if sum(rows.values()) == 0 else ("OK", "")


# ---------------------------------------------------------------- CryptoKrios
def chrome_render(url):
    """Fallback only: render in the agent Chrome via CDP. Raises if Chrome isn't running (never starts one)."""
    pf = Path.home() / ".config/agent-chrome/DevToolsActivePort"
    port = pf.read_text().split()[0] if pf.exists() else None
    if not port:
        raise RuntimeError(f"agent Chrome port file missing ({pf}); not starting a browser")
    urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5).read()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        pg = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}").contexts[0].new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=60000); time.sleep(6)
            return pg.content().encode()
        finally:
            pg.close()


def src_cryptokrios(ctx):
    fails = []
    code, body, err = curl(f"{CK_BASE}/creators")
    ctx.save("creators.html", body, f"{CK_BASE}/creators", code)
    if err:
        return "FAILED", f"/creators list page: {err}"
    slugs = sorted(set(re.findall(r'href="/creators/([A-Za-z0-9._-]+)"', body.decode("utf-8", "replace"))))
    log.info("[cryptokrios] /creators lists %d slugs", len(slugs))
    missing = [s for s in CK_PREREG if s not in slugs]
    if missing:
        log.warning("[cryptokrios] pre-registered slugs not on list page, fetching directly anyway: %s", missing)
        fails.append(f"pre-registered not on list page: {missing}")
    ctx.notes.update(n_slugs_on_list=len(slugs), prereg_missing_from_list=missing)
    no_preds = []
    for i, s in enumerate(slugs + missing, 1):
        url = f"{CK_BASE}/creators/{s}"
        code, body, err = curl(url)
        how = "curl"
        if not err and b"recentPredictions" not in body:
            log.warning("[cryptokrios] %s: curl page has no recentPredictions (%dB) -> trying agent Chrome", s, len(body))
            ctx.save(f"creator_{s}.curl.html", body, url, code)
            try:
                body, how = chrome_render(url), "agent-chrome"
            except Exception as e:
                err = f"no recentPredictions in curl page; chrome fallback FAILED: {e!r}"
        ctx.save(f"creator_{s}.html", body, url, code)
        if err:
            fails.append(f"{s}: {err}"); log.error("[cryptokrios] %s failed: %s", s, err)
        elif b"recentPredictions" not in body:
            no_preds.append(s); log.warning("[cryptokrios] %s: no recentPredictions object even via %s", s, how)
        else:
            log.debug("[cryptokrios] %s ok via %s (%dB)", s, how, len(body))
        if i % 50 == 0: log.info("[cryptokrios] progress %d/%d", i, len(slugs) + len(missing))
        time.sleep(CK_PAUSE)
    ctx.notes["no_recentPredictions"] = no_preds
    if no_preds: fails.append(f"{len(no_preds)} pages without recentPredictions: {no_preds[:20]}")
    if fails:
        return "FAILED", " | ".join(fails[:15])
    return ("EMPTY", "list page had 0 creators") if not slugs else ("OK", "")


# ---------------------------------------------------------------- YouTube
MAP = ROOT / "youtube" / "channel_map.tsv"
MAP_COLS = ["list", "name_in_prereg", "key", "status", "channel_url", "channel_id", "channel_title_seen",
            "resolved_how", "evidence", "resolved_at_utc"]


def ytdlp(args, timeout=180):
    p = subprocess.run([YTDLP, *args], capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, "\n".join(l for l in p.stderr.splitlines() if "Deprecated Feature" not in l)


def check_channel(r, name):
    """Confirm a channel URL exists via yt-dlp (1 entry); fills channel_id/title. Returns True if confirmed."""
    rc, out, err = ytdlp(["--flat-playlist", "--playlist-end", "1", "-J", r["channel_url"] + "/videos"])
    time.sleep(YT_PAUSE)
    try:
        j = json.loads(out)
        r.update(status="RESOLVED", channel_id=j.get("channel_id") or "", channel_title_seen=j.get("channel") or "")
        log.info("resolve %s -> %s (%s, %s)", name, r["channel_url"], r["channel_id"], r["channel_title_seen"])
        return True
    except Exception:
        last = [l for l in err.splitlines() if l.startswith("ERROR")][-1:] or [err[-200:]]
        r.update(status="UNVERIFIED", evidence=r["evidence"] + f" | yt-dlp check of {r['channel_url']} failed rc={rc}: {last[0]}")
        log.error("resolve %s: yt-dlp check of %s failed rc=%s %s", name, r["channel_url"], rc, err[-300:])
        return False


def cmd_resolve(force=False):
    """Build channel_map.tsv once. Every row records where the URL came from; anything not resolvable from
    those sources is UNRESOLVED and skipped by the weekly run (no guessing)."""
    if MAP.exists() and not force:
        log.info("channel map exists (%s); use --force to rebuild", MAP); return
    MAP.parent.mkdir(parents=True, exist_ok=True)
    par = KOL_DIR / "逐個預測數據/data/parsed"
    raw = KOL_DIR / "逐個預測數據/data/raw"
    ck = {r["slug"]: r for r in csv.DictReader(open(par / "cryptokrios_creators.csv"))}
    art = (raw / "bullvox_20261111_blog_best-finance-youtubers-2026.html").read_text(errors="ignore")
    art_links = {m.group(1): html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()
                 for m in re.finditer(r'<a[^>]+href="/youtuber/([^/"]+)/?"[^>]*>(.*?)</a>', art, re.S)}
    prof = {r["slug"]: r for r in csv.DictReader(open(par / "bullvox_creator_profiles.csv"))}
    kol_doc = (KOL_DIR / "KOL準確度-原始收集.md").read_text()
    rows = []
    for lst, name, key, how, ref in LIST_A:
        r = dict(list=lst, name_in_prereg=name, key=key, status="UNRESOLVED", channel_url="", channel_id="",
                 channel_title_seen="", resolved_how=how, evidence="", resolved_at_utc=iso())
        if how == "cryptokrios_youtubeUrl":
            c = ck.get(ref)
            if c and c.get("youtubeUrl"):
                r.update(channel_url=c["youtubeUrl"], evidence=f"cryptokrios_creators.csv slug={ref} title={c['title']!r} youtubeUrl from /creators/{ref} page")
            else:
                r["evidence"] = f"slug {ref} not in cryptokrios_creators.csv or no youtubeUrl"
        elif how.startswith("bullvox"):
            link = art_links.get(ref)
            p = prof.get(ref)
            mh = re.search(r"youtube\.com/(@[A-Za-z0-9._-]+)", p["header_verbatim"]) if p else None
            if link and mh:
                r.update(channel_url=f"https://www.youtube.com/{mh.group(1)}",
                         evidence=f"BullVox article 'best-finance-youtubers-2026' links {link!r} -> /youtuber/{ref}/; that profile page shows youtube.com/{mh.group(1)}")
            else:
                r["evidence"] = (f"BullVox article links {link!r} -> /youtuber/{ref}/ but no saved profile page with a "
                                 f"YouTube handle (profile in parsed csv: {bool(p)}; live page HTTP 404 on 2026-11-11). Not guessed.")
        else:
            m = re.search(r"TiaBTC \((UC[A-Za-z0-9_-]{22})\)", kol_doc)
            if m:
                r.update(channel_url=f"https://www.youtube.com/channel/{m.group(1)}",
                         evidence=f"KOL準確度-原始收集.md: '提阿非羅大人 TiaBTC ({m.group(1)})'")
        if r["channel_url"]:
            ok = check_channel(r, name)
            if not ok and how.startswith("bullvox"):
                # 2026-11-11: BullVox's displayed handle 404s for some channels (@elartedeinvertir, @FelixFriends).
                # Fallback: the video IDs BullVox itself lists on that profile -> YouTube public oEmbed author_url.
                # Accept only if every listed video has the same uploader.
                pf = raw / f"bullvox_20261111_youtuber_{ref}.html"
                vids = list(dict.fromkeys(re.findall(r"watch\?v=([A-Za-z0-9_-]{11})", pf.read_text(errors="ignore"))))[:3] if pf.exists() else []
                authors = []
                for v in vids:
                    code, body, err = curl(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={v}&format=json", timeout=20)
                    try:
                        j = json.loads(body); authors.append((v, j.get("author_name"), j.get("author_url")))
                    except Exception:
                        authors.append((v, None, f"oembed http={code} {err[:100]}"))
                    time.sleep(2)
                urls = {a[2] for a in authors}
                log.info("resolve %s: oEmbed of BullVox-listed videos %s -> %s", name, vids, authors)
                if len(vids) >= 2 and len(urls) == 1 and all(a[1] for a in authors):
                    r.update(channel_url=urls.pop(), resolved_how="bullvox_profile_video_ids_then_youtube_oembed",
                             evidence=r["evidence"] + f" | that handle 404s on YouTube; BullVox profile lists videos {vids}, "
                                      f"YouTube oEmbed uploader for all of them: {authors[0][1]!r} {authors[0][2]}")
                    check_channel(r, name)
                else:
                    r["evidence"] += f" | oEmbed fallback inconclusive: {authors}"
        else:
            log.warning("resolve %s: UNRESOLVED (%s)", name, r["evidence"])
        r = {k: re.sub(r"\s+", " ", str(v)) for k, v in r.items()}  # TSV safety
        rows.append(r)
    with MAP.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MAP_COLS, delimiter="\t", lineterminator="\n"); w.writeheader(); w.writerows(rows)
    log.info("wrote %s: %d rows, %d RESOLVED", MAP, len(rows), sum(r["status"] == "RESOLVED" for r in rows))


def channels():
    if not MAP.exists():
        raise RuntimeError(f"{MAP} missing; run `forward_snapshot.py resolve` once first")
    return list(csv.DictReader(MAP.open(), delimiter="\t"))


def src_youtube_lists(ctx):
    fails, skipped, counts = [], [], {}
    for ch in channels():
        if ch["status"] != "RESOLVED":
            skipped.append(f"{ch['name_in_prereg']}={ch['status']}")
            log.info("[youtube_lists] skip %s: status %s in channel_map", ch["name_in_prereg"], ch["status"]); continue
        base = f"https://www.youtube.com/channel/{ch['channel_id']}" if ch["channel_id"] else ch["channel_url"]
        for tab in YT_TABS:
            url = f"{base}/{tab}"
            rc, out, err = ytdlp(["--flat-playlist", "--playlist-end", str(YT_N), "-J",
                                  "--extractor-args", "youtubetab:approximate_date", url])
            if rc == 0 and out.strip().startswith("{"):
                n = len(json.loads(out).get("entries") or [])
                ctx.save(f"{ch['key']}.{tab}.flat.json", out.encode(), url, "yt-dlp rc=0")
                counts[f"{ch['key']}/{tab}"] = n
                log.info("[youtube_lists] %s %s: %d entries", ch["key"], tab, n)
            elif "does not have a" in err and "tab" in err:
                counts[f"{ch['key']}/{tab}"] = 0
                ctx.save(f"{ch['key']}.{tab}.no-tab.txt", err.encode(), url, f"yt-dlp rc={rc}", compress=False)
                log.info("[youtube_lists] %s has no %s tab (real absence, not a failure): %s", ch["key"], tab, err[-200:])
            else:
                fails.append(f"{ch['key']}/{tab}: rc={rc} {err[-300:]}")
                ctx.save(f"{ch['key']}.{tab}.error.txt", (out[:2000] + "\n" + err).encode(), url, f"yt-dlp rc={rc}", compress=False)
                log.error("[youtube_lists] %s %s FAILED rc=%s: %s", ch["key"], tab, rc, err[-500:])
            time.sleep(YT_PAUSE)
    ctx.notes.update(entries=counts, skipped_channels=skipped)
    if fails:
        return "FAILED", f"{len(fails)} tab fetches failed: " + " | ".join(fails[:10]) + (f" | skipped: {skipped}" if skipped else "")
    note = f"skipped (not resolved): {skipped}" if skipped else ""
    return ("EMPTY", note) if sum(counts.values()) == 0 else ("OK", note)


DATES = ROOT / "youtube_upload_dates" / "upload_dates.tsv"
DATE_COLS = ["video_id", "upload_date", "timestamp", "release_timestamp", "live_status", "fetched_at_utc"]
CSV_COLS = ["snapshot_date_utc", "fetched_at_utc", "channel_key", "channel_id", "tab", "playlist_index", "video_id",
            "title", "duration_s", "view_count", "approx_timestamp_utc", "upload_date", "upload_date_source"]


def src_youtube_upload_dates(ctx):
    lists_dir = ROOT / "youtube_lists" / ctx.day
    man = lists_dir / "MANIFEST.json"
    if not man.exists():
        return "FAILED", f"no youtube_lists snapshot for {ctx.day} ({man} missing)"
    known = {r["video_id"]: r for r in csv.DictReader(DATES.open(), delimiter="\t")} if DATES.exists() else {}
    vids = []  # (channel row, tab, index, entry, fetched_at)
    chmap = {c["key"]: c for c in channels()}
    for f in json.loads(man.read_text())["files"]:
        m = re.match(r"(.+)\.(videos|streams)\.flat\.json\.gz$", f["file"])
        if not m: continue
        j = json.loads(gzip.decompress((lists_dir / f["file"]).read_bytes()))
        for i, e in enumerate(j.get("entries") or [], 1):
            vids.append((chmap[m.group(1)], m.group(2), i, e, f["fetched_at"]))
    todo = [v for v in dict.fromkeys(e["id"] for _, _, _, e, _ in vids) if v not in known]
    log.info("[youtube_upload_dates] %d listed videos, %d already dated, %d to fetch", len(vids), len(vids) - len(todo), len(todo))
    res_lines, fails, consec_bot, tripped = [], {}, 0, False
    new = []
    for vid in todo:
        if tripped:
            fails[vid] = "NOT_ATTEMPTED: bot-check circuit open this run"; continue
        url = f"https://www.youtube.com/watch?v={vid}"
        try:
            rc, out, err = ytdlp(["--skip-download", "--no-playlist", "--print",
                                  "%(id)s\t%(upload_date)s\t%(timestamp)s\t%(release_timestamp)s\t%(live_status)s", url], timeout=120)
        except subprocess.TimeoutExpired:
            rc, out, err = -1, "", "timeout 120s"
        res_lines.append(f"{iso()}\t{vid}\trc={rc}\t{out.strip()}\t{err.strip()[-400:]}".replace("\n", " "))
        parts = out.strip().split("\t")
        if rc == 0 and len(parts) == 5 and re.fullmatch(r"\d{8}", parts[1]):
            new.append(dict(zip(DATE_COLS, parts + [iso()]))); consec_bot = 0
            log.debug("[youtube_upload_dates] %s upload_date=%s", vid, parts[1])
        else:
            fails[vid] = f"rc={rc} {err.strip()[-200:]}"
            log.error("[youtube_upload_dates] %s failed rc=%s: %s", vid, rc, err.strip()[-300:])
            consec_bot = consec_bot + 1 if "confirm you" in err and "not a bot" in err else 0
            if consec_bot >= YT_BOTCHECK_TRIP:
                tripped = True
                log.error("[youtube_upload_dates] %d consecutive bot-check refusals -> stop per-video requests this run (politeness)", consec_bot)
        time.sleep(YT_VIDEO_PAUSE)
    ctx.save("per_video_results.tsv", ("\n".join(res_lines) + "\n").encode(), "yt-dlp per video", None, compress=False)
    if new:
        hdr = not DATES.exists()
        DATES.parent.mkdir(parents=True, exist_ok=True)
        with DATES.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=DATE_COLS, delimiter="\t", lineterminator="\n")
            if hdr: w.writeheader()
            w.writerows(new)
        for r in new: known[r["video_id"]] = r
    # append-only per-channel CSV; (snapshot_date, tab, video_id) never written twice
    vdir = ROOT / "youtube" / "videos"; vdir.mkdir(parents=True, exist_ok=True)
    appended = {}
    for key in dict.fromkeys(c["key"] for c, *_ in vids):
        p = vdir / f"{key}.csv"
        have = {(r["snapshot_date_utc"], r["tab"], r["video_id"]) for r in csv.DictReader(p.open())} if p.exists() else set()
        out_rows = []
        for c, tab, i, e, fat in (v for v in vids if v[0]["key"] == key):
            if (ctx.day, tab, e["id"]) in have: continue
            k = known.get(e["id"])
            ts = e.get("timestamp")
            out_rows.append(dict(snapshot_date_utc=ctx.day, fetched_at_utc=fat, channel_key=key, channel_id=c["channel_id"],
                                 tab=tab, playlist_index=i, video_id=e["id"], title=e.get("title"), duration_s=e.get("duration"),
                                 view_count=e.get("view_count"),
                                 approx_timestamp_utc=iso(dt.datetime.fromtimestamp(ts, dt.timezone.utc)) if ts else "",
                                 upload_date=k["upload_date"] if k else "",
                                 upload_date_source=("yt-dlp per-video " + k["fetched_at_utc"]) if k else ("FAILED: " + fails.get(e["id"], "unknown"))[:250]))
        if out_rows:
            hdr = not p.exists()
            with p.open("a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=CSV_COLS); hdr and w.writeheader(); w.writerows(out_rows)
        appended[key] = len(out_rows)
        log.info("[youtube_upload_dates] %s.csv: +%d rows (%d already present for today)", key, len(out_rows), len(have and [h for h in have if h[0] == ctx.day]))
    ctx.notes.update(listed=len(vids), fetched_new=len(new), failed=len(fails), circuit_tripped=tripped, csv_rows_appended=appended)
    if fails:
        sample = list(fails.items())[:5]
        return "FAILED", (f"upload_date missing for {len(fails)}/{len(todo)} new videos (rows still appended with blank date)"
                          f"{'; bot-check circuit tripped' if tripped else ''}: {sample}")
    return ("EMPTY", "no listed videos") if not vids else ("OK", "")


SOURCES = {"etoro": src_etoro, "polymarket": src_polymarket, "cryptokrios": src_cryptokrios,
           "youtube_lists": src_youtube_lists, "youtube_upload_dates": src_youtube_upload_dates}
# youtube_upload_dates needs today's youtube_lists, so the two run in one sequential group
GROUPS = [["etoro"], ["polymarket"], ["cryptokrios"], ["youtube_lists", "youtube_upload_dates"]]


def cmd_run(only, force):
    day = utcnow().strftime("%Y-%m-%d")
    sel = [s for s in SOURCES if not only or s in only]
    lockf = (ROOT / ".lock").open("w")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error("another forward_snapshot run holds %s; exiting", ROOT / ".lock"); return 1
    free = shutil.disk_usage(Path.home()).free / 1e9
    log.info("RUN day=%s sources=%s force=%s disk_free=%.1f GB (min %d)", day, sel, force, free, MIN_FREE_GB)
    if free < MIN_FREE_GB:
        for s in sel: ledger_row(s, "FAILED", error=f"skipped: disk free {free:.1f} GB < {MIN_FREE_GB} GB")
        return 1
    results = {}

    def group(g):
        for s in g:
            if s in sel:
                threading.current_thread().name = s
                results[s] = run_source(s, SOURCES[s], day, force)
    with ThreadPoolExecutor(len(GROUPS)) as ex:
        list(ex.map(group, GROUPS))
    log.info("RUN done: %s", results)
    return 0 if all(v != "FAILED" for v in results.values()) else 2


def cmd_status():
    if not LEDGER.exists(): print("no ledger yet"); return
    rows = list(csv.DictReader(LEDGER.open(), delimiter="\t"))
    last = {}
    for r in rows: last[r["source"]] = r
    for s, r in last.items():
        print(f"{s:22} {r['timestamp_utc']} {r['status']:7} files={r['files']:>5} bytes={int(r['bytes'] or 0):>11,} {r['error'][:150]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run"); r.add_argument("--only", default=""); r.add_argument("--force", action="store_true")
    rs = sp.add_parser("resolve"); rs.add_argument("--force", action="store_true")
    sp.add_parser("status")
    a = ap.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    setup_logging(utcnow().strftime("%Y-%m-%d"))
    if a.cmd == "run":
        only = [x for x in a.only.split(",") if x]
        bad = [x for x in only if x not in SOURCES]
        if bad: ap.error(f"unknown sources {bad}; choose from {list(SOURCES)}")
        sys.exit(cmd_run(only, a.force))
    if a.cmd == "resolve":
        cmd_resolve(a.force)
    if a.cmd == "status":
        cmd_status()


if __name__ == "__main__":
    main()
