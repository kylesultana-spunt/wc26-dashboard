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

# Pull real bookmaker odds once a day (09:00 UTC) or on a manual run — OddsPapi's free
# tier is ~250 calls/month, so we can't poll it every 15 min. Refreshes data/odds.json,
# which the Value Finder reads. Manual: run `python3 src/fetch_odds.py` locally any time.
if [ "$GITHUB_EVENT_NAME" = "workflow_dispatch" ] || \
   { [ "$(date -u +%H)" = "09" ] && [ "$(date -u +%M)" -lt 15 ]; }; then
  python3 src/build_squads.py || true     # refresh 26-man squads (ESPN) once a day
  python3 src/fetch_odds.py || true
fi

python3 src/export_dashboard.py

# stage for Cloudflare Pages (publish dir = public/, entrypoint index.html)
mkdir -p public
cp dashboard.html public/index.html
echo "built public/index.html"
