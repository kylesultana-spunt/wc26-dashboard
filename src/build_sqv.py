"""Build squad-value index Q(country, year) from Transfermarkt valuations.
Q = log10(sum of the country's top-23 player values at June 1 of that year)."""
import os
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# TM citizenship name -> results_all team name (only mismatches)
ALIAS = {"United States": "United States", "Korea, South": "South Korea",
         "Cote d'Ivoire": "Ivory Coast", "DR Congo": "DR Congo",
         "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Cape Verde": "Cape Verde",
         "Curacao": "Curaçao", "St. Kitts & Nevis": "Saint Kitts and Nevis",
         "Trinidad and Tobago": "Trinidad and Tobago", "Czech Republic": "Czech Republic"}

def main():
    p = pd.read_csv(os.path.join(DATA, "tm", "players.csv"),
                    usecols=["player_id", "country_of_citizenship"])
    v = pd.read_csv(os.path.join(DATA, "tm", "player_valuations.csv"),
                    usecols=["player_id", "date", "market_value_in_eur"])
    v["date"] = pd.to_datetime(v["date"])
    df = v.merge(p, on="player_id").dropna(subset=["country_of_citizenship",
                                                   "market_value_in_eur"])
    rows = []
    for year in range(2012, 2027):
        asof = pd.Timestamp(f"{year}-06-01")
        sub = df[(df.date <= asof) & (df.date >= asof - pd.Timedelta(days=550))]
        last = sub.sort_values("date").groupby("player_id").tail(1)
        for country, g in last.groupby("country_of_citizenship"):
            top = g.market_value_in_eur.nlargest(23)
            total = top.sum() + 1e5  # floor avoids log(0) for micro-nations
            rows.append({"team": ALIAS.get(country, country), "year": year,
                         "q": round(float(np.log10(total)), 4),
                         "n_players": len(top)})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DATA, "squad_values.csv"), index=False)
    print(f"{len(out)} country-years written")
    chk = out[out.year == 2026].set_index("team")
    for t in ["Germany", "England", "Ghana", "Panama", "Haiti", "Curaçao", "Scotland", "Japan"]:
        if t in chk.index:
            r = chk.loc[t]
            print(f"  {t:12s} 2026: Q={r.q:.2f} (€{10**r.q/1e6:,.0f}M, {r.n_players} players)")

if __name__ == "__main__":
    main()
