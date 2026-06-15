"""WC26 bet finder.

Usage:
  python3 predict.py --home "USA" --away "Paraguay" [--ref "Facundo Tello"]
      [--stage group|r32|r16|qf|sf|final] [--rivalry]
      [--players "Christian Pulisic:USA, Diego Gomez:Paraguay"]
      [--odds odds.txt] [--json out.json]

odds.txt: one per line ->  market_key odds      e.g.  goals_over_2.5 1.85
Without --odds it prints fair odds + minimum odds to bet for every market.
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models

CAL = json.load(open(os.path.join(models.DATA, "calibration.json")))
P_MIN, EDGE_MIN, ODDS_MIN, P_CAP = 0.72, 0.05, 1.5, 0.93

def calibrate(p, key=None):
    eps = 1e-4
    p = min(max(p, eps), 1 - eps)
    lp = np.log(p / (1 - p))
    c = (CAL.get("fam", {}).get(models.market_family(key)) if key else None) or CAL
    return float(min(1 / (1 + np.exp(-(c["a"] + c["b"] * lp))), P_CAP))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--away", required=True)
    ap.add_argument("--ref", default=None)
    ap.add_argument("--stage", default="group")
    ap.add_argument("--rivalry", action="store_true")
    ap.add_argument("--players", default=None, help="'Name:Team, Name:Team' (assumed starters)")
    ap.add_argument("--odds", default=None, help="file with 'market_key odds' lines")
    ap.add_argument("--json", default=None)
    ap.add_argument("--log", action="store_true", help="append *** BET *** picks to data/bets.csv for CLV/ROI tracking")
    a = ap.parse_args()

    mm = models.MatchModel()
    lam, sims = mm.simulate(a.home, a.away, ref=a.ref, stage=a.stage, rivalry=a.rivalry)
    probs = models.market_probs(sims, a.home, a.away)

    if a.players:
        ps = models.PlayerStats()
        for spec in a.players.split(","):
            name, team = [x.strip() for x in spec.split(":")]
            pp = models.player_prop_probs(ps, mm, name, team,
                                          a.away if team == a.home else a.home, ref=a.ref)
            probs.update({k: v for k, v in pp.items() if not k.startswith("_")})

    meta = lam["_meta"]
    print(f"\n{a.home} vs {a.away}  | stage={a.stage}"
          f" | Elo {meta['elo'][a.home]:.0f} v {meta['elo'][a.away]:.0f}"
          f" | ref mult {meta['ref_mult']:.2f} (n={meta['ref_n']})")
    print(f"exp goals {lam['goals'][a.home]:.2f}-{lam['goals'][a.away]:.2f}"
          f" | corners {lam['corners'][a.home]:.1f}-{lam['corners'][a.away]:.1f}"
          f" | cards {lam['yellows'][a.home]+lam['reds'][a.home]:.1f}-"
          f"{lam['yellows'][a.away]+lam['reds'][a.away]:.1f}\n")

    odds = {}
    if a.odds:
        for line in open(a.odds):
            parts = line.split()
            if len(parts) >= 2:
                try: odds[" ".join(parts[:-1])] = float(parts[-1])
                except ValueError: pass

    rows = []
    for k, p in sorted(probs.items()):
        pc = calibrate(p, k)
        fair = 1 / pc
        min_odds = 1 / max(pc - EDGE_MIN, 1e-6)
        o = odds.get(k)
        flag = ""
        if pc >= P_MIN:
            if o is None:
                flag = "CANDIDATE" if min_odds >= ODDS_MIN else f"bet if odds>={max(min_odds, ODDS_MIN):.2f}"
            elif o >= ODDS_MIN and pc - 1 / o >= EDGE_MIN:
                flag = f"*** BET (EV {pc * o - 1:+.1%}) ***"
        rows.append((k, pc, fair, min_odds, o, flag))

    hdr = f"{'market':46s} {'prob':>6s} {'fair':>5s} {'min':>5s} {'book':>5s}  flag"
    print(hdr); print("-" * len(hdr))
    for k, pc, fair, mo, o, flag in rows:
        if pc >= 0.55 or flag or o:
            print(f"{k:46s} {pc:6.1%} {fair:5.2f} {max(mo, ODDS_MIN):5.2f} "
                  f"{o if o else '':>5}  {flag}")

    bets = [r for r in rows if "BET" in r[5]]
    if a.log and bets:
        import datetime, validate_bets as vb
        today = datetime.date.today().isoformat()
        for k, pc, fair, mo, o, flag in bets:
            vb.log_bet(today, f"{a.home} v {a.away}", k, pc, o)
        print(f"logged {len(bets)} bet(s) to data/bets.csv (fill odds_close + result later for CLV)")
    print(f"\n{len(bets)} qualifying bet(s)" if odds else
          "\n(no odds supplied — 'min' column = lowest odds at which a 72%+ market is worth taking)")
    if a.json:
        json.dump({"fixture": f"{a.home} v {a.away}", "stage": a.stage, "ref": a.ref,
                   "lambdas": {s: lam[s] for s in lam if s != "_meta"},
                   "markets": [{"market": k, "p": pc, "fair": f, "min_odds": m,
                                "book": o, "flag": fl} for k, pc, f, m, o, fl in rows]},
                  open(a.json, "w"), indent=1)
        print(f"JSON written to {a.json}")

if __name__ == "__main__":
    main()
