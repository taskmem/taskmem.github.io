#!/usr/bin/env bash
# Warm jsDelivr CDN cache for the assets used by the project page.
#
# Run this AFTER `git push` so the very first real visitor lands on a
# pre-warmed edge cache instead of paying the cold-cache origin-fetch cost.
#
# It does two things:
#   1) Purge jsDelivr's edge for our pinned `@main` paths (so it fetches
#      the freshly pushed commit instead of an older cached version).
#   2) Re-fetch each asset to populate the edge cache.
#
# Usage:
#   bash scripts/warm_cdn.sh

set -euo pipefail

REPO="taskmem/taskmem.github.io"
BRANCH="main"
CDN_BASE="https://cdn.jsdelivr.net/gh/${REPO}@${BRANCH}/"
PURGE_BASE="https://purge.jsdelivr.net/gh/${REPO}@${BRANCH}/"

# Assets that affect first-paint or first interaction. Keep this list
# in sync with what the page actually loads from jsDelivr.
ASSETS=(
  "static/images/introduction.png"
  "static/images/train.png"
  "static/videos/merged.mp4"
  "static/videos/HmnKbBmYii8_0.mp4"
  "static/videos/aWBRHk_-5as_0_new.mp4"
  "static/videos/hsKmC7RwHvo_3.mp4"
)

echo "=== 1) Purge jsDelivr edge cache (forces pull of latest commit) ==="
for asset in "${ASSETS[@]}"; do
  url="${PURGE_BASE}${asset}"
  printf "  purge %-50s -> " "${asset}"
  code=$(curl -sS -o /dev/null -w "%{http_code}" "${url}" || echo "ERR")
  echo "HTTP ${code}"
done

echo ""
echo "=== 2) Warm edge cache (HEAD each asset, retry once on miss) ==="
for asset in "${ASSETS[@]}"; do
  url="${CDN_BASE}${asset}"
  for attempt in 1 2; do
    printf "  warm[%d] %-50s -> " "${attempt}" "${asset}"
    out=$(curl -sSI -o /dev/null \
      -w "HTTP %{http_code}, %{time_total}s, ttfb=%{time_starttransfer}s, age=%header{age}, x-cache=%header{x-cache}" \
      "${url}" || echo "ERR")
    echo "${out}"
    # If second attempt also missed, give up; jsDelivr will warm on
    # next real request anyway.
    [[ "${attempt}" == "2" ]] && break
  done
done

echo ""
echo "Done. The first real visitor should now hit warm caches."
