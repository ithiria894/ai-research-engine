#!/usr/bin/env python3
"""Check a magnet's swarm health WITHOUT downloading content: fetch metadata, then count peers/seeds
for a short window with every file set to priority 0 (nothing is written). 2026-11-06."""
import sys, time, tempfile, libtorrent as lt
magnet, secs = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 180
ses = lt.session({"listen_interfaces": "0.0.0.0:6891", "enable_dht": True})
p = lt.parse_magnet_uri(magnet); p.save_path = tempfile.mkdtemp(prefix="th-")
p.flags |= lt.torrent_flags.upload_mode  # never download payload
h = ses.add_torrent(p); t0 = time.time(); best = (0, 0)
while time.time() - t0 < secs:
    s = h.status()
    best = (max(best[0], s.num_seeds), max(best[1], s.num_peers))
    meta = s.has_metadata
    print(f"{int(time.time()-t0):4d}s metadata={meta} seeds={s.num_seeds} peers={s.num_peers} "
          f"list_seeds={s.list_seeds} list_peers={s.list_peers} trackers_ok={sum(1 for a in h.trackers() if a.get('verified'))}", flush=True)
    time.sleep(15)
s = h.status()
if s.has_metadata:
    ti = h.torrent_file(); print("name", ti.name(), "files", ti.num_files(), "size_TB", round(ti.total_size()/1e12, 3))
print("MAX seeds", best[0], "MAX peers", best[1], "| tracker-reported seeds", s.list_seeds, "peers", s.list_peers)
