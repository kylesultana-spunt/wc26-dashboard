"""Fetch the current 26-man WC26 squads from ESPN (fallback: API-Football) so the model's
player pool only contains players who are actually in the tournament — dropping retired or
cut players (e.g. Giroud) that linger in the historical appearance data.

Writes data/squads.json: { "France": [{"name": "...", "pos": "M"}, ...], ... }
Run in CI before export_dashboard; safe to re-run (overwrites). No key needed for ESPN.
"""
import os, json, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                timeout=25) as r:
        return json.load(r)


def run():
    try:
        tj = _get(f"{ESPN}/teams?limit=100")
        teams = tj["sports"][0]["leagues"][0]["teams"]
    except Exception as e:
        print(f"build_squads: could not list teams ({e}); leaving squads.json untouched")
        return
    squads = {}
    for t in teams:
        team = t["team"]
        name, tid = team.get("displayName"), team.get("id")
        try:
            r = _get(f"{ESPN}/teams/{tid}/roster")
            ath = r.get("athletes", [])
            roster = []
            for a in ath:
                nm = a.get("displayName") or a.get("fullName")
                pos = (a.get("position") or {}).get("abbreviation") or \
                      (a.get("position") or {}).get("name", "")
                if nm:
                    roster.append({"name": nm, "pos": pos})
            if roster:
                squads[name] = roster
                print(f"  {name}: {len(roster)}")
        except Exception as e:
            print(f"  {name}: roster failed ({e})")
        time.sleep(0.15)
    if squads:
        json.dump(squads, open(os.path.join(DATA, "squads.json"), "w"), ensure_ascii=False)
        print(f"build_squads: wrote {len(squads)} squads")
    else:
        print("build_squads: no squads fetched; squads.json untouched")


if __name__ == "__main__":
    run()
