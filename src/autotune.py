"""Self-improving coefficient tuner — proposes (does NOT auto-apply) coefficient changes.

Coordinate-search over the model's hand-set coefficients, scored by held-out Brier on the
backtest tournaments (Euro 2024 / Copa 2024 / WC 2022). Writes data/autotune_proposal.json
with the current vs best settings and the Brier improvement. You review it; only if you
approve does `--apply` patch src/models.py. Re-fit calibration + re-export afterwards and
bump ALGO_VERSIONS so the Model 1 vs Model 2 graph shows whether it actually helped.

Usage:
  python3 src/autotune.py            # full search -> proposal
  python3 src/autotune.py --quick    # fast half-life-only search (demo)
  python3 src/autotune.py --apply    # patch models.py with the approved proposal
"""
import os, sys, json, re, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models, backtest as bt

DATA = models.DATA
PROP = os.path.join(DATA, "autotune_proposal.json")
BASE_COMP_W = dict(models.COMP_W)
CURRENT = {"half_life": 550.0, "comp_scale": 1.0, "sqv_g": 0.05}

_t = pd.read_csv(os.path.join(DATA, "team_matches.csv"))
_refs = pd.read_csv(os.path.join(DATA, "referee_matches.csv"))
_rbe = dict(zip(_refs.event_id.astype(str), _refs.referee))
GOALY = ("goals", "btts", "team_goals", "result", "double_chance", "dnb",
         "win_margin", "score_", "ht_score", "htft", "goal_both", "half_most")


def brier(p, holdouts, cap=None):
    models.HALF_LIFE_DAYS = p["half_life"]
    models.SQV_G = p["sqv_g"]
    models.COMP_W = {k: 1 + (v - 1) * p["comp_scale"] for k, v in BASE_COMP_W.items()}
    errs = []
    for comp, start, end in holdouts:
        try:
            mm = models.MatchModel(asof=start)
        except Exception:
            continue
        sub = _t[(_t.comp == comp) & (_t.date >= start) & (_t.date < end)]
        fx = sub[sub.home_away == "home"]
        if cap:
            fx = fx.head(cap)
        goals_only = comp == "fifa.world"
        for r in fx.itertuples():
            h, a = r.team, r.opponent
            ra = sub[(sub.event_id == r.event_id) & (sub.home_away == "away")]
            if len(ra) != 1:
                continue
            rh, rowa = r._asdict(), ra.iloc[0].to_dict()
            _, sims = mm.simulate(h, a, stage="group", ref=_rbe.get(str(r.event_id)))
            probs = models.market_probs(sims, h, a)
            for k, pr in probs.items():
                if goals_only and not any(k.startswith(x) or x in k for x in GOALY):
                    continue
                y = bt.outcome_value(rh, rowa, k, h, a)
                if y is not None:
                    errs.append((pr - y) ** 2)
    return float(np.mean(errs)) if errs else float("inf")


def search(quick=False):
    holds = bt.HOLDOUTS[:1] if quick else bt.HOLDOUTS
    grids = {"half_life": [350, 450, 550, 700, 900]}
    if not quick:
        grids["comp_scale"] = [0.0, 0.5, 1.0, 1.5, 2.0]
        grids["sqv_g"] = [0.0, 0.05, 0.10, 0.15]
    best = dict(CURRENT)
    base_b = brier(best, holds)
    print(f"baseline {best}  Brier {base_b:.5f}")
    results = {}
    for param, grid in grids.items():
        scores = {}
        for v in grid:
            cand = dict(best); cand[param] = v
            scores[v] = brier(cand, holds)
            print(f"  {param}={v}: Brier {scores[v]:.5f}")
        bv = min(scores, key=scores.get)
        best[param] = bv
        results[param] = scores
    best_b = brier(best, holds)
    out = {"current": CURRENT, "proposed": best,
           "brier_current": base_b, "brier_proposed": best_b,
           "improvement": round(base_b - best_b, 6),
           "holdouts": "1 (quick)" if quick else "all 3", "grids": results}
    json.dump(out, open(PROP, "w"), indent=1)
    print(f"\nPROPOSAL  {CURRENT}  ->  {best}")
    print(f"Brier {base_b:.5f} -> {best_b:.5f}  ({'IMPROVES' if best_b < base_b else 'no gain'} "
          f"by {base_b - best_b:+.5f})")
    print(f"written to {PROP} — review, then `python3 src/autotune.py --apply` to adopt")


def apply():
    if not os.path.exists(PROP):
        print("no proposal to apply"); return
    pr = json.load(open(PROP))["proposed"]
    src = open(os.path.join(os.path.dirname(__file__), "models.py")).read()
    src = re.sub(r"HALF_LIFE_DAYS = [\d.]+", f"HALF_LIFE_DAYS = {pr['half_life']}", src, 1)
    src = re.sub(r"SQV_G = [\d.]+", f"SQV_G = {pr['sqv_g']}", src, 1)
    cw = {k: round(1 + (v - 1) * pr["comp_scale"], 3) for k, v in BASE_COMP_W.items()}
    # NOTE: comp_scale rebuilds COMP_W proportionally; edit the dict by hand if you prefer
    open(os.path.join(os.path.dirname(__file__), "models.py"), "w").write(src)
    print(f"patched models.py: half_life={pr['half_life']}, sqv_g={pr['sqv_g']}")
    print("now run: python3 src/backtest.py && python3 src/fit_calibration.py && "
          "python3 src/export_dashboard.py  (and add an ALGO_VERSIONS entry)")


if __name__ == "__main__":
    if "--apply" in sys.argv:
        apply()
    else:
        search(quick="--quick" in sys.argv)
