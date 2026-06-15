# WC26 Bet Model

Finds high-probability (72%+) bets at odds 1.5+ across goals, corners, cards, fouls,
team shots/SoT and player props for World Cup 2026.

## Dashboard (main way to use this)

Open **dashboard.html** in any browser. Pick any fixture (real WC schedule is preloaded)
or any two of the 48 teams, set stage/referee/rivalry, tick the players you care about,
hit Run. The Bet Tips are ranked by model confidence; type a bookmaker price into any
card to see the edge and EV. Odds you enter are remembered per fixture. Everything runs
locally in the browser (12,000 simulations per run); no internet needed once built.

After each matchday run `./refresh.sh` (or the two commands below) to pull the newly
played matches and rebuild the dashboard with updated team/referee/player numbers.

## Odds

There is **no automatic odds feed**. The model never takes bookmaker prices as an input
(market prices are the opponent, not a signal). Enter prices manually on any tip card to
get its edge/EV. The old the-odds-api and oddschecker/Chrome scraping integrations have
been removed.

## Daily use (CLI alternative)

1. **Refresh data** (picks up newly played WC matches + referee appearances):
   ```
   python3 src/harvest.py refresh
   python3 src/harvest.py          # repeat until it prints DONE
   ```
2. **Run a fixture** (only inputs you ever give: teams, ref, stage, players you care about):
   ```
   python3 src/predict.py --home "USA" --away "Paraguay" --ref "Facundo Tello" \
       --stage group --players "Christian Pulisic:USA, Diego Gomez:Paraguay" \
       --odds my_odds.txt --json usa_par.json
   ```
   - `--odds` file: one line per market, `market_key odds` (e.g. `cards_over_2.5 1.62`).
     Without it, the output shows **fair odds** and the **minimum odds** worth taking.
   - `--rivalry` adds a card-temperature bump for grudge matches.
   - Injuries/rotation: just exclude affected players from `--players`; for team markets,
     judgement call — the model can't see lineups until you tell it.

## Referees

Each match's referee is read from ESPN (`src/build_referees.py`, run by `./refresh.sh`)
and synced by match ID into `data/referee_matches.csv`. The model applies that referee's
card tendency to the cards markets, the review re-grades completed matches with their real
official, and selecting a fixture auto-fills its assigned ref (announced refs for matches
within 3 days are pulled automatically). A ref gets the full card adjustment once he has
matches on record under the same name; until then his multiplier shrinks toward neutral. Each ref's card tendency now also blends his **club-football** record (`src/build_ref_club.py` from the Transfermarkt games/events dump, ~88k club matches), so even refs with few internationals have a stable strictness estimate (weight `CLUB_REF_W`, capped at 100 games).

## Bet rule

Flag = calibrated probability >= 72% AND odds >= 1.5 AND edge over implied >= 5 points.
Probabilities are Platt-calibrated on backtest and capped at 93% (the model proved
overconfident above that). **Bet singles. Doubles multiply risk past the rule.**

## What's under the hood

- `data/` — 3,351 internationals since WC 2022 (team + player + referee stats from
  ESPN's public API), full results history since 1872, self-computed Elo.
- `src/models.py` — Elo + Poisson goal curve (Dixon-Coles-lite), negative-binomial
  corners/shots/fouls with opponent & Elo-gap adjustment, referee-multiplier cards
  model, per-90 player props with shrinkage. 20k-sim Monte Carlo per fixture.
- `src/backtest.py` — held-out validation on Euro 2024, Copa América 2024, WC 2022.

## Market menu (bet365-aligned)

Goals: O/U + alternative lines, BTTS, team goals, goal ranges, exact/correct score,
result, double chance, DNB, winning margin, HT/FT, HT correct score, 1st/2nd-half
goals, goal in both halves, half with most goals.
Corners: O/U, 3-way (over/exactly/under) at every line 4–12, team corners, most corners.
Cards: match/team O/U, both teams to receive a card, most cards, red card in match,
1st-half cards — all referee-adjusted.
Other: total shots, total SoT, fouls, offsides, GK saves per team.
Player props: shots 1+..5+, SoT 1+..4+, to score, score or assist, assists,
fouls committed, to be fouled, to be booked, GK saves.

NOT modelled (no free data exists; bet365 prices these off Opta): throw-ins,
goal kicks, player passes/tackles, headed SoT, SoT outside box. Team tackles
markets were built then REMOVED — they failed backtest (59% hit at 72%+ claimed).

## Backtest (held-out tournaments, ~22,700 market predictions)

| Model says (calibrated) | Actually happened |
|---|---|
| 70–80% | 77.2% |
| 80–90% | 82.5% |
| 90%+ | 88.8% |

Bet rule (p>=0.72) hit 81.2% across 2,202 flagged markets.

## Performance trends (PAST RESULTS tab)

Completed matches are listed in **chronological order** (oldest first), and the tab
opens with two running-average charts. Gold dashes mark algorithm updates.

1. **Betting suggestion correctness** — share of graded picks that landed (100% = best).
2. **Stat prediction calibration (z-score)** — each predicted stat is standardised:
   **z = (actual − expected) / σ**, using the same σ the dashboard grades with
   (negative-binomial-style `sqrt(disp · mean)`). This weights a miss by how variable the
   market is, so a 1-foul miss and a 1-goal miss aren't treated the same.
   - **0 = on target (best);** the shaded band is the **±2σ expected range**.
   - Above 0 = reality came in higher than predicted (under-shot → predict higher);
     below 0 = lower (over-shot → predict lower). Points outside the band (amber) are
     matches where reality was unusually far from the model.
   - **Buttons** switch between all stats and any single market (Goals, Corners, Cards,
     Shots, SoT, Fouls).

Faint dots are single matches; bold lines are running averages. **Hover any column** to see that match, its score, and both the single-match and running values. Both rebuild
automatically from graded match history on every `./refresh.sh`.

**Mark when you change the algorithm.** Each change drops a dashed gold marker on both
charts. Log changes in the `ALGO_VERSIONS` list near the top of the `<script>` in
`src/dashboard_template.html`:

```js
const ALGO_VERSIONS=[
  {date:"2026-06-11",label:"v1.0",note:"Baseline model live for WC26 group stage"},
  // {date:"2026-06-20",label:"v1.1",note:"Recalibrated cards model"},
];
```

Edit it in the template (the source of truth) so markers survive the next refresh.

## Calibration (per-market)

Raw model probabilities are corrected by Platt scaling `p_cal = sigmoid(a + b·logit(p))`,
capped at 0.93. Calibration is **per market family**: `data/calibration.json` holds a
global `{a,b}` plus a `fam` block with its own `{a,b}` for goals, result, corners, cards,
shots, fouls, offsides and saves. This fixes a bias a single global curve cannot — held-out
backtesting showed corners/shots/saves were systematically **under-predicted** (reality
overshot by 4–7 points), while goals/result were spot on. Per-family fitting shrinks those
gaps to ~1 point and slightly improves the 72% bet-rule hit rate.

Re-fit after any model change or new backtest:

```
python3 src/backtest.py          # writes data/backtest_results.csv
python3 src/fit_calibration.py   # writes data/calibration.json (global + per-family)
python3 src/export_dashboard.py  # bakes the new calibration into the dashboard
```

The same `calibration.json` is consumed by `predict.py`, `export_dashboard.py` and the
browser (`D.league.cal`), each mapping a market to its family before calibrating. The old
global-only file is backed up once to `calibration.json.global.bak`.

The **Calibration health** panel in PAST RESULTS tracks this live from graded matches:
spread (std of standardised residuals — ~1 = the model's uncertainty is right), outlier
rate (~5% expected), overall bias, and per-market bias. Re-fit when a market's bias holds
past ±1σ over many games.

## Betting validation (profit, not accuracy)

Brier/hit-rate measure prediction quality, not money. `src/validate_bets.py` measures money:

- `python3 src/validate_bets.py` — backtest **calibration P&L**: at p≥0.72 the picks hit
  81.6% (well-calibrated) but the edge over a *fair* line is only +0.55%, so after a normal
  bookmaker margin, blindly betting every flag **loses** (−3.4%). Profit lives in the
  edge-vs-market filter and in specific markets — **corners (+15.9%)**, offsides and fouls
  carry edge; **cards (−3.3%)** and result do not at fair odds. See `BETTING_VALIDATION.md`.
- `python3 src/validate_bets.py --ledger` — real **ROI, yield, CLV, ¼-Kelly growth, max
  drawdown** from `data/bets.csv`. Log bets automatically with
  `python3 src/predict.py ... --odds my_odds.txt --log`, then fill `odds_close` + `result`.
  **CLV** (how much you beat the closing line) is the strongest long-run profit signal.

## Self-improving (auto-tune)

`src/autotune.py` is the learning loop. It coordinate-searches the model's hand-set
coefficients (recency half-life, competition weights, squad-value weight) and scores each
on **held-out Brier** across the backtest tournaments, then writes
`data/autotune_proposal.json` with the current vs best settings and the improvement.

It **never edits the model on its own** -- you review the proposal; only `python3
src/autotune.py --apply` patches `models.py`, after which you re-run
`backtest.py -> fit_calibration.py -> export_dashboard.py` and add an `ALGO_VERSIONS`
entry so the Model 1 vs Model 2 graph shows whether the new version actually helped.
Honest limit: it optimises calibration, not hit-rate -- over/under markets have a
variance ceiling (~55-65%), so the betting % plateaus; chasing it by overfitting loses.

## Honest limits

- Non-European teams have thinner corners/cards history (ESPN lacks AFC/CAF/CONMEBOL/
  CONCACAF qualifier stats) — the model shrinks toward the mean, so it will rarely
  flag exotic markets for those teams until their WC group games feed in.
- Hit rate isn't profit. The edge filter vs actual odds is what matters — always
  enter the real prices.
- Small samples, 64+ matches max. Variance is real; stake accordingly.
