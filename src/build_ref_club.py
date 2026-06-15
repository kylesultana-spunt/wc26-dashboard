"""Build each referee's club-football card tendency from the Transfermarkt player-scores
dump (games.csv = referee per club game, game_events.csv = card events). Refs who are
thin in international data have hundreds of club games, so this gives a far more stable
estimate of how strictly each official controls a match.

Writes data/ref_club_rates.csv: referee, club_games, club_ratio (cards/game vs the club
average; 1.0 = average, >1 = card-happy). RefStats blends this with the international rate.
"""
import os, io, csv, zipfile, unicodedata
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
ZIP = os.path.join(DATA, "tm", "player-scores.zip")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").split())


def main():
    z = zipfile.ZipFile(ZIP)
    # cards per game_id
    cards = Counter()
    with z.open("game_events.csv") as f:
        rd = csv.reader(io.TextIOWrapper(f, "utf-8"))
        hdr = next(rd); gi = hdr.index("game_id"); ti = hdr.index("type")
        for row in rd:
            if len(row) > max(gi, ti) and row[ti] == "Cards":
                cards[row[gi]] += 1
    # referee per game_id  + games per ref
    ref_games = Counter(); ref_cards = Counter(); display = {}
    with z.open("games.csv") as f:
        for r in csv.DictReader(io.TextIOWrapper(f, "utf-8")):
            ref = (r.get("referee") or "").strip()
            if not ref:
                continue
            nn = norm(ref)
            ref_games[nn] += 1
            ref_cards[nn] += cards.get(r["game_id"], 0)
            display.setdefault(nn, ref)
    tot_c = sum(ref_cards.values()); tot_g = sum(ref_games.values())
    mean = tot_c / tot_g
    print(f"club games with ref {tot_g}, mean cards/game {mean:.2f}, refs {len(ref_games)}")
    with open(os.path.join(DATA, "ref_club_rates.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ref_norm", "referee", "club_games", "club_cpg", "club_ratio"])
        for nn, g in sorted(ref_games.items(), key=lambda x: -x[1]):
            cpg = ref_cards[nn] / g
            w.writerow([nn, display[nn], g, round(cpg, 3), round(cpg / mean, 3)])
    print("wrote data/ref_club_rates.csv")


if __name__ == "__main__":
    main()
