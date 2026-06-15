"""Build the model's pre-match Bet Tips for a completed fixture and grade them.

6 Match + 6 Team + 6 Player tips per match (18), selected exactly as the live dashboard
would (over-side, model prob in the 0.40-0.68 betting band, one-per-family variety), then
graded against what actually happened. Candidates are computed once; `pick()` applies a
given calibration (V2 or V1) so both model versions can be compared on the same matches.
"""
import math
import pandas as pd
import models
import backtest as bt

SKIP = ("result", "dnb", "double_chance", "win_margin", "score_", "htft",
        "ht_score", "half_most", "goal_both")


def _cat_tm(k):
    if k.startswith(("team_", "gk_saves_", "most_corners", "most_cards", "btt_")):
        return "team"
    return "match"


def _fam_tm(k):
    for f in ("corners", "cards", "sot", "shots", "fouls", "offsides", "saves"):
        if f in k:
            return f
    return "goals"


def _grade_player(stat, line, prow):
    if prow is None:
        return 0
    def g(c):
        v = prow.get(c)
        return 0 if (v is None or (isinstance(v, float) and pd.isna(v))) else v
    if stat == "score_or_assist":
        return int((g("goals") + g("assists")) >= 1)
    if stat == "booked":
        return int((g("yellows") + (g("reds") or 0)) >= 1)
    col = {"shots": "shots", "sot": "sot", "fouls_committed": "fouls_committed",
           "fouls_suffered": "fouls_suffered", "goals": "goals", "assists": "assists",
           "saves": "saves"}.get(stat)
    return int((g(col) if col else 0) > line)


def build_candidates(mmp, ps, probs, row_h, row_a, h, a, ref, pm_event):
    """Return {match,team,player: [ {k, raw, hit, fk}, ... ]} with raw (uncalibrated) probs."""
    cands = {"match": [], "team": [], "player": []}
    for k, p in probs.items():
        if any(k.startswith(s) for s in SKIP):
            continue
        if "under" in k or k.endswith("_no"):   # over-side only — match the live Bet Tips
            continue
        y = bt.outcome_value(row_h, row_a, k, h, a)
        if y is None:
            continue
        c = _cat_tm(k)
        cands[c].append({"k": k, "raw": float(p), "hit": int(y), "fk": _fam_tm(k)})
    prow_by = {r["player"]: r for r in pm_event.to_dict("records")}
    starters = [r for r in pm_event.to_dict("records") if r.get("starter") in (True, "True", 1)]
    for pr in starters:
        pl, team = pr["player"], pr["team"]
        opp = a if team == h else h
        try:
            pp = models.player_prop_probs(ps, mmp, pl, team, opp, ref=ref)
        except Exception:
            continue
        for k, p in pp.items():
            if k.startswith("_") or not k.startswith(pl + "_"):
                continue
            rest = k[len(pl) + 1:]
            if "_over_" in rest:
                stat, _, ln = rest.rpartition("_over_"); line = float(ln)
            elif rest == "score_or_assist":
                stat, line = "score_or_assist", 0
            elif rest == "to_be_booked":
                stat, line = "booked", 0
            else:
                continue
            y = _grade_player(stat, line, prow_by.get(pl))
            label = f"{pl} {stat.replace('_', ' ')}" + ("" if line == 0 else f" {line}+")
            cands["player"].append({"k": label, "raw": float(p), "hit": int(y), "fk": pl})
    return cands


def pick(cands, calfn, per_cat=6):
    """Apply a calibration, keep over-side picks in the 0.40-0.68 band, take 6 per category
    with one-per-family variety. Returns a flat list of {k, p, fair, hit, cat}."""
    out = []
    for cat in ("match", "team", "player"):
        scored = []
        for c in cands[cat]:
            pc = calfn(c["raw"], c["k"])
            if not (0.40 <= pc <= 0.68):
                continue
            scored.append({**c, "pc": pc})
        chosen, fam = [], {}
        for cap in (1, 2, 3, 99):
            for c in sorted(scored, key=lambda x: -x["pc"]):
                if len(chosen) >= per_cat:
                    break
                if c in chosen or fam.get(c["fk"], 0) >= cap:
                    continue
                chosen.append(c); fam[c["fk"]] = fam.get(c["fk"], 0) + 1
            if len(chosen) >= per_cat:
                break
        for c in chosen:
            out.append({"k": c["k"], "p": round(c["pc"], 3),
                        "fair": round(1 / c["pc"], 2), "hit": c["hit"], "cat": cat})
    return out
