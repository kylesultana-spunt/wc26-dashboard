# Betting validation — profit, not accuracy

*Implements review item #9. Run `python3 src/validate_bets.py` (backtest) or
`python3 src/validate_bets.py --ledger` (live, once you've logged real bets).*

## Why this matters

The model was only ever validated on **prediction quality** (Brier, hit rate). That is not
the same as **profitability**. A model can hit 82% and still lose money if the bookmaker's
margin is bigger than its edge. This report measures money.

## What's computable now (held-out backtest)

We have outcomes for 2,275 flagged bets (p ≥ 0.72, after per-market calibration) across
Euro 2024, Copa América 2024 and WC 2022 — **but no historical odds**. So this is a
*calibration P&L*: flat 1-unit stakes at the model's own fair odds (1/p). It answers
"if the market priced exactly at our probability, would we grow or bleed?"

| metric | value | reading |
|---|---|---|
| flagged bets | 2,275 | |
| hit rate | 81.6% | vs avg model p 81.4% — **calibrated almost perfectly** in the bet zone |
| ROI / unit (fair odds) | **+0.55%** | marginally under-confident → not bleeding |
| cumulative P&L | +12.6u | over 2,275 bets |
| max drawdown | 24.7u | meaningful variance — stake accordingly |
| **realistic ROI (−~4% margin)** | **−3.45%** | **this is the headline** |

**The headline finding:** at 81.6% the picks are well-calibrated, but the model's edge
over a *fair* line is only +0.55%. A typical bookmaker margin (3–5%) is bigger than that
edge — so blindly betting every flagged pick at market odds **loses money**. Accuracy ≠
profit. You only profit where your probability beats a *specific* market's implied price,
which is exactly what the existing edge filter (`pc − 1/odds ≥ 5pts`) is for — this
validates that the filter is doing essential work, not decoration.

## Where the edge actually lives (by family, fair-odds ROI)

| family | n | hit | fair-odds ROI |
|---|---|---|---|
| **corners** | 104 | 86.5% | **+15.9%** |
| offsides | 99 | 81.8% | +5.7% |
| fouls | 117 | 85.5% | +2.8% |
| saves | 85 | 81.2% | +1.2% |
| goals | 908 | 83.5% | +1.1% |
| shots | 173 | 77.5% | −0.2% |
| result | 235 | 80.9% | −2.1% |
| **cards** | 554 | 78.5% | **−3.3%** |

Corners carry a large positive edge even before beating the market line — consistent with
the calibration review, which found corners were the most under-priced market. Cards and
result picks are negative-edge at fair odds: avoid flat-betting them, demand a bigger
price gap. (Small-n families like corners/offsides need more data to confirm.)

## Equity curve

See `equity.png` — cumulative units over the 2,275 flagged bets. The curve grinds upward
but with a 24.7u peak-to-trough drawdown, a realistic picture of variance on a thin edge.

## The metric that actually matters: CLV (needs going-forward logging)

True ROI, yield, **Closing Line Value**, Kelly growth and live drawdown require the odds
you *took* and the *closing* odds — never archived for the backtest. So the validator has a
second mode that reads a bet ledger:

`data/bets.csv` columns: `date, match, market, p_model, odds_taken, odds_close, result`

Populate it two ways:
- **Auto:** `python3 src/predict.py --home A --away B --odds my_odds.txt --log` appends every
  `*** BET ***` pick with the odds you entered.
- **Manual:** add a row when you place a bet; fill `odds_close` (the price at kickoff) and
  `result` (1/0) afterwards.

Then `python3 src/validate_bets.py --ledger` reports real **ROI, yield, ¼-Kelly bankroll
growth, max drawdown, and CLV** (average % you beat the close, and how often). CLV is the
single best predictor of long-run profit — if you consistently beat the closing line, the
money follows even when individual bets lose.

## Bottom line

- The model is **well-calibrated** (good) but its **raw edge is thin** (+0.55% vs fair).
- Profit depends entirely on the **edge-vs-market filter** and on **which markets** you bet
  — corners/offsides/fouls carry edge, cards/result do not at fair odds.
- Start logging bets now so CLV/ROI/Kelly become real numbers rather than backtest proxies.
