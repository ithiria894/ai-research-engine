#!/usr/bin/env bash
# Commit + push finished (zstd) parts of ~/data/reddit-archive to the PRIVATE GitHub repo
# ithiria894/reddit-archive. In-progress plain .jsonl parts are gitignored.
# GitHub limits respected: every .zst part < 100 MB (checked), each push batch < 1.5 GB.
set -euo pipefail
cd "$HOME/data/reddit-archive"
log() { echo "$(date '+%F %T') [sync] $*" | tee -a sync.log; }
log "start"
# refuse to push anything >= 95 MB (GitHub hard limit is 100 MB)
big=$(find . -path ./.git -prune -o -name '*.zst' -size +95M -print)
if [ -n "$big" ]; then log "ERROR oversize parts, not pushing: $big"; exit 1; fi
git add -A -- '*/DONE' README.md .gitignore run.log sync.log 2>/dev/null || true
batch=0; limit=$((1500*1024*1024)); n=0
while IFS= read -r f; do
  sz=$(stat -c %s "$f")
  if (( batch + sz > limit && n > 0 )); then
    git commit -q -m "archive batch ($n parts, $((batch/1024/1024)) MB)" && git push -q origin HEAD:main
    log "pushed batch: $n parts, $((batch/1024/1024)) MB"; batch=0; n=0
  fi
  git add -- "$f"; batch=$((batch+sz)); n=$((n+1))
done < <(git ls-files --others --exclude-standard -- '*.zst')
if ! git diff --cached --quiet; then
  git commit -q -m "archive sync ($n parts, $((batch/1024/1024)) MB)" && git push -q origin HEAD:main
  log "pushed: $n parts, $((batch/1024/1024)) MB"
else
  log "nothing new"
fi
