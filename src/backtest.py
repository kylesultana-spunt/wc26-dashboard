"""Backtest market probabilities on held-out tournaments (calibration check)."""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models

DATA = models.DATA

HOLDOUTS = [
    ("uefa.euro", "2024-06-01", "2024-08-01"),
    ("conmebol.america", "2024-06-01", "2024-08-01"),
    ("fifa.world", "2022-11-01", "2023-01-01"),  # goals only (no prior stat data)
]

def outcome_value(row_h, row_a, key, home, away):
    """Actual 0/1 outcome for a market key, or None if stat missing."""
    def tot(stat):
        a, b = row_h.get(f"{stat}_for"), row_a.get(f"{stat}_for")
        return None if (pd.isna(a) or pd.isna(b)) else a + b
    if key.startswith("goals_over_") or key.startswith("goals_under_"):
        t = tot("goals"); line = float(key.split("_")[-1])
        if t is None: return None
        return int(t > line) if "over" in key else int(t < line)
    if key == "btts_yes":
        return int(row_h["goals_for"] > 0 and row_a["goals_for"] > 0)
    if key == "btts_no":
        return int(not (row_h["goals_for"] > 0 and row_a["goals_for"] > 0))
    if key.startswith("corners_"):
        t = tot("corners"); line = float(key.split("_")[-1])
        if t is None: return None
        return int(t > line) if "over" in key else int(t < line)
    if key.startswith("cards_"):
        ch = row_h.get("yellows_for"); ca = row_a.get("yellows_for")
        rh = row_h.get("reds_for") or 0; ra = row_a.get("reds_for") or 0
        if pd.isna(ch) or pd.isna(ca): return None
        t = ch + ca + rh + ra; line = float(key.split("_")[-1])
        return int(t > line) if "over" in key else int(t < line)
    if key.startswith("fouls_"):
        t = tot("fouls"); line = float(key.split("_")[-1])
        if t is None: return None
        return int(t > line) if "over" in key else int(t < line)
    if key.startswith("team_") and "range" not in key:
        parts = key.split("_")
        stat = parts[1]  # corners/goals/cards/shots/sot
        line = float(parts[-1])
        team = "_".join(parts[2:-2])
        row = row_h if team == home else row_a
        col = {"corners": "corners_for", "goals": "goals_for", "shots": "shots_for",
               "sot": "sot_for"}.get(stat)
        if stat == "cards":
            v = (row.get("yellows_for") or np.nan)
            if pd.isna(v): return None
            v = v + (row.get("reds_for") or 0)
        else:
            v = row.get(col)
            if v is None or pd.isna(v): return None
        return int(v > line)
    # ---- extended menu ----
    gh, ga = row_h["goals_for"], row_a["goals_for"]
    def safe(row, col):
        v = row.get(col)
        return None if v is None or pd.isna(v) else v
    if key.startswith("result_"):
        t = key[7:]
        return int(gh > ga) if t == home else int(ga > gh) if t == away else int(gh == ga)
    if key.startswith("double_chance_"):
        rest = key[14:]
        if rest == f"{home}_draw": return int(gh >= ga)
        if rest == f"{away}_draw": return int(ga >= gh)
        return int(gh != ga)
    if key.startswith("dnb_"):
        if gh == ga: return None  # void
        return int(gh > ga) if key[4:] == home else int(ga > gh)
    if key.startswith("win_margin_"):
        rest = key[11:]
        t, m = rest.rsplit("_", 1)
        diff = (gh - ga) if t == home else (ga - gh)
        return int(diff >= 3) if m == "3plus" else int(diff == float(m))
    if key.startswith("score_"):
        i, j = map(int, key.split("_")[1:])
        return int(gh == i and ga == j)
    if key == "goals_4plus": return int(gh + ga >= 4)
    if key.startswith("goals_range_"):
        lo, hi = map(int, key.split("_")[2:])
        return int(lo <= gh + ga <= hi)
    if key.startswith("team_goals_range_"):
        rest = key[len("team_goals_range_"):]
        t, rng = rest.rsplit("_", 2)[0], rest.split("_")[-2:]
        g = gh if t == home else ga
        return int(g <= 1) if "0" in rng[0] else int(g >= 2)
    g1h, g1a = safe(row_h, "goals_1h_for"), safe(row_a, "goals_1h_for")
    c1h, c1a = safe(row_h, "cards_1h_for"), safe(row_a, "cards_1h_for")
    if key.startswith(("goals_1h_", "goals_2h_", "goal_both", "half_most", "ht_score", "htft")):
        if g1h is None or g1a is None: return None
        h1 = g1h + g1a; h2 = gh + ga - h1
        if key.startswith("goals_1h_"):
            line = float(key.split("_")[-1])
            return int(h1 > line) if "over" in key else int(h1 < line)
        if key.startswith("goals_2h_"):
            line = float(key.split("_")[-1])
            return int(h2 > line)
        if key == "goal_both_halves": return int(h1 > 0 and h2 > 0)
        if key == "half_most_goals_1h": return int(h1 > h2)
        if key == "half_most_goals_2h": return int(h2 > h1)
        if key == "half_most_goals_tie": return int(h1 == h2)
        if key.startswith("ht_score_"):
            i, j = map(int, key.split("_")[2:])
            return int(g1h == i and g1a == j)
        if key.startswith("htft_"):
            code = key[5:]
            htmap = {"H": g1h > g1a, "D": g1h == g1a, "A": g1h < g1a}
            ftmap = {"H": gh > ga, "D": gh == ga, "A": gh < ga}
            return int(htmap[code[0]] and ftmap[code[1]])
    if key.startswith("cards_1h_"):
        if c1h is None or c1a is None: return None
        line = float(key.split("_")[-1])
        t = c1h + c1a
        return int(t > line) if "over" in key else int(t < line)
    ch, ca = safe(row_h, "corners_for"), safe(row_a, "corners_for")
    if key.startswith(("corners_3w_", "most_corners")):
        if ch is None or ca is None: return None
        if key.startswith("corners_3w_"):
            n = int(key.split("_")[-1]); t = ch + ca
            return int(t > n) if "over" in key else int(t == n) if "exactly" in key else int(t < n)
        if key == f"most_corners_{home}": return int(ch > ca)
        if key == f"most_corners_{away}": return int(ca > ch)
        return int(ch == ca)
    yh, ya = safe(row_h, "yellows_for"), safe(row_a, "yellows_for")
    if key.startswith(("btt_cards", "most_cards", "red_card")):
        if yh is None or ya is None: return None
        th = yh + (safe(row_h, "reds_for") or 0); ta = ya + (safe(row_a, "reds_for") or 0)
        if key == "btt_cards_yes": return int(th > 0 and ta > 0)
        if key == "btt_cards_no": return int(not (th > 0 and ta > 0))
        if key == f"most_cards_{home}": return int(th > ta)
        if key == f"most_cards_{away}": return int(ta > th)
        if key == "most_cards_tie": return int(th == ta)
        r = (safe(row_h, "reds_for") or 0) + (safe(row_a, "reds_for") or 0)
        return int(r > 0) if key == "red_card_yes" else int(r == 0)
    for fam, col in (("offsides", "offsides_for"), ("tackles", "tackles_for"),
                     ("shots", "shots_for"), ("sot", "sot_for")):
        if key.startswith(f"{fam}_over_") or key.startswith(f"{fam}_under_"):
            a, b = safe(row_h, col), safe(row_a, col)
            if a is None or b is None: return None
            line = float(key.split("_")[-1]); t = a + b
            return int(t > line) if "over" in key else int(t < line)
    if key.startswith("gk_saves_"):
        rest = key[len("gk_saves_"):]
        t = rest.rsplit("_over_", 1)[0]; line = float(rest.rsplit("_over_", 1)[1])
        v = safe(row_h if t == home else row_a, "saves_for")
        if v is None: return None
        return int(v > line)
    return None

def run():
    t_all = pd.read_csv(os.path.join(DATA, "team_matches.csv"))
    refs = pd.read_csv(os.path.join(DATA, "referee_matches.csv"))
    ref_by_event = dict(zip(refs.event_id.astype(str), refs.referee))
    records = []
    for comp, start, end in HOLDOUTS:
        mm = models.MatchModel(asof=start)
        sub = t_all[(t_all.comp == comp) & (t_all.date >= start) & (t_all.date < end)]
        fixtures = sub[sub.home_away == "home"]
        goals_only = comp == "fifa.world"
        for fx in fixtures.itertuples():
            home, away = fx.team, fx.opponent
            row_h = fx._asdict()
            ra = sub[(sub.event_id == fx.event_id) & (sub.home_away == "away")]
            if len(ra) != 1: continue
            row_a = ra.iloc[0].to_dict()
            ref = ref_by_event.get(str(fx.event_id))
            stage = "group"
            _, sims = mm.simulate(home, away, ref=ref, stage=stage)
            probs = models.market_probs(sims, home, away)
            GOALY = ("goals", "btts", "team_goals", "result", "double_chance", "dnb",
                     "win_margin", "score_", "ht_score", "htft", "goal_both", "half_most")
            for k, p in probs.items():
                if goals_only and not any(k.startswith(x) or x in k for x in GOALY):
                    continue
                y = outcome_value(row_h, row_a, k, home, away)
                if y is None: continue
                fam = ("result" if any(k.startswith(x) for x in
                       ("result", "double_chance", "dnb", "win_margin", "score_",
                        "ht_score", "htft", "half_most")) else
                       "goals" if "goals" in k or "btts" in k or "goal_both" in k else
                       "corners" if "corners" in k else
                       "cards" if "cards" in k else
                       "offsides" if "offsides" in k else
                       "tackles" if "tackles" in k else
                       "saves" if "saves" in k else
                       "shots" if "shots" in k or "sot" in k else "fouls")
                records.append({"comp": comp, "market": k, "family": fam, "p": p, "y": y})
    df = pd.DataFrame(records)
    df.to_csv(os.path.join(DATA, "backtest_results.csv"), index=False)
    print(f"{len(df)} market predictions across holdouts\n")
    print("== Brier score by family (lower better; naive-0.5 baseline = 0.25) ==")
    fam = df.groupby("family").apply(
        lambda g: pd.Series({"brier": ((g.p - g.y) ** 2).mean(),
                             "base_rate_brier": ((g.y.mean() - g.y) ** 2).mean(),
                             "n": len(g)}), include_groups=False)
    print(fam.round(4).to_string())
    print("\n== Calibration in the betting zone ==")
    for lo, hi in [(0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]:
        z = df[(df.p >= lo) & (df.p < hi)]
        if len(z):
            print(f"model {lo:.0%}-{hi:.0%}: actual hit rate {z.y.mean():.1%}  (n={len(z)})")
    print("\n== The actual bet rule: p>=0.72 ==")
    z = df[df.p >= 0.72]
    print(f"flagged {len(z)}: hit rate {z.y.mean():.1%}")
    for f, g in z.groupby("family"):
        print(f"  {f}: {g.y.mean():.1%} (n={len(g)})")

if __name__ == "__main__":
    run()
