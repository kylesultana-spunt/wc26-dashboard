"""Fit probability calibration from backtest_results.csv.

Writes data/calibration.json:
  {"a":<global>, "b":<global>, "fam": {<family>: {"a":..,"b":..}, ...}}

Calibration maps a raw model probability p to a corrected one via Platt scaling:
    p_cal = sigmoid(a + b * logit(p)),  capped at 0.93.

A single GLOBAL (a,b) is fit on all held-out predictions. Each market FAMILY also gets
its own (a,b), shrunk toward the global by sample size (w = n/(n+K)), so sparse families
(saves, offsides, fouls) stay stable while data-rich ones (corners, shots, goals, result)
can correct their own bias. This fixes the systematic under-prediction of count markets
(corners/shots/saves) that a single global curve cannot, since it is symmetric in logit.

Run after backtest.py (which produces backtest_results.csv). Pure numpy; no scipy needed.
"""
import os, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
K_SHRINK = 1500.0   # family fit is shrunk toward global with weight n/(n+K)
P_CAP = 0.93


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _sig(z):
    return 1.0 / (1.0 + np.exp(-z))


def fit_platt(x, y, iters=60):
    """Logistic regression y ~ a + b*x by Newton/IRLS. Returns (a, b)."""
    X = np.column_stack([np.ones_like(x), x])
    beta = np.array([0.0, 1.0])
    for _ in range(iters):
        p = _sig(X @ beta)
        W = np.clip(p * (1 - p), 1e-6, None)
        grad = X.T @ (y - p)
        H = -(X * W[:, None]).T @ X
        try:
            step = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            break
        beta = beta - step
        if np.max(np.abs(step)) < 1e-9:
            break
    return float(beta[0]), float(beta[1])


def run():
    df = pd.read_csv(os.path.join(DATA, "backtest_results.csv"))
    x = _logit(df.p.values)
    y = df.y.values.astype(float)
    ga, gb = fit_platt(x, y)

    fam = {}
    for f, g in df.groupby("family"):
        fa, fb = fit_platt(_logit(g.p.values), g.y.values.astype(float))
        w = len(g) / (len(g) + K_SHRINK)
        fam[f] = {"a": round(w * fa + (1 - w) * ga, 4),
                  "b": round(w * fb + (1 - w) * gb, 4)}

    out = {"a": round(ga, 4), "b": round(gb, 4), "fam": fam}
    path = os.path.join(DATA, "calibration.json")
    # keep a one-time backup of the previous (global-only) calibration
    if os.path.exists(path):
        old = json.load(open(path))
        if "fam" not in old and not os.path.exists(path + ".global.bak"):
            json.dump(old, open(path + ".global.bak", "w"))
    json.dump(out, open(path, "w"))
    print(f"global a={ga:+.4f} b={gb:.4f}")
    for f, v in sorted(fam.items()):
        print(f"  {f:9} a={v['a']:+.4f} b={v['b']:.4f}")
    print(f"wrote {path}")


if __name__ == "__main__":
    run()
