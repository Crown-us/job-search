#!/usr/bin/env bash
# Publish data/site/ ke branch gh-pages (GitHub Pages).
# Branch-nya selalu satu commit (force push), jadi history main tetap bersih
# dan repo nggak membengkak oleh jobs.json harian.
set -euo pipefail
cd "$(dirname "$0")/.."
SITE=data/site
[ -f "$SITE/index.html" ] || { echo "!! $SITE/index.html belum ada, jalankan: jobhunter site"; exit 1; }

REMOTE="$(git remote get-url origin)"
NAME="$(git config user.name)"
EMAIL="$(git config user.email)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cp -r "$SITE"/. "$TMP"/
touch "$TMP/.nojekyll"
git -C "$TMP" init -q -b gh-pages
git -C "$TMP" add -A
git -C "$TMP" -c user.name="$NAME" -c user.email="$EMAIL" \
    commit -q -m "situs $(date '+%Y-%m-%d %H:%M')"
git -C "$TMP" push -q --force "$REMOTE" gh-pages
echo "terbit: gh-pages"
