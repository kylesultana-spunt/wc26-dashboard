"""Does blending club card rates improve booking prediction on held-out internationals?
Fit window: data before 2025-07-01. Holdout: international apps 2025-07-01 onward."""
import os, sys, unicodedata
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CUT = "2025-07-01"

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").split())

def main():
    # club rates from TM appearances before cutoff (last 2 seasons for recency)
    a = pd.read_csv(os.path.join(DATA, "tm", "appearances.csv"),
                    usecols=["player_id", "player_name", "date", "yellow_cards",
                             "red_cards", "minutes_played"])
    a = a[(a.date >= "2023-07-01") & (a.date < CUT) & (a.minutes_played > 0)]
    club = a.groupby(["player_id", "player_name"]).agg(
        mins=("minutes_played", "sum"), yc=("yellow_cards", "sum")).reset_index()
    club = club[club.mins >= 450]  # at least ~5 club games
    club["club_yc90"] = club.yc / club.mins * 90
    club["nname"] = club.player_name.map(norm)
    club = club.sort_values("mins", ascending=False).drop_duplicates("nname")
    club_map = dict(zip(club.nname, zip(club.club_yc90, club.mins)))
    print(f"club rates: {len(club)} players (>=450 club mins)")

    # international data
    p = pd.read_csv(os.path.join(DATA, "player_matches.csv"))
    p["date"] = pd.to_datetime(p["date"])
    p = p[p.minutes_est > 0]
    p["nname"] = p.player.map(norm)
    fit = p[p.date < CUT]
    hold = p[(p.date >= CUT) & (p.minutes_est >= 30)]
    print(f"holdout: {len(hold)} international appearances since {CUT}")
    # intl per-90 yc rates from fit window
    g = fit.groupby("nname").agg(im=("minutes_est", "sum"), iy=("yellows", "sum"))
    intl = {n: (r.iy / r.im * 90, r.im) for n, r in g.iterrows()}
    PRIOR = fit.yellows.sum() / fit.minutes_est.sum() * 90  # league avg yc/90
    K = 540.0  # prior weight in minutes (~6 games)

    matched = hold.nname.isin(club_map).mean()
    print(f"name match rate on holdout players: {matched:.0%}")

    def brier(use_club, w_club):
        se, n = 0.0, 0
        for r in hold.itertuples():
            ir, im = intl.get(r.nname, (PRIOR, 0.0))
            num, den = ir * im + PRIOR * K, im + K
            if use_club and r.nname in club_map:
                cr, cm = club_map[r.nname]
                num += w_club * cm * cr
                den += w_club * cm
            rate = num / den
            prob = 1 - np.exp(-rate * r.minutes_est / 90)
            y = 1.0 if (r.yellows or 0) > 0 else 0.0
            se += (prob - y) ** 2; n += 1
        return se / n

    b0 = brier(False, 0)
    print(f"\nINTL-ONLY (current model):   Brier {b0:.5f}")
    for w in [0.25, 0.5, 1.0]:
        print(f"with club blend (w={w}):      Brier {brier(True, w):.5f}")

if __name__ == "__main__":
    main()
