"""Extract match referees from ESPN summaries (gameInfo.officials) and merge them into
data/referee_matches.csv, synced by event_id. Fills refs the harvest never captured
(e.g. newly-played WC26 matches). Existing rows are preserved; only missing event_ids
are added. Run after harvest, before export_dashboard.
"""
import os, json, glob, unicodedata
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
RAW = os.path.join(DATA, "raw")
REF = os.path.join(DATA, "referee_matches.csv")
IDX = os.path.join(DATA, "events_index.json")


def norm_name(n):
    """ESPN sometimes gives 'Surname, First' — flip to 'First Surname'."""
    n = str(n).strip()
    if "," in n:
        a, b = [x.strip() for x in n.split(",", 1)]
        n = f"{b} {a}"
    return n


def main():
    idx = json.load(open(IDX)) if os.path.exists(IDX) else {}
    tm = pd.read_csv(os.path.join(DATA, "team_matches.csv"))
    agg = tm.groupby("event_id").agg(yc=("yellows_for", "sum"),
                                     rc=("reds_for", "sum"),
                                     fl=("fouls_for", "sum"))
    rows = []
    for f in glob.glob(os.path.join(RAW, "*.json")):
        eid = os.path.splitext(os.path.basename(f))[0]
        try:
            d = json.load(open(f))
        except Exception:
            continue
        offs = d.get("gameInfo", {}).get("officials", []) or []
        ref = next((o.get("fullName") for o in offs
                    if o.get("position", {}).get("name") == "Referee" and o.get("fullName")), None)
        if not ref:
            continue
        meta = idx.get(eid)
        comp = meta[0] if meta else ""
        date = meta[1][:10] if meta and meta[1] else ""
        try:
            a = agg.loc[int(eid)]
            yc, rc, fl = float(a.yc), float(a.rc), float(a.fl)
        except Exception:
            yc = rc = fl = None
        rows.append({"event_id": eid, "comp": comp, "date": date,
                     "referee": norm_name(ref), "yellows": yc, "reds": rc, "fouls": fl})
    new = pd.DataFrame(rows)
    if os.path.exists(REF):
        old = pd.read_csv(REF)
        have = set(old.event_id.astype(str))
        add = new[~new.event_id.astype(str).isin(have)]
        out = pd.concat([old, add], ignore_index=True)
    else:
        add, out = new, new
    out.to_csv(REF, index=False)
    print(f"referees from ESPN officials: {len(new)} matches; added {len(add)} new; "
          f"referee_matches.csv now {len(out)} rows, {out.referee.nunique()} refs")


if __name__ == "__main__":
    main()
