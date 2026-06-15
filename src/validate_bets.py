"""Betting-specific validation — profit, not just accuracy.

Two reports:

1) backtest_report()  — what's computable NOW from data/backtest_results.csv (held-out
   Euro 2024 / Copa 2024 / WC 2022 predictions). We have outcomes but no historical odds,
   so this is a CALIBRATION P&L: flat 1u stakes at the model's own fair odds (1/p_cal).
   ROI here is positive only if flagged bets win *more* often than the model claims
   (under-confidence = safe) and negative if they win less (over-confidence = bleed).
   It is NOT real ROI — subtract the bookmaker margin (~3-5%) for a realistic figure,
   and remember you only truly profit where your probability beats a *specific* market.

2) ledger_report() — real ROI / yield / CLV / Kelly growth / max drawdown, once you log
   actual bets (taken odds + closing odds + result) to data/bets.csv. This is the metric
   that matters; it populates as you bet. Use log_bet() (or predict.py --log) to append.

Run:  python3 src/validate_bets.py            # backtest calibration P&L
      python3 src/validate_bets.py --ledger   # real CLV/ROI from data/bets.csv
"""
import os, sys, csv, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models

DATA = models.DATA
BET_P = 0.72
LEDGER = os.path.join(DATA, "bets.csv")
LEDGER_COLS = ["date", "match", "market", "p_model", "odds_taken", "odds_close", "result"]


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _sig(z):
    return 1.0 / (1.0 + np.exp(-z))


def _calibrate(p, market, cal):
    c = cal.get("fam", {}).get(models.market_family(market)) or cal
    return float(min(_sig(c["a"] + c["b"] * _logit(p)), 0.93))


def _max_drawdown(equity):
    """Largest peak-to-trough drop on a cumulative-equity curve."""
    peak = np.maximum.accumulate(equity)
    return float((peak - equity).max()) if len(equity) else 0.0


# ---------------------------------------------------------------- backtest P&L
def backtest_report():
    df = pd.read_csv(os.path.join(DATA, "backtest_results.csv"))
    cal = json.load(open(os.path.join(DATA, "calibration.json")))
    df["pc"] = [_calibrate(p, k, cal) for p, k in zip(df.p, df.market)]
    bets = df[df.pc >= BET_P].reset_index(drop=True)
    n = len(bets)
    if n == 0:
        print("no flagged bets in backtest"); return
    ret = bets.y.values / bets.pc.values - 1.0          # flat 1u @ fair odds
    equity = np.cumsum(ret)
    roi = float(ret.mean())
    print("=== Backtest calibration P&L (flat 1u @ model fair odds) ===")
    print(f"  flagged bets (p>={BET_P}):  {n}")
    print(f"  hit rate:                {bets.y.mean()*100:.1f}%   (avg model p {bets.pc.mean()*100:.1f}%)")
    print(f"  ROI / unit:              {roi*100:+.2f}%   (>0 under-confident/safe, <0 over-confident)")
    print(f"  cumulative P&L:          {equity[-1]:+.1f}u over {n} bets")
    print(f"  max drawdown:            {_max_drawdown(equity):.1f}u")
    print(f"  realistic ROI (-~4% mkt margin): {(roi-0.04)*100:+.2f}%  <- why accuracy != profit")
    print("\n  edge by family (where the real value is):")
    rows = []
    for fam, g in bets.groupby(bets.market.map(models.market_family)):
        r = float((g.y.values / g.pc.values - 1).mean())
        rows.append((fam, len(g), g.y.mean()*100, r*100))
    for fam, gn, hit, r in sorted(rows, key=lambda x: -x[3]):
        print(f"    {fam:9} n={gn:4}  hit {hit:4.1f}%  fair-odds ROI {r:+5.1f}%")
    out = {"n": n, "hit": float(bets.y.mean()), "avg_p": float(bets.pc.mean()),
           "roi_fair": roi, "max_drawdown_u": _max_drawdown(equity),
           "equity": [round(float(x), 4) for x in equity],
           "by_family": {f: {"n": gn, "hit": hit/100, "roi_fair": r/100} for f, gn, hit, r in rows}}
    json.dump(out, open(os.path.join(DATA, "betting_validation.json"), "w"))
    print(f"\n  wrote data/betting_validation.json")
    return out


# ---------------------------------------------------------------- live ledger
def log_bet(date, match, market, p_model, odds_taken, odds_close="", result=""):
    """Append one bet to data/bets.csv (create with header if missing)."""
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(LEDGER_COLS)
        w.writerow([date, match, market, round(float(p_model), 4),
                    odds_taken, odds_close, result])


def ledger_report():
    """Real ROI / yield / CLV / Kelly growth / drawdown from settled bets in data/bets.csv.
    Needs odds_taken, odds_close and result (1=win, 0=loss) filled in."""
    if not os.path.exists(LEDGER):
        print(f"no ledger yet — create {LEDGER} with columns: {','.join(LEDGER_COLS)}")
        return
    d = pd.read_csv(LEDGER)
    s = d.dropna(subset=["odds_taken", "result"]).copy()
    s = s[s.result.isin([0, 1, "0", "1"])]
    if len(s) == 0:
        print("ledger has no settled bets yet (need odds_taken + result)."); return
    s["result"] = s.result.astype(float)
    s["odds_taken"] = s.odds_taken.astype(float)
    # flat-stake P&L
    pnl = np.where(s.result == 1, s.odds_taken - 1, -1.0)
    equity = np.cumsum(pnl)
    roi = pnl.sum() / len(s)
    # fractional-Kelly bankroll growth
    bank, KELLY = 1.0, 0.25
    curve = [bank]
    for p, o, res in zip(s.p_model.astype(float), s.odds_taken, s.result):
        b = o - 1
        edge = (b * p - (1 - p)) / b if b > 0 else 0
        stake = max(0.0, edge) * KELLY * bank
        bank += stake * (b if res == 1 else -1)
        curve.append(bank)
    print("=== Live betting performance (data/bets.csv) ===")
    print(f"  settled bets:      {len(s)}")
    print(f"  hit rate:          {s.result.mean()*100:.1f}%")
    print(f"  ROI / yield:       {roi*100:+.2f}%  (profit per unit staked, flat)")
    print(f"  flat P&L:          {equity[-1]:+.2f}u   max drawdown {_max_drawdown(equity):.2f}u")
    print(f"  Kelly growth (¼):  {curve[-1]:.3f}x bankroll")
    cl = s.dropna(subset=["odds_close"])
    if len(cl):
        cl = cl[cl.odds_close.astype(float) > 0]
        clv = (cl.odds_taken.astype(float) / cl.odds_close.astype(float) - 1) * 100
        print(f"  CLV:               {clv.mean():+.2f}% avg, beat the close {100*(clv>0).mean():.0f}% of the time")
        print("                     (positive CLV is the strongest predictor of long-run profit)")
    else:
        print("  CLV:               n/a — fill odds_close to enable")


if __name__ == "__main__":
    if "--ledger" in sys.argv:
        ledger_report()
    else:
        backtest_report()
