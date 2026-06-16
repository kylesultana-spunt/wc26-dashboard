"""Single source of truth for the model's bet tips.

For each fixture we compute ONE definite set of 18 tips (6 match, 6 team, 6 player):
over-side only, calibrated model probability in the 0.40-0.68 betting band, ranked by
edge potential (soft markets first), one-per-family for variety. The SAME function feeds
the live dashboard and post-match grading, so what you are shown is exactly what gets
graded. Tips are frozen into data/locked_bets.json ~1h before kickoff and never change.

Determinism: the Monte Carlo is seeded per fixture (by event id) before the tips are
computed, so a fixture's tips are identical every run.
"""
import math
import numpy as np
import pandas as pd
import models
import backtest as bt

# how soft books tend to price each family (edge potential) — mirrors the dashboard
SOFT = {"fouls": 1.00, "cards": 0.95, "corners": 0.90, "offsides": 0.90,
        "saves": 0.85, "shots": 0.70, "goals": 0.35, "result": 0.30, "tackles": 0.6}
SKIP = ("result", "dnb", "double_chance", "win_margin", "score_", "htft",
        "ht_score", "half_most", "goal_both")


def seed_for(event_id):
    """Stable integer seed from an event id (so sims are reproducible per match)."""
    try:
        return int(str(event_id)) % (2**32 - 1)
    except Exception:
        return abs(hash(str(event_id))) % (2**32 - 1)


def reseed(event_id):
    models.RNG = np.random.default_rng(seed_for(event_id))


def _cat(k):
    if k.startswith(("team_", "gk_saves_", "most_corners", "most_cards", "btt_")):
        return "team"
    return "match"


def _calfn(cal):
    def f(p, key):
        p = min(max(p, 1e-4), 1 - 1e-4)
        lp = math.log(p / (1 - p))
        c = (cal.get("fam", {}).get(models.market_family(key))) or cal
        return min(1 / (1 + math.exp(-(c["a"] + c["b"] * lp))), 0.93)
    return f


def _expected_starters(players, h, a):
    """Top ~5 per team (4 outfield + GK), mirroring the dashboard's auto-pick."""
    out = []
    for t in (h, a):
        sq = list((players.get(t) or {}).items())
        outf = [(n, r) for n, r in sq if r.get("pos") != "G"]
        outf.sort(key=lambda nr: -(nr[1]["n"] * (min(nr[1].get("min", 60), 90) / 90)
                                    * (1 + 2 * (nr[1].get("shots", 0) or 0))))
        out += [(n, t) for n, _ in outf[:4]]
        gks = sorted([(n, r) for n, r in sq if r.get("pos") == "G"],
                     key=lambda nr: -nr[1]["n"])
        if gks:
            out.append((gks[0][0], t))
    return out


def _player_label(pl, mk):
    rest = mk[len(pl) + 1:]
    if "_over_" in rest:
        stat, _, ln = rest.rpartition("_over_")
        return f"{pl} {stat.replace('_', ' ')} {float(ln)}+", stat, float(ln)
    if rest == "score_or_assist":
        return f"{pl} score or assist", "score_or_assist", 0
    if rest == "to_be_booked":
        return f"{pl} to be booked", "booked", 0
    return None, None, None


def candidates(mmp, ps, probs, players, h, a, ref):
    """Pre-match candidate tips (over-side, no outcomes), keyed by category."""
    out = {"match": [], "team": [], "player": []}
    for k, p in probs.items():
        if any(k.startswith(s) for s in SKIP):
            continue
        if "under" in k or k.endswith("_no"):          # over-side only
            continue
        out[_cat(k)].append({"key": k, "mk": k, "raw": float(p),
                             "fam": models.market_family(k)})
    for pl, team in _expected_starters(players, h, a):
        try:
            pp = models.player_prop_probs(ps, mmp, pl, team, a if team == h else h, ref=ref)
        except Exception:
            continue
        for k, p in pp.items():
            if k.startswith("_") or not k.startswith(pl + "_"):
                continue
            label, stat, line = _player_label(pl, k)
            if label is None:
                continue
            out["player"].append({"key": label, "mk": k, "raw": float(p),
                                  "fam": pl, "player": pl, "stat": stat, "line": line})
    return out


def select(cands, cal, per_cat=6):
    """Pick the definite per-category tips: in-band, edge-ranked, one-per-family."""
    f = _calfn(cal)
    out = []
    for cat in ("match", "team", "player"):
        scored = []
        for c in cands[cat]:
            pc = f(c["raw"], c["mk"])
            if not (0.40 <= pc <= 0.68):
                continue
            soft = 0.85 if cat == "player" else SOFT.get(c["fam"], 0.6)
            scored.append({**c, "p": round(pc, 3), "fair": round(1 / pc, 2),
                           "cat": cat, "score": soft * 0.7 + pc * 0.3})
        scored.sort(key=lambda x: -x["score"])
        chosen, fam = [], {}
        for cap in (1, 2, 3, 99):
            for c in scored:
                if len(chosen) >= per_cat:
                    break
                if c in chosen or fam.get(c["fam"], 0) >= cap:
                    continue
                chosen.append(c)
                fam[c["fam"]] = fam.get(c["fam"], 0) + 1
            if len(chosen) >= per_cat:
                break
        for c in chosen:
            label = c["key"] if cat == "player" else c["key"].replace("_", " ")
            out.append({"k": label, "mk": c["mk"], "cat": cat, "p": c["p"],
                        "fair": c["fair"], "fam": c["fam"],
                        **({"player": c.get("player"), "stat": c.get("stat"),
                            "line": c.get("line")} if cat == "player" else {})})
    return out


def _grade_player(stat, line, prow):
    if prow is None:
        return None                          # didn't feature -> void
    def g(c):
        v = prow.get(c)
        return 0 if (v is None or (isinstance(v, float) and pd.isna(v))) else v
    if stat == "score_or_assist":
        return int((g("goals") + g("assists")) >= 1)
    if stat == "booked":
        return int((g("yellows") + (g("reds") or 0)) >= 1)
    col = {"shots": "shots", "sot": "sot", "fouls_committed": "fouls_committed",
           "fouls_suffered": "fouls_suffered", "goals": "goals",
           "assists": "assists", "saves": "saves"}.get(stat)
    return int((g(col) if col else 0) > line)


def grade(tips, row_h, row_a, h, a, pm_event):
    """Add 'hit' (1/0, or None=void) to each locked tip from actual results."""
    prow = {r["player"]: r for r in pm_event.to_dict("records")} if pm_event is not None else {}
    for t in tips:
        if t["cat"] == "player":
            t["hit"] = _grade_player(t.get("stat"), t.get("line"), prow.get(t.get("player")))
        else:
            y = bt.outcome_value(row_h, row_a, t["mk"], h, a)
            t["hit"] = None if y is None else int(y)
    return tips
