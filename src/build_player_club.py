"""Pull each squad player's CLUB-level per-game stats from ESPN's gamelog so the model's
fouls/shots/SoT rates rest on a player's full club season (30-50 games), not just the
handful of national-team appearances. Fixes the Olise/Sorloth granularity gap.

Reads data/squads.json (needs player ids from build_squads.py), writes
data/player_club_rates.csv:
  team,player,nname,games,fc_pg,fa_pg,shots_pg,sot_pg,yc_pg

ESPN gamelog stat order (names): totalGoals, goalAssists, totalShots, shotsOnTarget,
foulsCommitted, foulsSuffered, offsides, yellowCards, redCards. No minutes are given, so
rates are per appearance (fine for starters, who are what the lineup tilt uses).
Run occasionally (club stats move slowly); commit the CSV. ESPN, no key.
"""
import os, json, time, csv, unicodedata
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
GL = "https://site.web.api.espn.com/apis/common/v3/sports/soccer/all/athletes/{}/gamelog"
IDX = {"shots": 2, "sot": 3, "fc": 4, "fa": 5, "yc": 7}   # positions in the stats array


def _nname(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").split())


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                timeout=20) as r:
        return json.load(r)


def player_rates(pid):
    """Aggregate club games from the gamelog into per-appearance rates."""
    j = _get(GL.format(pid))
    tot = {k: 0.0 for k in IDX}
    games = 0
    for st in j.get("seasonTypes", []) or []:
        for cat in st.get("categories", []) or []:
            for ev in cat.get("events", []) or []:
                s = ev.get("stats")
                if not s or len(s) < 9:
                    continue
                try:
                    for k, i in IDX.items():
                        tot[k] += float(s[i])
                    games += 1
                except (ValueError, TypeError):
                    continue
    if games == 0:
        return None
    return {"games": games, "fc_pg": tot["fc"] / games, "fa_pg": tot["fa"] / games,
            "shots_pg": tot["shots"] / games, "sot_pg": tot["sot"] / games,
            "yc_pg": tot["yc"] / games}


def run():
    sq_path = os.path.join(DATA, "squads.json")
    if not os.path.exists(sq_path):
        print("build_player_club: squads.json missing — run build_squads.py first")
        return
    squads = json.load(open(sq_path))
    rows, done, miss = [], 0, 0
    for team, roster in squads.items():
        for pl in roster:
            pid = pl.get("id")
            if not pid:
                continue
            try:
                r = player_rates(pid)
            except Exception:
                r = None
            if not r:
                miss += 1
                continue
            rows.append({"team": team, "player": pl["name"], "nname": _nname(pl["name"]),
                         **{k: round(v, 4) for k, v in r.items()}})
            done += 1
            time.sleep(0.05)
    if rows:
        with open(os.path.join(DATA, "player_club_rates.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["team", "player", "nname", "games",
                                              "fc_pg", "fa_pg", "shots_pg", "sot_pg", "yc_pg"])
            w.writeheader(); w.writerows(rows)
        print(f"build_player_club: wrote {done} players ({miss} without gamelog)")
    else:
        print("build_player_club: no rows (check squad ids)")


if __name__ == "__main__":
    run()
