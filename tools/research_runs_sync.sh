#!/usr/bin/env bash
# Hourly backup of ~/MyGithub/research-runs (raw research data, NOT otherwise in git) to the PRIVATE
# repo ithiria894/research-runs. Nicole 2026-11-04: 「全部開private repo」(incl. medical-record runs).
# Files > 95 MB (GitHub limit 100 MB) are split into 90 MiB parts + .sha256 + .README.md; the original is gitignored.
set -euo pipefail
cd "$HOME/MyGithub/research-runs"
log() { echo "$(date '+%F %T') [research-runs-sync] $*" | tee -a .sync.log; }
while IFS= read -r f; do
  rel="${f#./}"
  grep -qxF "/$rel" .gitignore 2>/dev/null && [ -f "$f.part-00" ] && continue
  log "splitting oversize $rel ($(stat -c %s "$f") bytes)"
  ( cd "$(dirname "$f")" && b=$(basename "$f") && sha256sum "$b" > "$b.sha256" && rm -f "$b".part-* && split -b 90M -d -a 2 "$b" "$b.part-" \
    && printf '# %s — split for GitHub (100 MB limit)\n\nRebuild: `cat %s.part-* > %s && sha256sum -c %s.sha256`\n' "$b" "$b" "$b" "$b" > "$b.README.md" )
  grep -qxF "/$rel" .gitignore 2>/dev/null || echo "/$rel" >> .gitignore
done < <(find . -path ./.git -prune -o -type f -size +95M ! -name '*.part-*' -print)
git add -A
if git diff --cached --quiet; then log "nothing new"; exit 0; fi
git commit -q -m "research-runs sync $(date '+%F %H:%M')"
git push -q origin HEAD:main
log "pushed $(git log -1 --format=%h)"
