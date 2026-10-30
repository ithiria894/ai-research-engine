#!/usr/bin/env bash
# MediaCrawler (xhs | dy | ks | bili | wb | tieba | zhihu) through the AGENT Chrome on :9223.
# Never resident: one crawl per call. Output goes to the given directory as JSONL.
# Usage: tools/mediacrawler.sh PLATFORM search "kw1,kw2" OUT_DIR [extra main.py args]
set -uo pipefail
M=${MEDIACRAWLER_HOME:-$HOME/.local/share/research-engine/tools/MediaCrawler}
CFG=$M/config/base_config.py
log() { echo "mediacrawler: $*" >&2; }
[[ -x "$M/.venv/bin/python" ]] || { log "[unconfigured] not installed at $M"; exit 2; }
# Upstream defaults to CDP port 9222 = Nicole's personal Chrome. Force the agent Chrome every run,
# so an upstream update cannot silently point it back.
sed -i -E 's/^CDP_DEBUG_PORT = [0-9]+/CDP_DEBUG_PORT = 9223/; s/^CDP_CONNECT_EXISTING = .*/CDP_CONNECT_EXISTING = True/; s/^ENABLE_CDP_MODE = .*/ENABLE_CDP_MODE = True/' "$CFG"
grep -q '^CDP_DEBUG_PORT = 9223' "$CFG" || { log "[error] could not pin CDP_DEBUG_PORT=9223; refusing to run"; exit 1; }
curl -fsS --max-time 2 http://127.0.0.1:9223/json/version >/dev/null || { log "[unconfigured] agent Chrome :9223 not running (agent-chrome.py start)"; exit 2; }
platform=${1:?platform}; type=${2:?type}; kw=${3:?keywords}; out=${4:?output dir}; shift 4
mkdir -p "$out"
log "crawl platform=$platform type=$type keywords=$kw out=$out"
cd "$M" && .venv/bin/python main.py --platform "$platform" --type "$type" --keywords "$kw" --lt qrcode \
  --save_data_option jsonl --save_data_path "$out" "$@"
