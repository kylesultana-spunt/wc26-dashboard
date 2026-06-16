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
    # ---- restrict the pool to the current 26-man squad (drops cut/retired players) ----
    import unicodedata as _ud2
    def _nm(s):
        s = _ud2.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
        return " ".join(s.replace("-", " ").split())
    sq_path = os.path.join(models.DATA, "squads.json")
    if os.path.exists(sq_path):
        squads = json.load(open(sq_path))
        sq_norm = {}
        for tm, roster in squads.items():
            full, li = set(), set()
            for pl in roster:
                n = _nm(pl["name"]); full.add(n)
                tk = n.split()
                if tk:
                    li.add(tk[-1] + "|" + tk[0][0])     # lastname|firstinitial fallback
            sq_norm[tm] = (full, li)
        dropped = 0
        for t in list(players):
            if t not in sq_norm:
                continue                                # team not matched -> leave as-is
            full, li = sq_norm[t]
            kept = {}
            for nm, rec in players[t].items():
                n = _nm(nm); tk = n.split()
                key = (tk[-1] + "|" + tk[0][0]) if tk else ""
                if n in full or key in li:
                    kept[nm] = rec
                else:
                    dropped += 1
            if kept:                                    # only apply if we matched someone
                players[t] = kept
        print(f"squad filter: pool restricted to current squads (dropped {dropped} non-squad players)")
    for t in players:  # cap squad lists
        top = sorted(players[t].items(), key=lambda kv: -kv[1]["n"])[:45]
        players[t] = dict(top)

    book_out = {}  # odds feed removed
    # ---- ONE locked set of bets per fixture (single source of truth) ----
    # bets.py selects 18 tips (6 match / 6 team / 6 player). The first build within ~1h of
    # kickoff (or after the match) FREEZES them into locked_bets.json; thereafter they are
    # never recomputed. The same frozen set is shown live and graded after the match, so what
    # you saw is exactly what gets scored. Monte Carlo is seeded per event id => reproducible.
    import bets
    cal = json.load(open(os.path.join(models.DATA, "calibration.json")))
    tm_all = pd.read_csv(os.path.join(models.DATA, "team_matches.csv"))
    tm_all = tm_all[tm_all.comp == "fifa.world"]
    pm_all = pd.read_csv(os.path.join(models.DATA, "player_matches.csv"))
    locks_path = os.path.join(models.DATA, "locked_bets.json")
    locks = json.load(open(locks_path)) if os.path.exists(locks_path) else {}
    PS_now = models.PlayerStats()
    now_mt = pd.Timestamp.now(tz="Europe/Malta")
    _mm_cache, _ps_cache = {}, {}
    def _models_asof(asof):
        if asof is None:
            return mm, PS_now
        if asof not in _mm_cache:
            _mm_cache[asof] = models.MatchModel(asof=asof)
            _ps_cache[asof] = models.PlayerStats(asof=asof)
        return _mm_cache[asof], _ps_cache[asof]

    def _compute(f, asof=None, want_xi=False):
        h, a, eid = f["home"], f["away"], str(f.get("eid"))
        bets.reseed(eid)
        mmp, ps = _models_asof(asof)
        ref = f.get("ref") or ref_by_event.get(eid) or None
        xi = bets.fetch_xi(eid) if want_xi else {}    # only at lock time (~1h pre-KO); else skip ESPN
        smult = bets.stat_mult(ps, players, h, a, xi) if xi else None  # lineup tilt (fouls/shots)
        lam, sims = mmp.simulate(h, a, stage="group", ref=ref, stat_mult=smult)
        probs = models.market_probs(sims, h, a)
        tips = bets.select(bets.candidates(mmp, ps, probs, players, h, a, ref, xi=xi), cal)
        exp_pred = []
        for label, stat in [("goals", "goals"), ("corners", "corners"), ("cards", None),
                            ("shots", "shots"), ("SoT", "sot"), ("fouls", "fouls")]:
            if stat:
                eh_ = float(np.median(sims[stat][h])); ea_ = float(np.median(sims[stat][a]))
            else:
                eh_ = float(np.median(sims["yellows"][h] + sims["reds"][h]))
                ea_ = float(np.median(sims["yellows"][a] + sims["reds"][a]))
            exp_pred.append({"label": label, "eh": round(eh_, 1), "ea": round(ea_, 1)})
        return tips, exp_pred

    locked_disp, review = {}, []
    for f in fixtures:
        h, a, eid = f["home"], f["away"], str(f.get("eid"))
        try:
            ko = pd.Timestamp(f["date"][:16]).tz_localize("Europe/Malta")
        except Exception:
            ko = None
        in_window = bool(f["done"]) or (ko is not None and now_mt >= ko - pd.Timedelta(hours=1))
        near = ko is not None and (ko - now_mt) <= pd.Timedelta(days=5)
        if eid in locks:
            entry = locks[eid]
        elif in_window:                                   # FREEZE now (pull confirmed XI)
            tips, exp_pred = _compute(f, asof=(f["date"][:10] if f["done"] else None), want_xi=True)
            entry = {"home": h, "away": a, "kickoff": f["date"], "eid": eid,
                     "locked_at": now_mt.strftime("%Y-%m-%d %H:%M") + " (Malta)",
                     "tips": tips, "exp_pred": exp_pred}
            locks[eid] = entry
            print(f"LOCKED bets: {h} v {a}")
        elif near:                                        # provisional preview (not frozen)
            tips, exp_pred = _compute(f)
            entry = {"home": h, "away": a, "kickoff": f["date"], "eid": eid,
                     "locked_at": None, "tips": tips, "exp_pred": exp_pred}
        else:                                             # far off: lock closer to kickoff
            entry = {"home": h, "away": a, "kickoff": f["date"], "eid": eid,
                     "locked_at": None, "tips": [], "exp_pred": []}
        locked_disp[f"{h}|{a}"] = {"locked": entry["locked_at"] is not None,
                                   "lock_time": entry["locked_at"],
                                   "kickoff": f["date"], "tips": entry["tips"]}
        if f["done"]:                                     # grade once stats are in
            rh = tm_all[(tm_all.team == h) & (tm_all.event_id.astype(str) == eid)]
            ra = tm_all[(tm_all.team == a) & (tm_all.event_id.astype(str) == eid)]
            if len(rh) == 1 and len(ra) == 1 and entry["tips"]:
                row_h, row_a = rh.iloc[0].to_dict(), ra.iloc[0].to_dict()
                pm_ev = pm_all[pm_all.event_id.astype(str) == eid]
                graded = bets.grade([dict(t) for t in entry["tips"]], row_h, row_a, h, a, pm_ev)
                STMAP = {"goals": "goals", "corners": "corners", "shots": "shots",
                         "SoT": "sot", "fouls": "fouls"}
                exp_rows = []
                for e in entry["exp_pred"]:
                    if e["label"] == "cards":
                        ah_ = (row_h.get("yellows_for") or 0) + (row_h.get("reds_for") or 0)
                        aa_ = (row_a.get("yellows_for") or 0) + (row_a.get("reds_for") or 0)
                    else:
                        st = STMAP[e["label"]]
                        ah_ = row_h.get(f"{st}_for"); aa_ = row_a.get(f"{st}_for")
                    if ah_ is None or (isinstance(ah_, float) and np.isnan(ah_)):
                        continue
                    exp_rows.append({**e, "ah": int(ah_), "aa": int(aa_)})
                review.append({"date": f["date"][:10], "home": h, "away": a,
                               "score": f"{int(row_h['goals_for'])}-{int(row_a['goals_for'])}",
                               "exp": exp_rows, "tips": graded})
    json.dump(locks, open(locks_path, "w"))
    review = sorted(review, key=lambda r: r["date"], reverse=True)

    # ---- Value Finder: model probability vs real market price (OddsPapi) ----
    # For every upcoming fixture with live odds, compare the model's probability for each
    # priced market (corners / goals / cards totals + BTTS) to the BEST price across 130+
    # books, and to Pinnacle's no-vig "fair" line. Flag only genuine value.
    odds_path = os.path.join(models.DATA, "odds.json")
    odds = json.load(open(odds_path)) if os.path.exists(odds_path) else {}
    calf = bets._calfn(cal)
    EDGE_MIN = 0.03
    fix_by_eid = {str(f.get("eid")): f for f in fixtures}
    value = []
    for eid, od in odds.items():
        f = fix_by_eid.get(eid)
        if not f or f.get("done"):
            continue
        bets.reseed(eid)
        h, a = f["home"], f["away"]
        ref = f.get("ref") or ref_by_event.get(eid) or None
        lam, sims = mm.simulate(h, a, stage="group", ref=ref)
        tot = {"corners": sims["corners"][h] + sims["corners"][a],
               "goals": sims["goals"][h] + sims["goals"][a],
               "cards": (sims["yellows"][h] + sims["reds"][h]
                         + sims["yellows"][a] + sims["reds"][a])}
        btts = float(((sims["goals"][h] > 0) & (sims["goals"][a] > 0)).mean())
        for k, m in od.get("markets", {}).items():
            b365, so, su = m.get("b365"), m.get("sharp_over"), m.get("sharp_under")
            if not b365 or b365 <= 1.0 or not so or not su:
                continue                      # need a Bet365 price + a Pinnacle line
            label = k.replace("_", " ")
            ck = k                            # calibration key (family)
            if k == "btts_yes":
                raw = btts
            elif k.startswith("tc1_over_") or k.startswith("tc2_over_"):  # per-team corners
                team = h if k.startswith("tc1") else a
                line = float(k.split("_over_")[1])
                lh = line * 2
                if abs(lh - round(lh)) > 1e-9 or round(lh) % 2 == 0:
                    continue
                raw = float((sims["corners"][team] > line).mean())
                label = f"{team} corners over {line}"
                ck = "corners_over_x"
            else:
                fam, _, ln = k.partition("_over_")
                if fam not in tot:
                    continue
                line = float(ln)
                lh = line * 2                 # keep only clean .5 lines (binary over/under)
                if abs(lh - round(lh)) > 1e-9 or round(lh) % 2 == 0:
                    continue
                raw = float((tot[fam] > line).mean())
            p = calf(raw, ck)                 # model probability (calibrated)
            if not (0.15 <= p <= 0.92):
                continue
            sharp = (1 / so) / ((1 / so) + (1 / su))   # Pinnacle de-vig = true prob
            edge = b365 * p - 1               # edge: Bet365 price vs OUR MODEL's probability
            sharp_edge = b365 * sharp - 1     # same vs Pinnacle's fair line (the trust-check)
            if not (EDGE_MIN <= edge <= 0.30):  # floor = value; cap kills nonsense
                continue
            kelly = max((p * b365 - 1) / (b365 - 1), 0) / 4   # quarter-Kelly off the model prob
            value.append({"match": f"{h} v {a}", "key": label,
                          "p": round(p, 3), "sharp": round(sharp, 3),
                          "b365": b365, "edge": round(edge, 3),
                          "sharp_edge": round(sharp_edge, 3),
                          "kelly": round(kelly, 3),
                          "beats_sharp": bool(sharp_edge >= 0)})  # Pinnacle also says Bet365 is generous
    value.sort(key=lambda x: -x["edge"])
    print(f"value finder: {len(value)} +EV bets from {len(odds)} priced fixtures")

    data = {
        "asof": pd.Timestamp.now(tz="Europe/Malta").strftime("%Y-%m-%d %H:%M") + " (Malta)",
        "teams": team_data, "refs": refs, "players": players, "fixtures": fixtures,
        "book": {}, "review": review, "locked": locked_disp, "value": value,  # value = +EV bets vs real market
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
