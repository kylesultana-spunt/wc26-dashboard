# PITCHIQ — public World Cup 2026 site

A statz.ai-style public site generated from the betting model. **Separate from `dashboard.html`**
(your private tool); this is the consumer-facing site you can put online.

## Open it
Open `index.html` in any browser. Everything is static — no server needed.

## Pages
- **index.html** — landing: hero + verified track record, upcoming fixtures, results, group tables, favourites.
- **fixtures.html** — all 72 group games, filter by group / status / team search.
- **groups.html** — 12 group tables (live standings, top-2 qualify) + each group's fixtures.
- **teams.html** — all 48 nations, searchable, with rating and qualification status.
- **team/<country>.html** — profile: rating, win %, form, fixtures & results, squad players we price.
- **outrights.html** — model win probabilities for all 48, with implied fair prices.
- **match/<id>.html** — the statz-style slip builder (PITCHIQ Picks / Safer Slip / Long Shot /
  Goals + Shots / Match Lines), stake → returns, plus the full priced market browser and the
  model's projection. Completed matches show every pick graded.

## Rebuild
From `wc26/`:  `./build_public.sh`   (or run `src/build_predictions.py` then `src/build_public_site.py`).
Run `./refresh.sh` first on a matchday to pull new results, then rebuild.

## Customise
- Rename the site: change `BRAND` (one line) at the top of `src/build_public_site.py`.
- Colours live in the `CSS` block in the same file (matches the dashboard's violet/magenta palette).

## Note
Odds shown are the model's **fair** price, not a bookmaker offer. The accumulator slips mirror
statz's presentation; your own validation (see `BETTING_VALIDATION.md`) shows singles with a real
edge-vs-market are where the value is — shop the best book line and bet responsibly.
