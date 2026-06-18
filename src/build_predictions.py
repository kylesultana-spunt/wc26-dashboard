"""Generate per-fixture prediction JSON for the public Statz-style site.

Loads the fitted model ONCE, builds the squad-filtered player pool (mirrors
export_dashboard.py), then for every fixture in data/fixtures.json writes
site_data/<eid>.json containing:

  meta (teams, ref, kickoff, done, score)   lambdas (expected rates per team)
  exp_pred (median goals/corners/cards/...)  markets (every calibrated market)
  tips (the 18 locked-style picks)           player form pips (last-5 actuals)
  graded tips + expected-vs-actual           for completed matches

Also writes site_data/_index.json (fixtures list + team Elo ratings) for the
homepage.  Same model + calibration as the dashboard, so the numbers match.

Run:  python3 src/build_predictions.py
"""
import json, os, sys, math, unicodedata
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models
import bets
import backtest as bt

DATA = models.DATA
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site_data")
os.makedirs(OUT, exist_ok=True)

P_MIN, EDGE_MIN, ODDS_MIN, P_CAP = 0.72, 0.05, 1.5, 0.93
CAL = json.load(open(os.path.join(DATA, "calibration.json")))


def calibrate(p, key=None):
    eps = 1e-4
    p = min(max(p, eps), 1 - eps)
    lp = math.log(p / (1 - p))
    c = (CAL.get("fam", {}).get(models.market_family(key)) if key else None) or CAL
    return float(min(1 / (1 + math.exp(-(c["a"] + c["b"] * lp))), P_CAP))


def _nm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").split())


def build_player_pool(teams):
    """Vectorised per-90 with shrinkage + squad filter — copied from export_dashboard."""
    p = pd.read_csv(os.path.join(DATA, "player_matches.csv"))
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
    players, K = {}, 6.0
    cpath = os.path.join(DATA, "club_rates.csv")
    club = pd.read_csv(cpath).set_index("nname") if os.path.exists(cpath) else None
    CLUB_COL = {"yellows": "club_yc90", "goals": "club_g90", "assists": "club_a90"}
    CLUB_W = 0.25
    for (team, name), g in p.groupby(["team", "player"]):
        if g.date.max() < pd.Timestamp("2024-06-01") or len(g) < 2:
            continue
        pos = g.position.mode().iloc[0] if g.position.notna().any() else "?"
        eff = (g.w * g.minutes_est / 90)
        n_eff = eff.sum()
        rec = {"pos": pos, "n": int(len(g)),
               "min": round(float(g[g.starter].minutes_est.mean()
                                  if g.starter.any() else 60.0), 1)}
        crow = club.loc[_nm(name)] if (club is not None and _nm(name) in club.index) else None
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
    # squad filter
    sq_path = os.path.join(DATA, "squads.json")
    if os.path.exists(sq_path):
        squads = json.load(open(sq_path))
        sq_norm = {}
        for tm, roster in squads.items():
            full, li = set(), set()
            for pl in roster:
                n = _nm(pl["name"]); full.add(n)
                tk = n.split()
                if tk:
                    li.add(tk[-1] + "|" + tk[0][0])
            sq_norm[tm] = (full, li)
        for t in list(players):
            if t not in sq_norm:
                continue
            full, li = sq_norm[t]
            kept = {}
            for nm, rec in players[t].items():
                n = _nm(nm); tk = n.split()
                key = (tk[-1] + "|" + tk[0][0]) if tk else ""
                if n in full or key in li:
                    kept[nm] = rec
            if kept:
                players[t] = kept
    for t in players:
        top = sorted(players[t].items(), key=lambda kv: -kv[1]["n"])[:45]
        players[t] = dict(top)
    return players


# ---- player recent form (last-5 actuals) for the statz-style pips -------------
STAT_COL = {"shots": "shots", "sot": "sot", "fouls_committed": "fouls_committed",
            "fouls_suffered": "fouls_suffered", "goals": "goals",
            "assists": "assists", "saves": "saves"}


def build_form_index():
    p = pd.read_csv(os.path.join(DATA, "player_matches.csv"))
    p["date"] = pd.to_datetime(p["date"])
    p = p.sort_values("date", ascending=False)
    return p


def player_form(form_df, team, player, stat, line):
    g = form_df[(form_df.team == team) & (form_df.player == player)].head(5)
    if g.empty:
        return []
    pips = []
    for _, r in g.iterrows():
        if stat == "score_or_assist":
            v = (r.get("goals") or 0) + (r.get("assists") or 0)
            cleared = v >= 1
        elif stat == "booked":
            v = (r.get("yellows") or 0) + (r.get("reds") or 0)
            cleared = v >= 1
        else:
            col = STAT_COL.get(stat)
            v = r.get(col) if col else None
            v = 0 if v is None or (isinstance(v, float) and pd.isna(v)) else v
            cleared = v > line
        pips.append({"v": int(v), "hit": bool(cleared)})
    return pips  # newest first


def main():
    fixtures = json.load(open(os.path.join(DATA, "fixtures.json")))
    teams = sorted({f["home"] for f in fixtures} | {f["away"] for f in fixtures})
    odds_path = os.path.join(DATA, "odds.json")
    ODDS = json.load(open(odds_path)) if os.path.exists(odds_path) else {}

    print("fitting model...", flush=True)
    mm = models.MatchModel()
    ps = models.PlayerStats()
    print("building player pool...", flush=True)
    players = build_player_pool(teams)
    form_df = build_form_index()

    tm_all = pd.read_csv(os.path.join(DATA, "team_matches.csv"))
    tm_all = tm_all[tm_all.comp == "fifa.world"]
    pm_all = pd.read_csv(os.path.join(DATA, "player_matches.csv"))

    index = {"fixtures": [], "teams": {}, "asof": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
    for t in teams:
        index["teams"][t] = {"elo": round(mm.elo.get(models.to_results_name(t), 1500), 1)}

    n_done = 0
    START = int(os.environ.get("FIXTURE_START", "1"))   # resume support (1-based)
    for i, f in enumerate(fixtures, 1):
        h, a, eid = f["home"], f["away"], str(f.get("eid"))
        if i < START:
            continue
        ref = f.get("ref") or None
        bets.reseed(eid)
        lam, sims = mm.simulate(h, a, stage="group", ref=ref)
        base_probs = models.market_probs(sims, h, a)   # team/match markets only

        # player props for the FULL squad pool (not just expected starters), so
        # regular contributors like defensive mids who foul a lot but rarely shoot
        # still get priced and surface on the site.
        # Kept SEPARATE from base_probs so bets.candidates categorises cleanly.
        probs = dict(base_probs)
        roster = [(pl, t) for t in (h, a) for pl in (players.get(t) or {})]
        for pl, team in roster:
            try:
                pp = models.player_prop_probs(ps, mm, pl, team,
                                              a if team == h else h, ref=ref)
            except Exception:
                continue
            # drop non-finite props (e.g. saves for outfield players have no data -> NaN)
            probs.update({k: v for k, v in pp.items()
                          if not k.startswith("_") and isinstance(v, float) and math.isfinite(v)})

        # full calibrated market table
        markets = []
        for k, p in sorted(probs.items()):
            if not (isinstance(p, (int, float)) and math.isfinite(p)):
                continue
            pc = calibrate(p, k)
            fair = 1 / pc
            min_odds = 1 / max(pc - EDGE_MIN, 1e-6)
            flag = ""
            if pc >= P_MIN:
                flag = f"bet if odds>={max(min_odds, ODDS_MIN):.2f}" if min_odds >= ODDS_MIN \
                    else "value"
            markets.append({"market": k, "p": round(pc, 4), "fair": round(fair, 3),
                            "min_odds": round(max(min_odds, ODDS_MIN), 3),
                            "fam": models.market_family(k), "flag": flag})

        # ---- value bets: OUR model probability vs the real bookmaker price ----
        # (best available price across books; trust-checked vs Pinnacle when present)
        value = []
        od = ODDS.get(eid, {})
        if od and not f.get("done"):
            tot = {"corners": sims["corners"][h] + sims["corners"][a],
                   "goals": sims["goals"][h] + sims["goals"][a],
                   "cards": (sims["yellows"][h] + sims["reds"][h]
                             + sims["yellows"][a] + sims["reds"][a])}
            btts = float(((sims["goals"][h] > 0) & (sims["goals"][a] > 0)).mean())
            for k, mo in od.get("markets", {}).items():
                price = mo.get("best") or mo.get("b365")
                if not price or price <= 1.0:
                    continue
                so, su = mo.get("sharp_over"), mo.get("sharp_under")
                label, ck = k.replace("_", " "), k
                if k == "btts_yes":
                    raw, label = btts, "both teams to score"
                elif k.startswith("tc1_over_") or k.startswith("tc2_over_"):
                    team = h if k.startswith("tc1") else a
                    line = float(k.split("_over_")[1]); lh = line * 2
                    if abs(lh - round(lh)) > 1e-9 or round(lh) % 2 == 0:
                        continue
                    raw = float((sims["corners"][team] > line).mean())
                    label, ck = f"{team} over {line} corners", "corners_over_x"
                else:
                    fam, _, ln = k.partition("_over_")
                    if fam not in tot:
                        continue
                    line = float(ln); lh = line * 2
                    if abs(lh - round(lh)) > 1e-9 or round(lh) % 2 == 0:
                        continue
                    raw = float((tot[fam] > line).mean())
                    label = f"{fam} over {line}"
                p = calibrate(raw, ck)
                if not (0.15 <= p <= 0.92):
                    continue
                edge = price * p - 1
                if not (EDGE_MIN <= edge <= 0.40):
                    continue
                row = {"k": label, "p": round(p, 3), "price": round(float(price), 2),
                       "book": mo.get("book") or "", "edge": round(edge, 3),
                       "fam": models.market_family(ck)}
                if so and su:
                    sharp = (1 / so) / ((1 / so) + (1 / su))
                    row["sharp_edge"] = round(float(price) * sharp - 1, 3)
                    row["beats_sharp"] = bool(float(price) * sharp - 1 >= 0)
                value.append(row)
            value.sort(key=lambda x: -x["edge"])

        # curated tips (6 match / 6 team / 6 player) — same selector as the dashboard.
        # candidates() computes player props itself, so feed it the clean base markets.
        tips = bets.select(bets.candidates(mm, ps, base_probs, players, h, a, ref), CAL)
        for t in tips:
            if t["cat"] == "player" and t.get("player"):
                pteam = _team_of(players, t["player"], h, a)
                t["team"] = pteam
                t["pos"] = (players.get(pteam, {}).get(t["player"], {}) or {}).get("pos", "")
                t["form"] = player_form(form_df, pteam, t["player"],
                                        t.get("stat"), t.get("line") or 0)

        # expected medians
        exp_pred = []
        for label, stat in [("goals", "goals"), ("corners", "corners"), ("cards", None),
                            ("shots", "shots"), ("SoT", "sot"), ("fouls", "fouls")]:
            if stat:
                eh_ = float(np.median(sims[stat][h])); ea_ = float(np.median(sims[stat][a]))
            else:
                eh_ = float(np.median(sims["yellows"][h] + sims["reds"][h]))
                ea_ = float(np.median(sims["yellows"][a] + sims["reds"][a]))
            exp_pred.append({"label": label, "eh": round(eh_, 1), "ea": round(ea_, 1)})

        out = {"eid": eid, "date": f["date"], "home": h, "away": a, "ref": ref or "",
               "stage": "group", "done": bool(f.get("done")),
               "elo": {h: index["teams"][h]["elo"], a: index["teams"][a]["elo"]},
               "lambdas": {s: lam[s] for s in lam if s != "_meta"},
               "exp_pred": exp_pred, "tips": tips, "markets": markets, "value": value}

        score = None
        if f.get("done"):
            rh = tm_all[(tm_all.team == h) & (tm_all.event_id.astype(str) == eid)]
            ra = tm_all[(tm_all.team == a) & (tm_all.event_id.astype(str) == eid)]
            if len(rh) == 1 and len(ra) == 1:
                row_h, row_a = rh.iloc[0].to_dict(), ra.iloc[0].to_dict()
                score = f"{int(row_h['goals_for'])}-{int(row_a['goals_for'])}"
                pm_ev = pm_all[pm_all.event_id.astype(str) == eid]
                graded = bets.grade([dict(t) for t in tips], row_h, row_a, h, a, pm_ev)
                out["graded"] = graded
                STMAP = {"goals": "goals", "corners": "corners", "shots": "shots",
                         "SoT": "sot", "fouls": "fouls"}
                exp_rows = []
                for e in exp_pred:
                    if e["label"] == "cards":
                        ah_ = (row_h.get("yellows_for") or 0) + (row_h.get("reds_for") or 0)
                        aa_ = (row_a.get("yellows_for") or 0) + (row_a.get("reds_for") or 0)
                    else:
                        st = STMAP[e["label"]]
                        ah_ = row_h.get(f"{st}_for"); aa_ = row_a.get(f"{st}_for")
                    if ah_ is None or (isinstance(ah_, float) and np.isnan(ah_)):
                        continue
                    exp_rows.append({**e, "ah": int(ah_), "aa": int(aa_)})
                out["exp_graded"] = exp_rows
                n_done += 1
        out["score"] = score

        json.dump(out, open(os.path.join(OUT, f"{eid}.json"), "w"), indent=0, allow_nan=False)
        print(f"  [{i}/{len(fixtures)}] {h} v {a}  ({len(markets)} markets, {len(tips)} tips)"
              + (f"  {score}" if score else ""), flush=True)

    # rebuild _index from ALL match files on disk (so partial/resumed runs compose)
    index["fixtures"] = []
    for f in fixtures:
        eid = str(f.get("eid")); fp = os.path.join(OUT, f"{eid}.json")
        if not os.path.exists(fp):
            continue
        d = json.load(open(fp))
        index["fixtures"].append({"eid": eid, "date": d.get("date"), "home": d.get("home"),
                                  "away": d.get("away"), "ref": d.get("ref", ""),
                                  "done": bool(d.get("done")), "score": d.get("score"),
                                  "n_tips": len(d.get("tips", []))})
    json.dump(index, open(os.path.join(OUT, "_index.json"), "w"), indent=1)

    # ---- per-team export for the team profile pages ----
    PKEYS = ["shots", "sot", "goals", "assists", "fouls_committed", "fouls_suffered",
             "yellows", "saves"]
    teams_out = {}
    for t in teams:
        pool = players.get(t, {})
        ranked = sorted(pool.items(), key=lambda kv: -(kv[1]["n"] * (1 + kv[1].get("goals", 0)
                                                                     + kv[1].get("shots", 0))))
        plist = []
        for nm, rec in ranked[:26]:
            plist.append({"name": nm, "pos": rec.get("pos", ""), "n": rec.get("n", 0),
                          **{k: round(float(rec.get(k, 0) or 0), 2) for k in PKEYS}})
        teams_out[t] = {"elo": round(mm.elo.get(models.to_results_name(t), 1500), 1),
                        "n": int((tm_all.team == t).sum()) if "team" in tm_all else 0,
                        "players": plist}
    json.dump(teams_out, open(os.path.join(OUT, "_teams.json"), "w"),
              indent=1, allow_nan=False, ensure_ascii=False)

    print(f"\nDONE: {len(fixtures)} fixtures + {len(teams_out)} teams written to site_data/ "
          f"({n_done} graded)")


def _team_of(players, player, h, a):
    for t in (h, a):
        if player in (players.get(t) or {}):
            return t
    return h


if __name__ == "__main__":
    main()
