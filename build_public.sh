#!/bin/bash
# Build the public PITCHIQ site (separate from dashboard.html).
#   1. build_predictions.py  -> site_data/*.json  (runs the model once for all 72 fixtures)
#   2. build_public_site.py  -> site/             (static HTML: hub, fixtures, groups, teams, matches)
# Re-run after each matchday (./refresh.sh first to pull new results), then redeploy site/.
set -e
cd "$(dirname "$0")"
python3 src/build_predictions.py
python3 src/build_public_site.py
echo
echo "Open site/index.html in a browser. To publish, host the site/ folder on any static host"
echo "(Netlify, Cloudflare Pages, GitHub Pages) — it needs no server."
