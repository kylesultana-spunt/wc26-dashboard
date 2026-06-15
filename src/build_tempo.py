"""Tournament-tempo adjustment: how much hotter does THIS World Cup run than the
model's baseline, per stat? Learned from completed WC26 matches, shrunk toward 1.0
so a small sample can't overfit. Recomputed every refresh; sharpens each matchday."""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models

DATA = models.DATA
STATS = ["goals", "corners", "yellows", "reds", "fouls", "shots", "sot", "offsides", "saves"]
K = 10.0          # prior strength: ~10 matches pulling toward ratio 1.0
CAP = (0.85, 1.30)

def main():
    t = pd.read_csv(os.path.join(DATA, "team_matches.csv"))
    wc = t[(t.comp == "fifa.world") & (t.date >= "2026-06-01")].dropna(subset=["corners_for"])
    fixtures = wc[wc.home_away == "home"]
    if len(fixtures) == 0:
        json.dump({"_n": 0}, open(os.path.join(DATA, "tempo.json"), "w"))
        print("tempo: no completed WC26 matches yet")
        return
    # model WITHOUT tempo (env flag) to get the un-adjusted expectation
    os.environ["WC26_NO_TEMPO"] = "1"
    mm = models.MatchModel()
    exp_sum = {s: 0.0 for s in STATS}
    act_sum = {s: 0.0 for s in STATS}
    n = 0
    for fx in fixtures.itertuples():
        h, a = fx.team, fx.opponent
        row_a = wc[(wc.team == a) & (wc.opponent == h) & (wc.date == fx.date)]
        if len(row_a) != 1:
            continue
        ra = row_a.iloc[0]
        lam = mm.lambdas(h, a, stage="group")
        for s in STATS:
            exp_sum[s] += lam[s][h] + lam[s][a]
            ah = getattr(fx, f"{s}_for"); aa = ra[f"{s}_for"]
            if pd.notna(ah) and pd.notna(aa):
                act_sum[s] += ah + aa
        n += 1
    tempo = {"_n": n}
    for s in STATS:
        ratio = act_sum[s] / exp_sum[s] if exp_sum[s] > 0 else 1.0
        shrunk = (n * ratio + K * 1.0) / (n + K)         # pull toward 1.0
        tempo[s] = round(float(np.clip(shrunk, *CAP)), 4)
    json.dump(tempo, open(os.path.join(DATA, "tempo.json"), "w"))
    print(f"tempo from {n} WC26 matches:",
          {s: tempo[s] for s in ["goals", "corners", "shots", "fouls", "yellows"]})

if __name__ == "__main__":
    main()
