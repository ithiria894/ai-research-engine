#!/usr/bin/env bash
# On-demand local SearXNG (252 engines) for the research engine. Never resident:
# `search` starts the server if needed, queries it, and stops it again if it started it.
# Usage: tools/searxng.sh start|stop|status|search "QUERY" [ENGINES]
set -uo pipefail
HOME_DIR=${SEARXNG_HOME:-$HOME/.local/share/research-engine/tools/searxng}
export SEARXNG_SETTINGS_PATH=${SEARXNG_SETTINGS_PATH:-$HOME/.config/research-engine/searxng/settings.yml}
URL=http://127.0.0.1:8888
RUN=$HOME/.local/state/research-engine; mkdir -p "$RUN"
PID=$RUN/searxng.pid; LOG=$RUN/searxng.log
log() { echo "searxng: $*" >&2; }
up() { curl -fsS --max-time 2 "$URL/healthz" >/dev/null 2>&1; }

start() {
  if up; then log "already running"; return 0; fi
  [[ -x "$HOME_DIR/.venv/bin/python" ]] || { log "[unconfigured] not installed at $HOME_DIR"; return 2; }
  log "starting (settings $SEARXNG_SETTINGS_PATH)"
  # No subshell: $! must be the python pid itself, or stop kills a wrapper and leaves the server up.
  pushd "$HOME_DIR" >/dev/null || return 2
  nohup .venv/bin/python -m searx.webapp >"$LOG" 2>&1 &
  echo $! >"$PID"
  popd >/dev/null
  for _ in $(seq 1 60); do up && { log "ready after start"; return 0; }; sleep 0.5; done
  log "[timeout] did not become healthy; see $LOG"; tail -5 "$LOG" >&2; return 1
}
stop() {
  [[ -f "$PID" ]] || { log "no pid file; nothing started by this script"; return 0; }
  local pid; pid=$(cat "$PID")
  kill "$pid" 2>/dev/null
  for _ in $(seq 1 20); do up || { log "stopped pid $pid"; rm -f "$PID"; return 0; }; sleep 0.25; done
  kill -9 "$pid" 2>/dev/null; rm -f "$PID"
  up && { log "[error] still answering after kill -9 of $pid"; return 1; } || log "stopped pid $pid (forced)"
}
case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) up && echo running || echo stopped ;;
  search)
    q=${2:?query required}; engines=${3:-}
    started=0; up || { start || exit $?; started=1; }
    args=(--data-urlencode "q=$q" -d format=json); [[ -n "$engines" ]] && args+=(-d "engines=$engines")
    curl -sS -G --max-time 60 "$URL/search" "${args[@]}"; rc=$?
    [[ $started == 1 ]] && stop
    exit $rc ;;
  *) echo "usage: $0 start|stop|status|search QUERY [ENGINES]" >&2; exit 64 ;;
esac
