# Algorithm review — what's driving the fluctuations

*Diagnostic run on the 9 reviewed WC26 matches (108 stat predictions) and cross-checked
on 22,651 held-out backtest predictions (Euro 2024, Copa América 2024, WC 2022).*

## TL;DR

The match-to-match **fluctuations you're seeing are healthy noise, not a model fault** —
they're exactly the size a correctly-calibrated model should produce, and trying to
"smooth" them away would make the model worse (overconfident). **But** the analysis did
surface two *real, capturable* miscalibrations underneath the noise. Fix those, not the
wiggle.

## 1. The fluctuations themselves are noise — leave them alone

Standardised residuals z = (actual − expected) / σ across the 9 matches:

| metric | value | what a perfect model gives |
|---|---|---|
| spread (std of z) | **0.98** | 1.00 |
| outliers beyond ±2σ | **5.6%** | ~4.6% |
| range | −1.5 to +3.3 | bounces in ±2–3 |

A standardised residual std of ~1.0 is the textbook signature of **correct** uncertainty.
The model's σ is right: single matches *should* swing between roughly ±2σ. A model whose
per-match line sat flat on zero would be overfit and would hand you false "edges." So the
up-and-down is the model working, not failing.

## 2. The real signal hiding underneath: two specific miscalibrations

### (a) Count markets are under-predicted — corners, shots, saves
Confirmed on the large backtest (so it's not small-sample noise), and it matches the live
review (shots +0.42σ, corners running high):

| market | n (backtest) | predicted | actual | gap |
|---|---|---|---|---|
| corners | 3,984 | 38.7% | 45.2% | **+6.6** |
| saves | 664 | 40.2% | 46.7% | **+6.5** |
| shots | 2,324 | 48.9% | 53.7% | **+4.8** |
| cards | 2,525 | 49.3% | 51.6% | +2.4 |
| goals | 5,439 | 47.3% | 47.0% | −0.3 |
| result | 6,387 | 19.0% | 18.9% | −0.1 |
| fouls | 664 | 50.0% | 50.0% | 0.0 |

Reality **overshoots** our corner/shot/save numbers systematically. Goals, result and
fouls are bang on. This is the single most actionable finding — and it explains the small
+0.27σ upward bias you noticed live.

### (b) High-confidence picks are overconfident
Calibration by predicted-probability bucket (backtest):

| model says | actually happens | gap |
|---|---|---|
| 0–50% | 25.4% (pred 22.0) | +3.4 |
| 50–60% | 57.6% | +2.5 |
| 60–70% | 65.2% | +0.1 |
| 70–80% | 74.2% | −0.4 |
| 80–90% | **80.0%** (pred 84.9) | **−4.8** |
| 90%+ | **86.3%** (pred 93.2) | **−6.8** |

Classic S-curve: the middle is well-calibrated, but the extremes are too extreme. The
existing 93% cap helps, but the 80–95% range is still ~5–7 points hot — meaning some bets
flagged at the 72%+ rule are really mid-60s.

## 3. What was *not* a driver (ruled out)

- **Blowouts**: weak effect only — mean |z| 0.91 in 3+ goal games vs 0.66 in close ones,
  correlation +0.14. Expected and minor; not worth a feature.
- **Winner vs loser**: residual means near-identical (+0.24 vs +0.25). No systematic
  "we mis-read the losing side" effect.

## 4. Recommended changes (in priority order)

1. **Per-market calibration for the count stats.** The global Platt calibration is
   dominated by goals/result and barely touches corners/shots/saves. Fit (or bias-correct)
   corners, shots and saves separately — lift their predicted means ~5–7 points of
   probability. Biggest, safest win.
2. **Tame the top end.** Add curvature/shrinkage above ~80% (or lower the 93% cap to
   ~88–90%) so 90%-flagged bets are honestly ~86%. Protects the bankroll on "locks."
3. **Watch the +0.27σ global drift.** Too small to act on at n=9, but if it persists past
   ~30 matches, nudge the league means up. Don't touch it yet.
4. **Don't** try to model the match-to-match wiggle. It's irreducible variance.

## How to verify any change

Re-run `src/backtest.py` after a change and confirm: (a) the corner/shot/save family gaps
shrink toward 0, (b) the 80–90% and 90%+ buckets move toward their diagonal, and (c) the
overall hit-rate at the 72% rule holds or improves. A live calibration panel on the
dashboard (z-spread + per-market gap, updating each refresh) would let you watch this
without re-running the backtest.
