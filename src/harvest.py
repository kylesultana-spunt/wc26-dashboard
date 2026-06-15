"""Harvest international match data (team + player stats) from ESPN's public JSON API."""
import json, os, time, sys, csv
import urllib.request

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
RAW = os.path.join(DATA, "raw")
os.makedirs(RAW, exist_ok=True)

COMPS = [
    "fifa.world", "fifa.worldq.uefa", "fifa.worldq.conmebol", "fifa.worldq.concacaf",
    "fifa.worldq.afc", "fifa.worldq.caf", "fifa.worldq.ofc",
    "uefa.euro", "uefa.nations", "conmebol.america", "concacaf.gold",
    "concacaf.nations.league", "caf.nations", "afc.asian", "fifa.friendly",
]
CHUNKS = [
    "20220601-20221231", "20230101-20230630", "20230701-20231231",
    "20240101-20240630", "20240701-20241231", "20250101-20250630",
    "20250701-20251231", "20260101-20260715",
]

def get(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            if i == retries - 1:
                print(f"FAIL {url}: {e}", flush=True)
                return None
            time.sleep(2 * (i + 1))

def collect_events():
    from concurrent.futures import ThreadPoolExecutor
    events = {}  # id -> (comp, date, name)
    jobs = [(comp, chunk) for comp in COMPS for chunk in CHUNKS]
    def fetch(job):
        comp, chunk = job
        return comp, get(f"{BASE}/{comp}/scoreboard?dates={chunk}&limit=400", retries=2)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for comp, d in ex.map(fetch, jobs):
            if not d:
                continue
            for e in d.get("events", []):
                st = e.get("status", {}).get("type", {}).get("state")
                if st == "post":  # completed only
                    events[e["id"]] = (comp, e.get("date", ""), e.get("name", ""))
    print(f"index: {len(events)} events", flush=True)
    with open(os.path.join(DATA, "events_index.json"), "w") as f:
        json.dump(events, f)
    return events

def stat_map(stats):
    return {s["name"]: s.get("displayValue") for s in stats}

def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def parse_summary(eid, comp, date, d, team_rows, player_rows):
    bs = d.get("boxscore", {})
    teams = bs.get("teams", [])
    if len(teams) != 2:
        return
    comps = d.get("header", {}).get("competitions", [{}])[0].get("competitors", [])
    score = {c.get("homeAway"): num(c.get("score")) for c in comps}
    sides = {}
    for t in teams:
        ha = t.get("homeAway")
        sides[ha] = {"team": t.get("team", {}).get("displayName"),
                     "id": t.get("team", {}).get("id"), **stat_map(t.get("statistics", []))}
    if "home" not in sides or "away" not in sides:
        return
    # first-half goals/cards per team from keyEvents
    fh = {sides["home"]["team"]: {"g": 0, "c": 0}, sides["away"]["team"]: {"g": 0, "c": 0}}
    for ev in d.get("keyEvents", []):
        txt = (ev.get("type", {}).get("text", "") or "").lower()
        if ev.get("period", {}).get("number") != 1:
            continue
        tm = ev.get("team", {}).get("displayName")
        if tm not in fh:
            continue
        if "own goal" in txt:
            other = [t for t in fh if t != tm][0]
            fh[other]["g"] += 1
        elif ("goal" in txt and "kick" not in txt) or txt == "penalty - scored":
            fh[tm]["g"] += 1
        elif "card" in txt:
            fh[tm]["c"] += 1
    # substitution minutes from keyEvents
    sub_in, sub_out = {}, {}
    for ev in d.get("keyEvents", []):
        if "substitution" in (ev.get("type", {}).get("text", "") or "").lower():
            clock = num((ev.get("clock", {}).get("displayValue") or "0'").replace("'", "").split("+")[0])
            aths = ev.get("participants") or []
            for i, a in enumerate(aths):
                aid = a.get("athlete", {}).get("id")
                if aid is None:
                    continue
                # ESPN convention: first participant on, second off (varies; store both)
                (sub_in if i == 0 else sub_out)[aid] = clock
    for ha, opp_ha in (("home", "away"), ("away", "home")):
        s, o = sides[ha], sides[opp_ha]
        team_rows.append({
            "event_id": eid, "comp": comp, "date": date[:10], "team": s["team"],
            "opponent": o["team"], "home_away": ha,
            "goals_for": score.get(ha), "goals_against": score.get(opp_ha),
            "corners_for": num(s.get("wonCorners")), "corners_against": num(o.get("wonCorners")),
            "yellows_for": num(s.get("yellowCards")), "yellows_against": num(o.get("yellowCards")),
            "reds_for": num(s.get("redCards")), "reds_against": num(o.get("redCards")),
            "fouls_for": num(s.get("foulsCommitted")), "fouls_against": num(o.get("foulsCommitted")),
            "shots_for": num(s.get("totalShots")), "shots_against": num(o.get("totalShots")),
            "sot_for": num(s.get("shotsOnTarget")), "sot_against": num(o.get("shotsOnTarget")),
            "offsides_for": num(s.get("offsides")), "offsides_against": num(o.get("offsides")),
            "tackles_for": num(s.get("totalTackles")), "tackles_against": num(o.get("totalTackles")),
            "saves_for": num(s.get("saves")), "saves_against": num(o.get("saves")),
            "goals_1h_for": fh[s["team"]]["g"] if d.get("keyEvents") else None,
            "cards_1h_for": fh[s["team"]]["c"] if d.get("keyEvents") else None,
            "possession": num(s.get("possessionPct")),
        })
    for ros in d.get("rosters", []):
        tname = ros.get("team", {}).get("displayName")
        opp = sides["away"]["team"] if tname == sides["home"]["team"] else sides["home"]["team"]
        for r in ros.get("roster", []):
            ath = r.get("athlete", {})
            st = {s["name"]: num(s.get("value")) for s in r.get("stats", [])}
            if not st:
                continue
            starter = bool(r.get("starter"))
            aid = ath.get("id")
            mins = 90.0
            if starter and aid in sub_out:
                mins = sub_out[aid]
            elif not starter and aid in sub_in:
                mins = max(0.0, 90.0 - sub_in[aid])
            elif not starter:
                mins = 0.0
            if mins == 0 and not st.get("appearances"):
                continue
            player_rows.append({
                "event_id": eid, "comp": comp, "date": date[:10], "team": tname,
                "opponent": opp, "player": ath.get("displayName"), "player_id": aid,
                "position": (r.get("position", {}) or {}).get("abbreviation"),
                "starter": starter, "minutes_est": mins,
                "shots": st.get("totalShots"), "sot": st.get("shotsOnTarget"),
                "goals": st.get("totalGoals"), "assists": st.get("goalAssists"),
                "saves": st.get("saves"), "fouls_committed": st.get("foulsCommitted"),
                "fouls_suffered": st.get("foulsSuffered"),
                "yellows": st.get("yellowCards"), "reds": st.get("redCards"),
            })

def main():
    args = [x for x in sys.argv[1:] if x != "refresh"]
    budget = float(args[0]) if args else 35.0
    t0 = time.time()
    idx_path = os.path.join(DATA, "events_index.json")
    if "refresh" in sys.argv:
        events = collect_events()  # re-scan for newly completed matches
    elif os.path.exists(idx_path):
        events = json.load(open(idx_path))
    else:
        events = collect_events()
    missing = [eid for eid in events if not os.path.exists(os.path.join(RAW, f"{eid}.json"))]
    print(f"{len(events)} events, {len(missing)} to fetch", flush=True)
    from concurrent.futures import ThreadPoolExecutor
    def fetch(eid):
        comp = events[eid][0]
        d = get(f"{BASE}/{comp}/summary?event={eid}", retries=2)
        if d:
            json.dump(d, open(os.path.join(RAW, f"{eid}.json"), "w"))
        return eid
    fetched = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        batch = []
        for eid in missing:
            if time.time() - t0 > budget:
                break
            batch.append(ex.submit(fetch, eid))
            if len(batch) >= 40:
                for f in batch: f.result()
                fetched += len(batch); batch = []
        for f in batch: f.result()
        fetched += len(batch)
    remaining = sum(1 for eid in events if not os.path.exists(os.path.join(RAW, f"{eid}.json")))
    if remaining:
        print(f"PARTIAL: fetched {fetched} this run, {remaining} remaining", flush=True)
        return
    # all cached -> parse everything
    team_rows, player_rows = [], []
    for eid, (comp, date, name) in events.items():
        try:
            d = json.load(open(os.path.join(RAW, f"{eid}.json")))
            parse_summary(eid, comp, date, d, team_rows, player_rows)
        except Exception as e:
            print(f"parse fail {eid}: {e}", flush=True)
    for fname, rows in (("team_matches.csv", team_rows), ("player_matches.csv", player_rows)):
        if rows:
            with open(os.path.join(DATA, fname), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    print(f"DONE: {len(team_rows)} team rows, {len(player_rows)} player rows", flush=True)

if __name__ == "__main__":
    main()
