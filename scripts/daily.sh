#!/usr/bin/env bash
# Daily pipeline for Linux: pull -> enrich -> analyze -> public site -> Discord feeds -> sync.
# Same steps as daily.cmd minus the Windows toast. Override PY to use another interpreter.
set -u
cd "$(dirname "$0")/.."
PY="${PY:-$HOME/.venvs/jobhunter/bin/python}"
DEV_CHANNEL=1561725081095250023
KREATIF_CHANNEL=1561730155158966363
REMOTE_CHANNEL=1561733022368407623
SKIP_DISCORD="${SKIP_DISCORD:-0}"

run() { echo "== $*"; "$PY" -m jobhunter "$@" || echo "!! gagal: $1 (lanjut ke langkah berikutnya)"; }

run discover --per-board 40 --limit 900
run enrich --limit 30 --min-score 60
run analyze --limit 15 --min-score 75
run digest --limit 12 --min-fit 60
run site
if [ "$SKIP_DISCORD" != "1" ]; then
  run discord --per-job --public --only-new --exclude-feeds --max-age-days 30 --limit 3 --min-fit 70 \
      --tracks fullstack,it_support,ai_junior,admin_data --channel "$DEV_CHANNEL"
  run discord --per-job --public --only-new --exclude-feeds --max-age-days 30 --limit 2 --min-fit 75 \
      --tracks marketing,video_editor,graphic_design,social_media --channel "$KREATIF_CHANNEL"
  run discord --per-job --public --only-new --feeds-only --max-age-days 45 --limit 3 --min-fit 60 \
      --tracks fullstack,it_support,ai_junior,marketing,video_editor,graphic_design,social_media --channel "$REMOTE_CHANNEL"
  run sync
fi
echo "selesai: data/site/index.html"
