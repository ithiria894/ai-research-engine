#!/usr/bin/env bash
# On-demand local RSSHub (1,995 site namespaces). Never resident: `get` starts the server if
# needed, fetches one route as JSON Feed, and stops it again if it started it.
# Usage: tools/rsshub.sh start|stop|status|get /namespace/route
set -uo pipefail
HOME_DIR=${RSSHUB_HOME:-$HOME/.local/share/research-engine/tools/RSSHub}
PORT=${RSSHUB_PORT:-1200}; URL=http://127.0.0.1:$PORT
RUN=$HOME/.local/state/research-engine; mkdir -p "$RUN"; PID=$RUN/rsshub.pid; LOG=$RUN/rsshub.log
log() { echo "rsshub: $*" >&2; }
up() { curl -fsS --max-time 2 "$URL/healthz" >/dev/null 2>&1; }
node24() { source "$HOME/.nvm/nvm.sh" >/dev/null 2>&1 && nvm which 24 2>/dev/null; }

start() {
  if up; then log "already running"; return 0; fi
  local node; node=$(node24); [[ -x "$node" && -f "$HOME_DIR/dist/index.mjs" ]] || { log "[unconfigured] needs Node 24 (nvm) and a built $HOME_DIR"; return 2; }
  log "starting on 127.0.0.1:$PORT"
  pushd "$HOME_DIR" >/dev/null || return 2
  # Cookies for login-gated routes (e.g. ZHIHU_COOKIES, XIAOHONGSHU_COOKIE) can be exported by the caller.
  NODE_ENV=production PORT=$PORT LISTEN_INADDR_ANY=0 NODE_OPTIONS=--max-http-header-size=32768 \
    nohup "$node" dist/index.mjs >"$LOG" 2>&1 &
  echo $! >"$PID"; popd >/dev/null
  for _ in $(seq 1 80); do up && { log "ready"; return 0; }; sleep 0.5; done
  log "[timeout] not healthy; see $LOG"; tail -5 "$LOG" >&2; return 1
}
stop() {
  [[ -f "$PID" ]] || { log "no pid file; nothing started by this script"; return 0; }
  local pid; pid=$(cat "$PID"); kill "$pid" 2>/dev/null
  for _ in $(seq 1 20); do up || { log "stopped pid $pid"; rm -f "$PID"; return 0; }; sleep 0.25; done
  kill -9 "$pid" 2>/dev/null; rm -f "$PID"; up && { log "[error] still answering"; return 1; } || log "stopped pid $pid (forced)"
}
case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) up && echo running || echo stopped ;;
  get)
    route=${2:?route required, e.g. /v2ex/topics/hot}
    started=0; up || { start || exit $?; started=1; }
    sep='?'; [[ "$route" == *\?* ]] && sep='&'
    code=$(curl -sS --max-time 90 -o /dev/stdout -w '\n%{http_code}' "$URL$route${sep}format=json")
    rc=$?; body=${code%$'\n'*}; status=${code##*$'\n'}
    printf '%s\n' "$body"
    [[ $started == 1 ]] && stop
    [[ $rc == 0 && "$status" =~ ^2 ]] || { log "[error] HTTP $status for $route"; exit 1; } ;;
  *) echo "usage: $0 start|stop|status|get /route" >&2; exit 64 ;;
esac
