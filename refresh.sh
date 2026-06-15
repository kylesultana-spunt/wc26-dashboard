#!/bin/bash
# Refresh data (new WC matches/refs) and rebuild dashboard.html. Run after each matchday.
cd "$(dirname "$0")"
# global results + official Elo (feeds the ratings — must stay current)
curl -s -o data/results_all.csv "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
curl -s -A "Mozilla/5.0" -o data/elo.tsv "https://www.eloratings.net/World.tsv"
python3 src/harvest.py refresh
until python3 src/harvest.py | grep -q DONE; do echo "...fetching more"; done
python3 src/build_referees.py
python3 src/build_ref_club.py
python3 src/build_tempo.py
python3 src/export_dashboard.py
echo "dashboard.html updated — reopen it in your browser."
