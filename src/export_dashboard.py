"""Export fitted model + fixtures + squads into a self-contained dashboard.html."""
import json, os, sys, urllib.request
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "dashboard.html")

def get_fixtures():
    url = ("https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/"
           "scoreboard?dates=20260611-20260720&limit=200")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=25))
    fixtures, teams = [], set()
    SKIP = ("Winner", "Place", "Group", "Loser", "Third", "Quarterfinal", "Semifinal", "Round of")
    for e in d.get("events", []):
        comp = e.get("competitions", [{}])[0]
        cs = comp.get("competitors", [])
        if len(cs) != 2:
            continue
        names = {c.get("homeAway"): c.get("team", {}).get("displayName") for c in cs}
        h, a = names.get("home"), names.get("away")
        real = [x for x in (h, a) if x and not any(s in x for s in SKIP)]
        teams.update(real)
        if h and a and len(real) == 2:
            _dt = e.get("date", "")
            try:
                _dt = pd.Timestamp(_dt).tz_convert("Europe/Malta").strftime("%Y-%m-%d %H:%M")
            except Exception:
                _dt = _dt[:16].replace("T", " ")
            fixtures.append({"date": _dt,
                             "home": h, "away": a, "eid": e.get("id"),
                             "done": e.get("status", {}).get("type", {}).get("state") == "post"})
    return sorted(fixtures, key=lambda f: f["date"]), sorted(teams)

def main():
    print("fitting model...", flush=True)
    mm = models.MatchModel()
    ts, rs = mm.ts, mm.rs
    fixtures, teams = get_fixtures()
    print(f"{len(fixtures)} fixtures, {len(teams)} teams", flush=True)

    EXPORT_STATS = ["goals", "corners", "yellows", "reds", "fouls", "shots", "sot",
                    "offsides", "saves"]
    team_data = {}
    REC_STATS = ["goals", "corners", "yellows", "reds", "fouls", "shots", "sot", "offsides", "saves"]
    for t in teams:
        rows = ts.t[(ts.t.team == t)].dropna(subset=["possession"])
        poss = (float(np.average(rows.possession, weights=rows.w))
                if len(rows) else 50.0)
        # last-10 raw values per stat (newest first) for evidence bullets
        recent = {}
        trows = ts.t[ts.t.team == t].sort_values("date", ascending=False)
        for s in REC_STATS:
            d = trows.dropna(subset=[f"{s}_for"]).head(10)
            recent[s] = {"f": [int(x) for x in d[f"{s}_for"]],
                         "a": [int(x) for x in d[f"{s}_against"].fillna(0)]}
        qv = models.squad_q().get((models.to_results_name(t), 2026))
        team_data[t] = {
            "q": round(qv, 3) if qv is not None else None,
            "elo": mm.elo.get(models.to_results_name(t), 1500),
            "f": {s: [round(ts.factor(t, s, "for")[0], 4),
                      round(ts.factor(t, s, "against")[0], 4)] for s in EXPORT_STATS},
            "n": int((ts.t.team == t).sum()),
            "poss": round(poss, 1),
            "rec": recent,
        }

    refs = []
    for name, g in rs.r.groupby("referee"):
        if not name or len(g) < 1:
            continue
        mult, n = rs.multiplier(name)
        refs.append({"name": name, "mult": round(mult, 3), "n": int(n)})
    refs.sort(key=lambda r: r["name"])
    ref_by_event = dict(zip(rs.r.event_id.astype(str), rs.r.referee))
    import datetime as _dt
    _today = _dt.date.today()
    for f in fixtures:
        rname = ref_by_event.get(str(f.get("eid")))
        if not rname and not f["done"]:
            try:
                fd = _dt.date.fromisoformat(f["date"][:10])
                if 0 <= (fd - _today).days <= 5:   # appointed refs show ~1-2 days out; check 5
                    jd = json.load(urllib.request.urlopen(urllib.request.Request(
                        f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={f['eid']}",
                        headers={"User-Agent": "Mozilla/5.0"}), timeout=15))
                    offs = jd.get("gameInfo", {}).get("officials", []) or []
                    rname = next((o.get("fullName") for o in offs
                                  if o.get("position", {}).get("name") == "Referee"), None)
            except Exception:
                pass
        f["ref"] = rname or ""
    json.dump(fixtures, open(os.path.join(models.DATA, "fixtures.json"), "w"))  # change here = schedule/ref update -> triggers redeploy

    # players: fast vectorised per-90 with shrinkage to position mean
    p = pd.read_csv(os.path.join(models.DATA, "player_matches.csv"))
    p["date"] = pd.to_datetime(p["date"])
    p = p[(p.minutes_est > 0) & (p.team.isin(teams))]
    p["w"] = p["comp"].map(models.COMP_W).fillna(1.0) * models._decay(
        p["date"], pd.Timestamp.now().strftime("%Y-%m-%d"))
    PSTATS = ["shots", "sot", "goals", "assists", "fouls_committed",
              "fouls_suffered", "yellows", "saves"]
    pos_prior = {}
    for s in PSTATS:
        per90 = p[s].fillna(0) / p.minutes_est * 90
        pos_prior[s] = per90.groupby(p.position.fillna("?")).mean().to_dict()
        pos_prior[s]["_all"] = float(per90.mean())
    players = {}
    K = 6.0
    import unicodedata as _ud
    def _nn(s):
        s = _ud.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
        return " ".join(s.replace("-", " ").split())
    cpath = os.path.join(models.DATA, "club_rates.csv")
    club = pd.read_csv(cpath).set_index("nname") if os.path.exists(cpath) else None
    CLUB_COL = {"yellows": "club_yc90", "goals": "club_g90", "assists": "club_a90"}
    CLUB_W = 0.25  # validated blend weight
    for (team, name), g in p.groupby(["team", "player"]):
        if g.date.max() < pd.Timestamp("2024-06-01") or len(g) < 2:
            continue
        pos = g.position.mode().iloc[0] if g.position.notna().any() else "?"
        eff = (g.w * g.minutes_est / 90)
        n_eff = eff.sum()
        rec = {"pos": pos, "n": int(len(g)),
               "min": round(float(g[g.starter].minutes_est.mean()
                                  if g.starter.any() else 60.0), 1)}
        crow = club.loc[_nn(name)] if (club is not None and _nn(name) in club.index) else None
        for s in PSTATS:
            r90 = (g[s].fillna(0) / g.minutes_est * 90)
            rate = float(np.average(r90, weights=eff)) if n_eff > 0 else 0.0
            prior = pos_prior[s].get(pos, pos_prior[s]["_all"])
            num, den = n_eff * rate, n_eff
            if crow is not None and s in CLUB_COL:
                ce = CLUB_W * float(crow["mins"]) / 90.0
                num += ce * float(crow[CLUB_COL[s]])
                den += ce
            rec[s] = round((num + K * prior) / (den + K), 4)
        players.setdefault(team, {})[name] = rec
    for t in players:  # cap squad lists
        top = sorted(players[t].items(), key=lambda kv: -kv[1]["n"])[:45]
        players[t] = dict(top)

    book_out = {}  # odds feed + oddschecker integration removed
    # ---- review of completed fixtures: model (as of kickoff) vs reality ----
    cal = json.load(open(os.path.join(models.DATA, "calibration.json")))
    def _cal(p, key=None):
        p = min(max(p, 1e-4), 1 - 1e-4)
        lp = np.log(p / (1 - p))
        c = (cal.get("fam", {}).get(models.market_family(key)) if key else None) or cal
        return float(min(1 / (1 + np.exp(-(c["a"] + c["b"] * lp))), 0.93))
    _bak = os.path.join(models.DATA, "calibration.json.global.bak")
    cal_v1 = json.load(open(_bak)) if os.path.exists(_bak) else cal   # previous model version
    def _cal_v1(p, key=None):
        p = min(max(p, 1e-4), 1 - 1e-4); lp = np.log(p / (1 - p))
        c = (cal_v1.get("fam", {}).get(models.market_family(key)) if key else None) or cal_v1
        return float(min(1 / (1 + np.exp(-(c["a"] + c["b"] * lp))), 0.93))
    import backtest as _bt
    rcache_path = os.path.join(models.DATA, "review_cache_v2.json")
    rcache = json.load(open(rcache_path)) if os.path.exists(rcache_path) else {}
    tm_all = pd.read_csv(os.path.join(models.DATA, "team_matches.csv"))
    tm_all = tm_all[tm_all.comp == "fifa.world"]
    import review_tips
    pm_all = pd.read_csv(os.path.join(models.DATA, "player_matches.csv"))
    done = [f for f in fixtures if f["done"]]
    by_date = {}
    for f in done:
        fid = f"{f['date'][:10]}|{f['home']}|{f['away']}"
        if fid not in rcache:
            by_date.setdefault(f["date"][:10], []).append(f)
    for d, fs in sorted(by_date.items()):
        try:
            mmp = models.MatchModel(asof=d)  # model as it stood before that day
            ps_d = models.PlayerStats(asof=d)
        except Exception as e:
            print(f"review: model asof {d} failed: {e}")
            continue
        for f in fs:
            h, a = f["home"], f["away"]
            rh = tm_all[(tm_all.team == h) & (tm_all.opponent == a) & (tm_all.date == d)]
            ra = tm_all[(tm_all.team == a) & (tm_all.opponent == h) & (tm_all.date == d)]
            if len(rh) != 1 or len(ra) != 1:
                continue  # stats not harvested yet -> next refresh
            row_h, row_a = rh.iloc[0].to_dict(), ra.iloc[0].to_dict()
            ref_e = ref_by_event.get(str(row_h.get("event_id")))
            lam, sims = mmp.simulate(h, a, stage="group", ref=ref_e)
            probs = models.market_probs(sims, h, a)
            exp_rows = []
            for label, stat in [("goals", "goals"), ("corners", "corners"),
                                ("cards", None), ("shots", "shots"), ("SoT", "sot"),
                                ("fouls", "fouls")]:
                if stat:
                    eh_ = float(np.median(sims[stat][h])); ea_ = float(np.median(sims[stat][a]))
                    ah_, aa_ = row_h.get(f"{stat}_for"), row_a.get(f"{stat}_for")
                else:  # cards: medians of combined yellows+reds simulations
                    eh_ = float(np.median(sims["yellows"][h] + sims["reds"][h]))
                    ea_ = float(np.median(sims["yellows"][a] + sims["reds"][a]))
                    ah_ = (row_h.get("yellows_for") or 0) + (row_h.get("reds_for") or 0)
                    aa_ = (row_a.get("yellows_for") or 0) + (row_a.get("reds_for") or 0)
                if ah_ is None or (isinstance(ah_, float) and np.isnan(ah_)):
                    continue
                exp_rows.append({"label": label, "eh": round(eh_, 1), "ea": round(ea_, 1),
                                 "ah": int(ah_), "aa": int(aa_)})
            # 6 Match + 6 Team + 6 Player tips per match, graded as-of-kickoff
            ev = str(int(row_h.get("event_id")))
            pm_ev = pm_all[pm_all.event_id.astype(str) == ev]
            cands = review_tips.build_candidates(mmp, ps_d, probs, row_h, row_a, h, a, ref_e, pm_ev)
            calls = review_tips.pick(cands, _cal)        # v2 (current, per-market calibration)
            calls_v1 = review_tips.pick(cands, _cal_v1)  # v1 (previous global calibration)
            fid = f"{d}|{h}|{a}"
            rcache[fid] = {"date": d, "home": h, "away": a,
                           "score": f"{int(row_h['goals_for'])}-{int(row_a['goals_for'])}",
                           "exp": exp_rows, "calls": calls, "calls_v1": calls_v1}
            print(f"review built: {h} v {a} ({rcache[fid]['score']})")
    json.dump(rcache, open(rcache_path, "w"))
    review = sorted(rcache.values(), key=lambda r: r["date"], reverse=True)
    data = {
        "asof": pd.Timestamp.now(tz="Europe/Malta").strftime("%Y-%m-%d %H:%M") + " (Malta)",
        "teams": team_data, "refs": refs, "players": players, "fixtures": fixtures,
        "book": {}, "review": review,  # odds feed removed — manual entry only
        "league": {"means": {s: round(ts.means[s], 4) for s in EXPORT_STATS},
                   "disp": {s: round(ts.disp[s], 4) for s in EXPORT_STATS},
                   "beta": {s: round(ts.elo_beta.get(s, 0.0), 5) for s in EXPORT_STATS},
                   "gc": [round(float(x), 6) for x in mm.gc],
                   "p1h_goals": round(ts.p1h_goals, 4), "p1h_cards": round(ts.p1h_cards, 4),
                   "cal": cal,
                   "pos_prior": {s: {k: round(v, 4) for k, v in pos_prior[s].items()}
                                 for s in PSTATS}},
    }
    tpl = open(os.path.join(HERE, "dashboard_template.html")).read()
    html = tpl.replace("__MODEL_DATA__", json.dumps(data, ensure_ascii=False))
    open(OUT, "w").write(html)
    print(f"wrote {OUT} ({os.path.getsize(OUT)//1024} KB)", flush=True)

if __name__ == "__main__":
    main()
