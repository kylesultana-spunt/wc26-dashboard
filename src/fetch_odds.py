"""Pull real bookmaker odds from OddsPapi (free tier) for our upcoming fixtures.

Writes data/odds.json keyed by OUR event id:
  { "<eid>": { "matched": "Home|Away",
               "markets": { "corners_over_8.5": {"best":1.65,"book":"x","sharp_over":1.63,"sharp_under":2.19},
                            "goals_over_2.5": {...}, "cards_over_4.5": {...},
                            "btts_yes": {"best":..,"book":..,"sharp_over":..,"sharp_under":..} } } }

For each market we keep the BEST over-side price across all books (line shopping) plus
Pinnacle's over/under so the value step can de-vig to a sharp 'fair' probability.

Key: data/oddsapi_key.txt or env ODDS_API_KEY. No key -> writes nothing (build still works).
Conservative on the free 250/month budget: only OUR not-done fixtures within WINDOW_DAYS.
"""
import os, sys, json, time, re, unicodedata
import urllib.request, urllib.parse
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
BASE = "https://api.oddspapi.io/v4"
WINDOW_DAYS = 2                      # only fetch fixtures kicking off within this many days
MAX_FIXTURES = 8                     # cap odds calls per run (free tier = ~250/month)
SPORT_SOCCER = 10
SHARP = "pinnacle"
# OddsPapi marketType + period=fulltime  ->  our market-key prefix
TOTALS = {"totals": "goals", "totals-corners": "corners", "totals-cards": "cards"}


def _key():
    return (os.environ.get("ODDS_API_KEY")
            or (open(os.path.join(DATA, "oddsapi_key.txt")).read().strip()
                if os.path.exists(os.path.join(DATA, "oddsapi_key.txt")) else ""))


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(and|the|dr|rep|republic|of|srl)\b", " ", s)
    return re.sub(r"[^a-z]", "", s)


_ALIAS = {"turkiye": "turkey", "czechia": "czechrepublic", "cotedivoire": "ivorycoast",
          "capeverde": "caboverde", "bosniaherzegovina": "bosnia", "congodr": "congo",
          "southkorea": "korea", "usa": "unitedstates"}


def _akey(name):
    n = _norm(name)
    return _ALIAS.get(n, n)


def _get(path, **params):
    params["apiKey"] = _key()
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "wc26"}),
                                timeout=30) as r:
        return json.load(r)


def _price(bd, mid, oid):
    try:
        o = bd[str(mid)]["outcomes"][str(oid)]["players"]["0"]
        return o["price"] if o.get("active", True) else None
    except (KeyError, TypeError):
        return None


def run():
    if not _key():
        print("fetch_odds: no OddsPapi key — skipping (manual odds entry still works)")
        return
    fixtures = json.load(open(os.path.join(DATA, "fixtures.json")))
    today = dt.date.today()
    want = {}
    for f in fixtures:
        if f.get("done"):
            continue
        try:
            d = dt.date.fromisoformat(f["date"][:10])
        except Exception:
            continue
        if 0 <= (d - today).days <= WINDOW_DAYS:
            want[(_akey(f["home"]), _akey(f["away"]))] = f
    if not want:
        print("fetch_odds: no upcoming fixtures in window")
        return
    # cap to the soonest MAX_FIXTURES to stay within the free request budget
    if len(want) > MAX_FIXTURES:
        soonest = sorted(want.values(), key=lambda f: f["date"])[:MAX_FIXTURES]
        want = {(_akey(f["home"]), _akey(f["away"])): f for f in soonest}
    cat = {m["marketId"]: m for m in _get("markets", sportId=SPORT_SOCCER)}
    time.sleep(1.0)
    lo = min(f["date"][:10] for f in want.values())
    hi = (dt.date.fromisoformat(lo) + dt.timedelta(days=WINDOW_DAYS)).isoformat()
    opfix = _get("fixtures", sportId=SPORT_SOCCER, **{"from": lo, "to": hi})
    time.sleep(1.0)
    out = {}
    for opf in opfix:
        if opf.get("tournamentName") != "World Cup" or not opf.get("hasOdds"):
            continue
        p1, p2 = _akey(opf["participant1Name"]), _akey(opf["participant2Name"])
        f = want.get((p1, p2)) or want.get((p2, p1))
        if not f:
            continue
        try:
            books = _get("odds", fixtureId=opf["fixtureId"]).get("bookmakerOdds", {})
        except Exception as e:
            print(f"fetch_odds: odds fetch failed for {f['home']} v {f['away']}: {e}")
            time.sleep(1.0); continue
        time.sleep(1.0)
        markets = {}
        # ---- over/under family markets (corners, goals, cards) ----
        # collect, per (prefix,line): best Over price across books + Pinnacle over/under
        agg = {}
        for slug, bdwrap in books.items():
            bd = bdwrap.get("markets", {})
            for mid in bd:
                m = cat.get(int(mid))
                if not m or m.get("period") != "fulltime":
                    continue
                mt = m.get("marketType")
                if mt in TOTALS:
                    line = m.get("handicap")
                    over = next((o["outcomeId"] for o in m["outcomes"]
                                 if o["outcomeName"].lower().startswith("over")), None)
                    under = next((o["outcomeId"] for o in m["outcomes"]
                                  if o["outcomeName"].lower().startswith("under")), None)
                    po = _price(bd, mid, over); pu = _price(bd, mid, under)
                    k = f"{TOTALS[mt]}_over_{line}"
                    a = agg.setdefault(k, {"best": 0.0, "book": None,
                                           "sharp_over": None, "sharp_under": None})
                    if po and po > a["best"]:
                        a["best"], a["book"] = po, slug
                    if slug == SHARP:
                        a["sharp_over"], a["sharp_under"] = po, pu
                elif mt == "bothteamsscore":
                    yes = next((o["outcomeId"] for o in m["outcomes"]
                                if o["outcomeName"].lower() == "yes"), None)
                    no = next((o["outcomeId"] for o in m["outcomes"]
                               if o["outcomeName"].lower() == "no"), None)
                    py = _price(bd, mid, yes); pn = _price(bd, mid, no)
                    a = agg.setdefault("btts_yes", {"best": 0.0, "book": None,
                                                    "sharp_over": None, "sharp_under": None})
                    if py and py > a["best"]:
                        a["best"], a["book"] = py, slug
                    if slug == SHARP:
                        a["sharp_over"], a["sharp_under"] = py, pn
        for k, a in agg.items():
            if a["best"] > 1.0:
                markets[k] = a
        out[str(f.get("eid"))] = {"matched": f"{f['home']}|{f['away']}",
                                  "books": len(books), "markets": markets}
        print(f"fetch_odds: {f['home']} v {f['away']} — {len(books)} books, {len(markets)} markets")
    json.dump(out, open(os.path.join(DATA, "odds.json"), "w"))
    print(f"fetch_odds: wrote odds.json ({len(out)} fixtures)")


if __name__ == "__main__":
    run()
