#!/usr/bin/env python3
"""Download Reddit dumps from Academic Torrents (Arctic Shift / Watchful1) — 2026-11-13.

Why: our API pipeline (reddit_archive.py) asks Arctic Shift page by page; fine for ~100 subs, wrong for
thousands of subs or all of Reddit (years of requests, ban risk). The same data is published as torrents
(list: https://github.com/ArthurHeitmann/arctic_shift/blob/master/download_links.md). Torrents put no load on
the Arctic Shift API. Runs on Waifu WSL (needs libtorrent: ~/venvs/research/bin/python).

Layout : ~/data/reddit-torrents/<infohash>.torrent          metadata
         ~/data/reddit-torrents/<infohash>.files.tsv        index, bytes, path
         ~/data/reddit-torrents/<torrent name>/...           downloaded files
         ~/data/reddit-torrents/torrent.log                  log
Usage  : reddit_torrent.py meta <infohash>                   fetch metadata + write file list
         reddit_torrent.py get <infohash> --subs-file F [--subs-file G ...] [--all]
               select only <sub>_comments.zst / <sub>_submissions.zst for subs listed (case-insensitive);
               --all = every file. Keeps seeding after completion until stopped.
"""
import argparse, re, sys, time
from pathlib import Path
import libtorrent as lt

ROOT = Path(__import__("os").environ.get("REDDIT_TORRENT_ROOT") or Path.home() / "data" / "reddit-torrents")
TRACKERS = ["https://academictorrents.com/announce.php", "udp://tracker.opentrackr.org:1337/announce",
            "udp://tracker.openbittorrent.com:6969/announce", "udp://exodus.desync.com:6969/announce"]
MIN_FREE_GB = 20

def log(*a):
    msg = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(msg, file=sys.stderr, flush=True)
    with (ROOT / "torrent.log").open("a") as f:
        f.write(msg + "\n")

def session():
    s = lt.session({"listen_interfaces": "0.0.0.0:6881,[::]:6881", "enable_dht": True,
                    "alert_mask": lt.alert.category_t.error_notification | lt.alert.category_t.status_notification})
    return s

def magnet(ih):
    return f"magnet:?xt=urn:btih:{ih}&" + "&".join("tr=" + t for t in TRACKERS)

def meta(ih, s=None):
    tf = ROOT / f"{ih}.torrent"
    if tf.exists():
        log(f"META {ih}: cached {tf}")
        return lt.torrent_info(str(tf))
    s = s or session()
    p = lt.parse_magnet_uri(magnet(ih)); p.save_path = str(ROOT); p.flags |= lt.torrent_flags.upload_mode
    h = s.add_torrent(p)
    log(f"META {ih}: waiting for metadata via DHT/trackers")
    t0 = time.time()
    while not h.status().has_metadata:
        if time.time() - t0 > 1800:
            log(f"META {ih}: FAILED no metadata after 30 min (peers={h.status().num_peers})"); sys.exit(2)
        time.sleep(5)
    ti = h.torrent_file()
    tf.write_bytes(lt.bencode(lt.create_torrent(ti).generate()))
    s.remove_torrent(h)
    fs = ti.files()
    with (ROOT / f"{ih}.files.tsv").open("w") as f:
        f.write("index\tbytes\tpath\n")
        for i in range(fs.num_files()):
            f.write(f"{i}\t{fs.file_size(i)}\t{fs.file_path(i)}\n")
    log(f"META {ih}: name={ti.name()} files={fs.num_files()} total={ti.total_size()/1e12:.3f} TB -> {tf.name}")
    return ti

def subs_from(files):
    subs = []
    for fp in files:
        subs += [l.split("#")[0].strip() for l in Path(fp).read_text().splitlines() if l.split("#")[0].strip()]
    return sorted({x.lower() for x in subs})

def get(ih, subs_files, everything):
    s = session()
    ti = meta(ih, s)
    fs = ti.files()
    want = set(subs_from(subs_files)) if subs_files else set()
    pat = re.compile(r"(?:^|/)([^/]+)_(?:comments|submissions)\.zst$", re.I)
    prio, chosen, missing = [], 0, set(want)
    for i in range(fs.num_files()):
        m = pat.search(fs.file_path(i))
        take = everything or (m is not None and m.group(1).lower() in want)
        if take and m:
            missing.discard(m.group(1).lower())
        prio.append(4 if take else 0)
        chosen += fs.file_size(i) if take else 0
    log(f"GET {ih}: selected {sum(1 for p in prio if p)} files, {chosen/1e9:.1f} GB; subs requested={len(want)}"
        f"; not in torrent={len(missing)}: {' '.join(sorted(missing))[:2000]}")
    free = __import__("shutil").disk_usage(ROOT).free
    if chosen > free - MIN_FREE_GB * 1e9:
        log(f"GET {ih}: STOP need {chosen/1e9:.1f} GB but only {free/1e9:.1f} GB free (guard {MIN_FREE_GB} GB)"); sys.exit(3)
    p = lt.add_torrent_params(); p.ti = ti; p.save_path = str(ROOT); p.file_priorities = prio
    h = s.add_torrent(p)
    last, last_fp = 0, 0
    sel = [i for i, pr in enumerate(prio) if pr]
    cfile = ROOT / f"{ih}.completed.tsv"   # index<TAB>path of every selected file fully downloaded (read by reddit_torrent_import.py)
    done = {int(l.split("\t")[0]) for l in cfile.read_text().splitlines() if "\t" in l} if cfile.exists() else set()
    while True:
        st = h.status()
        if time.time() - last_fp > 60 and st.state in (st.downloading, st.finished, st.seeding):
            fp = h.file_progress(flags=lt.torrent_handle.piece_granularity)
            new = [i for i in sel if i not in done and fp[i] == fs.file_size(i)]
            if new:
                with cfile.open("a") as f:
                    for i in new:
                        f.write(f"{i}\t{fs.file_path(i)}\n")
                done |= set(new)
                log(f"  completed {len(new)} files (total {len(done)}/{len(sel)}): " + " ".join(fs.file_path(i).rsplit('/', 1)[-1] for i in new)[:1500])
            last_fp = time.time()
        for a in s.pop_alerts():
            if a.category() & lt.alert.category_t.error_notification:
                log(f"  ALERT {a.what()}: {a.message()}")
        if time.time() - last > 300:
            log(f"  {st.state} {st.progress*100:.2f}% done={st.total_wanted_done/1e9:.1f}/{st.total_wanted/1e9:.1f} GB"
                f" down={st.download_rate/1e6:.2f} MB/s up={st.upload_rate/1e6:.2f} MB/s peers={st.num_peers} seeds={st.num_seeds}")
            last = time.time()
        time.sleep(10)

def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("meta"); a.add_argument("infohash")
    b = sp.add_parser("get"); b.add_argument("infohash"); b.add_argument("--subs-file", action="append", default=[])
    b.add_argument("--all", action="store_true")
    x = ap.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    log(f"RUN {' '.join(sys.argv[1:])}")
    if x.cmd == "meta":
        meta(x.infohash)
    else:
        if not x.subs_file and not x.all:
            ap.error("get needs --subs-file or --all")
        get(x.infohash, x.subs_file, x.all)

if __name__ == "__main__":
    main()
