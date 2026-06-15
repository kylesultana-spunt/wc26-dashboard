#!/bin/bash
# CI build: refresh data from ESPN + rebuild dashboard, then stage it for Cloudflare Pages.
# Skips the Transfermarkt-zip steps (build_club / build_ref_club) — their derived CSVs
# (club_rates.csv, ref_club_rates.csv) are committed, so they only need re-running locally
# when the dump is refreshed.
set -e
cd "$(dirname "$0")"

curl -s -o data/results_all.csv "https://raw.githubusercontent.com/martj42/international_results/master/results.csv" || true
curl -s -A "Mozilla/5.0" -o data/elo.tsv "https://www.eloratings.net/World.tsv" || true

python3 src/harvest.py refresh
until python3 src/harvest.py | grep -q DONE; do echo "...fetching more"; done
python3 src/build_referees.py
python3 src/build_tempo.py
python3 src/export_dashboard.py

# stage for Cloudflare Pages (publish dir = public/, entrypoint index.html)
mkdir -p public
cp dashboard.html public/index.html
echo "built public/index.html"
