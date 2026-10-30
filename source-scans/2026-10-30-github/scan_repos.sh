#!/usr/bin/env bash
# Re-runnable GitHub repo sweep for research-source prior art (2026-10-30).
# Output: raw/<slug>.json per query + raw/all.tsv (stars, repo, pushed, description).
set -uo pipefail
cd "$(dirname "$0")"
queries=(
  "deep research agent"
  "research agent web search sources"
  "awesome public apis"
  "xiaohongshu crawler"
  "weibo zhihu bilibili crawler"
  "metasearch engine self-hosted"
  "rss feed generator everything"
  "osint tools collection"
  "agent internet access twitter reddit youtube"
  "reddit scraper without api"
  "twitter scraper without api"
  "free web search api llm"
  "social media search cli"
  "claude skill research"
)
: > raw/all.tsv
for q in "${queries[@]}"; do
  slug=$(echo "$q" | tr ' ' '-')
  gh api -X GET search/repositories -f q="$q" -f sort=stars -f order=desc -f per_page=15 > "raw/$slug.json" 2>"raw/$slug.err"
  rc=$?
  n=$(jq '.items | length' "raw/$slug.json" 2>/dev/null || echo 0)
  total=$(jq '.total_count' "raw/$slug.json" 2>/dev/null || echo "?")
  echo "QUERY|$q|rc=$rc|returned=$n|total=$total"
  jq -r --arg q "$q" '.items[] | [.stargazers_count, .full_name, (.pushed_at[:10]), ($q), ((.description // "")[:120])] | @tsv' "raw/$slug.json" >> raw/all.tsv 2>/dev/null
  sleep 2
done
# Third-party repo descriptions sometimes contain live keys (2026-10-30: a Google API key in
# amir2510/script tripped GitHub secret scanning). Redact key-shaped strings before keeping raw output.
redact='s/AIza[0-9A-Za-z_-]{35}/[REDACTED-GOOGLE-KEY]/g; s/gh[opsu]_[0-9A-Za-z]{36,}/[REDACTED-GITHUB-TOKEN]/g; s/github_pat_[0-9A-Za-z_]{40,}/[REDACTED-GITHUB-TOKEN]/g; s/sk-[A-Za-z0-9_-]{20,}/[REDACTED-SK-KEY]/g; s/AKIA[0-9A-Z]{16}/[REDACTED-AWS-KEY]/g; s/xox[abprs]-[0-9A-Za-z-]{10,}/[REDACTED-SLACK-TOKEN]/g; s/tvly-[0-9A-Za-z_-]{20,}/[REDACTED-TAVILY-KEY]/g'
sed -E -i "$redact" raw/*.json raw/all.tsv
sort -t$'\t' -k2,2 -u raw/all.tsv | sort -t$'\t' -k1,1 -nr > raw/unique.tsv
echo "unique repos: $(wc -l < raw/unique.tsv)"
