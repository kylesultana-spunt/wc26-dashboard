"""Build club per-90 rates (cards/goals/assists) from TM appearances -> data/club_rates.csv
Validated 2026-06-13: blend weight 0.25 improves booking Brier on 10.5k held-out intl apps."""
import os, unicodedata
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").split())

def main():
    a = pd.read_csv(os.path.join(DATA, "tm", "appearances.csv"),
                    usecols=["player_name", "date", "yellow_cards", "red_cards",
                             "goals", "assists", "minutes_played"])
    a = a[(a.date >= "2024-01-01") & (a.minutes_played > 0)]
    a["nname"] = a.player_name.map(norm)
    g = a.groupby("nname").agg(mins=("minutes_played", "sum"),
                               yc=("yellow_cards", "sum"), gl=("goals", "sum"),
                               asst=("assists", "sum")).reset_index()
    g = g[g.mins >= 450]
    for src, dst in (("yc", "club_yc90"), ("gl", "club_g90"), ("asst", "club_a90")):
        g[dst] = (g[src] / g.mins * 90).round(4)
    g[["nname", "mins", "club_yc90", "club_g90", "club_a90"]].to_csv(
        os.path.join(DATA, "club_rates.csv"), index=False)
    print(f"club_rates.csv: {len(g)} players")

if __name__ == "__main__":
    main()
