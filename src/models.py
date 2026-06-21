"""WC26 betting models: goals (Dixon-Coles-lite), corners/shots/fouls (neg-binomial),
cards (referee-adjusted), player props (per-90 with shrinkage). Monte Carlo unified."""
import os, json
import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
RNG = np.random.default_rng(7)
N_SIM = 20000

# ESPN name -> martj42/results name
ALIASES = {
    "USA": "United States", "South Korea": "South Korea", "Ivory Coast": "Ivory Coast",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Czechia": "Czech Republic",
    "Türkiye": "Turkey", "Cabo Verde": "Cape Verde", "Congo DR": "DR Congo",
    "Chinese Taipei": "Taiwan", "Kyrgyz Republic": "Kyrgyzstan",
    "Brunei Darussalam": "Brunei", "Sao Tome and Principe": "São Tomé and Príncipe",
    "St. Vincent and the Grenadines": "Saint Vincent and the Grenadines",
    "St. Kitts and Nevis": "Saint Kitts and Nevis", "St. Lucia": "Saint Lucia",
    "US Virgin Islands": "United States Virgin Islands",
}
COMP_W = {"fifa.friendly": 0.6, "fifa.world": 1.25, "uefa.euro": 1.2,
          "conmebol.america": 1.2, "caf.nations": 1.1, "afc.asian": 1.1, "concacaf.gold": 1.1}
HALF_LIFE_DAYS = 550.0
CLUB_REF_W = 0.4      # weight on a ref's club-football card tendency (capped at 100 games)
CLUB_REF_CAP = 100

def _decay(dates, ref_date):
    age = (pd.Timestamp(ref_date) - pd.to_datetime(dates)).dt.days.clip(lower=0)
    return np.exp(-np.log(2) * age / HALF_LIFE_DAYS)

def to_results_name(espn_name):
    return ALIASES.get(espn_name, espn_name)

# ---------------- confederations (derived from continental championships) ----------------
_CONFED_CACHE = None
def confed_map():
    global _CONFED_CACHE
    if _CONFED_CACHE is not None:
        return _CONFED_CACHE
    r = pd.read_csv(os.path.join(DATA, "results_all.csv"))
    CONF = {"UEFA Euro": "UEFA", "UEFA Nations League": "UEFA", "Copa América": "CONMEBOL",
            "Gold Cup": "CONCACAF", "CONCACAF Nations League": "CONCACAF",
            "African Cup of Nations": "CAF", "AFC Asian Cup": "AFC",
            "Oceania Nations Cup": "OFC"}
    counts = {}
    for row in r.itertuples():
        for t, c in CONF.items():
            if t in str(row.tournament):
                for team in (row.home_team, row.away_team):
                    counts.setdefault(team, {}).setdefault(c, 0)
                    counts[team][c] += 1
    _CONFED_CACHE = {t: max(d, key=d.get) for t, d in counts.items()}
    return _CONFED_CACHE

def _fit_confed_offsets(obs, alpha=3e-5):
    """obs: list of (eh, ea, hadv, res, ch, ca) from cross-confed WC matches.
    Returns per-confederation Elo offsets (ridge-shrunk MLE, mean-zero)."""
    confs = sorted({c for *_, ch, ca in [(o[0], o[1], o[2], o[3], o[4], o[5]) for o in obs]
                    for c in (ch, ca)})
    if len(obs) < 80 or len(confs) < 3:
        return {}
    idx = {c: i for i, c in enumerate(confs)}
    eh = np.array([o[0] for o in obs]); ea = np.array([o[1] for o in obs])
    hadv = np.array([o[2] for o in obs]); res = np.array([o[3] for o in obs])
    ih = np.array([idx[o[4]] for o in obs]); ia = np.array([idx[o[5]] for o in obs])
    PRIOR_SD = 50.0  # Elo points; shrinks small-sample confeds toward zero
    def nll(o):
        d = (eh + o[ih]) - (ea + o[ia]) + hadv
        p = 1 / (1 + 10 ** (-d / 400))
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return (-np.sum(res * np.log(p) + (1 - res) * np.log(1 - p))
                + np.sum(o ** 2) / (2 * PRIOR_SD ** 2))
    # moment-based starting point: avg (actual - expected) per confed, ~700 Elo/pt
    x0 = np.zeros(len(confs))
    p0 = 1 / (1 + 10 ** (-((eh - ea + hadv) / 400)))
    for c, i in idx.items():
        m_h, m_a = ih == i, ia == i
        n = m_h.sum() + m_a.sum()
        if n:
            x0[i] = 700 * ((res[m_h] - p0[m_h]).sum() + ((1 - res[m_a]) - (1 - p0[m_a])).sum()) / n
    from scipy.optimize import minimize as _min
    o = _min(nll, x0, method="Nelder-Mead",
             options={"maxiter": 6000, "xatol": 0.5, "fatol": 0.01}).x
    o = o - o.mean()
    return dict(zip(confs, o))

# ---------------- Elo (computed from full results history) ----------------
def compute_elo(cutoff=None, cache=True):
    cpath = os.path.join(DATA, "elo_computed_v3.json")
    src_mtime = os.path.getmtime(os.path.join(DATA, "results_all.csv"))
    if cutoff is None and cache and os.path.exists(cpath):
        cached = json.load(open(cpath))
        if cached.get("_src_mtime") == src_mtime:  # stale cache = stale ratings
            return cached
    r = pd.read_csv(os.path.join(DATA, "results_all.csv"))
    r = r[r.date >= "1995-01-01"].dropna(subset=["home_score", "away_score"])
    if cutoff:
        r = r[r.date < cutoff]
    elo = {}
    K = {"FIFA World Cup": 55, "FIFA World Cup qualification": 40, "Friendly": 18}
    cmap = confed_map()
    xobs = []  # cross-confederation World Cup observations for offset fitting
    for row in r.itertuples():
        h, a = row.home_team, row.away_team
        eh, ea = elo.get(h, 1500.0), elo.get(a, 1500.0)
        hadv = 0 if row.neutral else 80
        exp_h = 1 / (1 + 10 ** ((ea - eh - hadv) / 400))
        gd = abs(row.home_score - row.away_score)
        res = 0.5 if gd == 0 else (1.0 if row.home_score > row.away_score else 0.0)
        if (row.tournament == "FIFA World Cup" and row.date >= "2006-01-01"):
            ch, ca = cmap.get(h), cmap.get(a)
            if ch and ca and ch != ca:
                xobs.append((eh, ea, hadv, res, ch, ca))
        k = K.get(row.tournament, 30) * (1 + 0.5 * max(gd - 1, 0) ** 0.8)
        ch, ca = cmap.get(h), cmap.get(a)
        if ch and ca and ch != ca:  # cross-confederation: rare, carries pool alignment.
            # 1.5x validated out-of-sample on WC2022 (2.0x overshoots)
            k *= float(os.environ.get("WC26_XK", "1.5"))
        elo[h] = eh + k * (res - exp_h)
        elo[a] = ea - k * (res - exp_h)
    elo = _anchor_to_official(elo)
    # closed-pool correction — TESTED AND REJECTED: offsets fit on WC 2006-2018
    # made 2022 prediction worse (the confed gap flips between cycles: 2022 was
    # Asia/Africa's tournament). Kept opt-in for future experiments only.
    if os.environ.get("WC26_CONF_OFF"):
        offs = _fit_confed_offsets(xobs)
        if offs:
            elo = {t: v + offs.get(cmap.get(t, ""), 0.0) for t, v in elo.items()}
            elo["_confed_offsets"] = {k: round(v, 1) for k, v in offs.items()}
    if cutoff is None and cache:
        elo["_src_mtime"] = src_mtime
        try:
            json.dump(elo, open(cpath, "w"))
        except OSError:
            pass
    return elo

def _anchor_to_official(elo):
    """My from-scratch Elo compresses gaps (mid-tier teams ~+100 vs elite, validated
    against eloratings.net). Fit linear map mine->official on matched teams, apply to all."""
    npath, wpath = os.path.join(DATA, "elo_names.tsv"), os.path.join(DATA, "elo.tsv")
    if not (os.path.exists(npath) and os.path.exists(wpath)):
        return elo
    code2name = dict(line.rstrip("\n").split("\t")[:2] for line in open(npath) if "\t" in line)
    official = {}
    for line in open(wpath):
        p = line.split("\t")
        if len(p) > 3 and p[2] in code2name:
            official[code2name[p[2]]] = float(p[3])
    both = [(elo[n], official[n]) for n in elo if n in official]
    if len(both) < 50:
        return elo
    x = np.array([b[0] for b in both]); yv = np.array([b[1] for b in both])
    b = np.cov(x, yv)[0, 1] / x.var(); a = yv.mean() - b * x.mean()
    return {k: a + b * v for k, v in elo.items()}

# ---------------- squad values (Transfermarkt top-23 citizenship index) ----------------
_SQV_CACHE = None
def squad_q():
    global _SQV_CACHE
    if _SQV_CACHE is None:
        path = os.path.join(DATA, "squad_values.csv")
        _SQV_CACHE = {}
        if os.path.exists(path):
            for r in pd.read_csv(path).itertuples():
                _SQV_CACHE[(r.team, int(r.year))] = float(r.q)
    return _SQV_CACHE

def sqv_enabled():
    return bool(os.environ.get("WC26_SQV"))

# Owner's judgment call (free fit says ~0; small fixed tilt kept by explicit choice):
# goal-rate multiplier exp(SQV_G * w * qdiff), qdiff in log10 EUR (1.0 = 10x squad value),
# w ramps 0->1 as the Elo gap goes 100->200 ("only where Elo rankings differ a lot").
SQV_G = 0.05
def sqv_weight(elod_abs_100s):
    return min(max(elod_abs_100s - 1.0, 0.0), 1.0)

# ---------------- goals: Poisson rate as function of elo diff ----------------
def fit_goal_curve(elo, cutoff=None):
    """Fit log(goals_for) = a + b*elodiff/100 [+ g*squad_value_diff] since 2018."""
    r = pd.read_csv(os.path.join(DATA, "results_all.csv"))
    r = r[(r.date >= "2018-01-01")].dropna(subset=["home_score", "away_score"])
    if cutoff:
        r = r[r.date < cutoff]
    rows = []
    for row in r.itertuples():
        eh, ea = elo.get(row.home_team), elo.get(row.away_team)
        if eh is None or ea is None:
            continue
        rows.append((row.home_score, (eh - ea) / 100))
        rows.append((row.away_score, (ea - eh) / 100))
    g = np.array([x[0] for x in rows]); d = np.array([x[1] for x in rows])
    def nll(p):
        lam = np.exp(p[0] + p[1] * d)
        return np.sum(lam - g * np.log(lam + 1e-12))
    return minimize(nll, [0.3, 0.1], method="Nelder-Mead").x  # a, b
    # note: free-fitting a squad-value coefficient here returns ~0 (tested);
    # the live SQV_G tilt is the owner's explicit choice, applied in lambdas()

# ---------------- team stat tendencies with shrinkage ----------------
STATS = ["corners", "yellows", "reds", "fouls", "shots", "sot", "goals",
         "offsides", "tackles", "saves"]

def _excluded_eids():
    """Event ids to ignore when fitting the model (extreme mismatch outliers)."""
    import json as _json
    try:
        return set(str(x) for x in _json.load(
            open(os.path.join(DATA, "exclude_matches.json"))).get("event_ids", []))
    except Exception:
        return set()


def _drop_excluded(df):
    eids = _excluded_eids()
    if eids and "event_id" in df.columns:
        return df[~df["event_id"].astype(str).isin(eids)].copy()
    return df


class TeamStats:
    def __init__(self, team_csv=None, asof=None):
        t = _drop_excluded(pd.read_csv(team_csv or os.path.join(DATA, "team_matches.csv")))
        t["date"] = pd.to_datetime(t["date"])
        if asof:
            t = t[t["date"] < pd.Timestamp(asof)]
        self.asof = asof or pd.Timestamp.now().strftime("%Y-%m-%d")
        t["w"] = t["comp"].map(COMP_W).fillna(1.0) * _decay(t["date"], self.asof)
        self.t = t
        self.means, self.disp = {}, {}
        for s in STATS:
            col = t[f"{s}_for"].dropna()
            self.means[s] = float(np.average(t.loc[col.index, f"{s}_for"], weights=t.loc[col.index, "w"]))
            m, v = col.mean(), col.var()
            self.disp[s] = float(max((v - m), 1e-9) / m**2) if v > m else 0.0  # NB alpha
        # elo-gap multiplier for corners/shots/sot (favourites generate more)
        self.elo_beta = {}
        elo = compute_elo()
        sub = t.dropna(subset=["corners_for"]).copy()
        sub["elod"] = [
            (elo.get(to_results_name(a), 1500) - elo.get(to_results_name(b), 1500)) / 100
            for a, b in zip(sub.team, sub.opponent)]
        # first-half shares (for HT markets)
        g1 = t.dropna(subset=["goals_1h_for"])
        self.p1h_goals = float(g1.goals_1h_for.sum() / max(g1.goals_for.sum(), 1))
        c1 = t.dropna(subset=["cards_1h_for", "yellows_for"])
        self.p1h_cards = float(c1.cards_1h_for.sum() /
                               max((c1.yellows_for + c1.reds_for.fillna(0)).sum(), 1))
        for s in ["corners", "shots", "sot", "fouls", "yellows", "offsides", "tackles", "saves"]:
            y = sub[f"{s}_for"].values; d = sub["elod"].values; mask = ~np.isnan(y)
            y, d = y[mask], d[mask]
            def nll(p, y=y, d=d):
                lam = np.exp(p[0] + p[1] * d)
                return np.sum(lam - y * np.log(lam + 1e-12))
            self.elo_beta[s] = float(minimize(nll, [np.log(self.means[s]), 0.0],
                                              method="Nelder-Mead").x[1])
        self._fit_conditional_dispersion(elo)

    def _fit_conditional_dispersion(self, elo):
        """Replace pooled dispersion with residual dispersion given model-predicted means.
        Pooled variance counts between-matchup mean differences as randomness, which
        fattens the tails and squashes over/under probabilities toward 50%."""
        from scipy.optimize import minimize_scalar
        from scipy.special import gammaln
        t = self.t
        elod = np.array([(elo.get(to_results_name(x), 1500) -
                          elo.get(to_results_name(o), 1500)) / 100
                         for x, o in zip(t.team, t.opponent)])
        for s in [x for x in STATS if x != "goals"]:
            col, aga = f"{s}_for", f"{s}_against"
            d = t.dropna(subset=[col])
            if len(d) < 300:
                continue
            # vectorised shrunk factors (same formula as factor(), k=8)
            k = 8.0
            f_for, f_aga = {}, {}
            for side, store in ((col, f_for), (aga, f_aga)):
                dd = t.dropna(subset=[side])
                gb = dd.assign(ws=dd[side] * dd.w).groupby("team")[["ws", "w"]].sum()
                rate = (gb.ws / gb.w) / max(self.means[s], 1e-9)
                store.update((((gb.w * rate + k) / (gb.w + k))).to_dict())
            beta = self.elo_beta.get(s, 0.0)
            mu = (self.means[s]
                  * d.team.map(f_for).fillna(1.0).values
                  * d.opponent.map(f_aga).fillna(1.0).values
                  * np.exp(beta * elod[d.index.map(
                      dict(zip(t.index, range(len(t)))))].astype(float)))
            y = d[col].values
            mu = np.maximum(mu * (y.mean() / mu.mean()), 1e-6)  # remove aggregate bias
            # NB1 dispersion (variance = phi * mean): pick phi that best predicts actual
            # over/under outcomes (min Brier). NB2 (var ~ mean^2) over-fattens blowout tails.
            from scipy.stats import nbinom as _nb, poisson as _po
            lines = np.unique(np.round(np.quantile(y, [0.3, 0.5, 0.7, 0.85])) - 0.5)
            lines = lines[lines > 0]
            best, best_phi = np.inf, 1.0
            for phi in np.linspace(1.0, 4.0, 31):
                sc = 0.0
                for ln in lines:
                    if phi <= 1.0 + 1e-9:
                        pr = _po.sf(int(ln), mu)
                    else:
                        r = mu / (phi - 1.0)
                        pr = _nb.sf(int(ln), r, 1.0 / phi)
                    sc += np.mean((pr - (y > ln)) ** 2)
                if sc < best:
                    best, best_phi = sc, phi
            self.disp[s] = float(best_phi)  # NB1 phi (1.0 = Poisson)

    def factor(self, team, stat, side, k=8.0):
        """Shrunk multiplicative tendency. side='for' or 'against'."""
        rows = self.t[(self.t.team == team)].dropna(subset=[f"{stat}_{side}"])
        if len(rows) == 0:
            return 1.0, 0
        w = rows["w"].values
        rate = np.average(rows[f"{stat}_{side}"], weights=w) / max(self.means[stat], 1e-9)
        n_eff = w.sum()
        return float((n_eff * rate + k) / (n_eff + k)), len(rows)

# ---------------- referee ----------------
class RefStats:
    def __init__(self, asof=None):
        r = _drop_excluded(pd.read_csv(os.path.join(DATA, "referee_matches.csv")).dropna(subset=["referee", "yellows"]))
        if asof:
            r = r[r["date"] < asof]
        self.r = r
        self.mean_yc = r["yellows"].mean()
        # club-football card tendency per ref (much bigger sample than internationals)
        self.club = {}
        cp = os.path.join(DATA, "ref_club_rates.csv")
        if os.path.exists(cp):
            import csv as _csv
            for row in _csv.DictReader(open(cp)):
                self.club[row["ref_norm"]] = (float(row["club_ratio"]), int(row["club_games"]))

    @staticmethod
    def _norm(s):
        import unicodedata
        s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
        return " ".join(s.replace("-", " ").split())

    def multiplier(self, ref, k=10.0):
        if not ref:
            return 1.0, 0
        rows = self.r[self.r.referee.str.lower() == ref.lower()]
        n = len(rows)
        num, den = 0.0, 0.0
        if n:
            num += n * (rows["yellows"].mean() / self.mean_yc); den += n
        cr = self.club.get(self._norm(ref))
        if cr:
            w = CLUB_REF_W * min(cr[1], CLUB_REF_CAP)   # club strictness (capped sample)
            num += w * cr[0]; den += w
        if den == 0:
            return 1.0, 0
        return float((num + k) / (den + k)), n + (cr[1] if cr else 0)

# ---------------- player ----------------
class PlayerStats:
    PSTATS = ["shots", "sot", "fouls_committed", "fouls_suffered", "yellows", "goals",
              "assists", "saves"]

    def __init__(self, asof=None):
        p = _drop_excluded(pd.read_csv(os.path.join(DATA, "player_matches.csv")))
        p["date"] = pd.to_datetime(p["date"])
        if asof:
            p = p[p["date"] < pd.Timestamp(asof)]
        p = p[p["minutes_est"] > 0]
        self.asof = asof or pd.Timestamp.now().strftime("%Y-%m-%d")
        p["w"] = p["comp"].map(COMP_W).fillna(1.0) * _decay(p["date"], self.asof)
        self.p = p
        self.pos_means = {}
        for s in self.PSTATS:
            per90 = p[s] / p["minutes_est"] * 90
            self.pos_means[s] = per90.groupby(p["position"]).mean().to_dict()
            self.pos_means[s]["_all"] = float(per90.mean())

    CLUB_W = 0.25       # validated 2026-06-13 on 10.5k held-out intl appearances
    CLUB_COL = {"yellows": "club_yc90", "goals": "club_g90", "assists": "club_a90"}

    def _club(self):
        if not hasattr(self, "_club_df"):
            path = os.path.join(DATA, "club_rates.csv")
            self._club_df = (pd.read_csv(path).set_index("nname")
                             if os.path.exists(path) else None)
        return self._club_df

    # ESPN club gamelog: per-appearance fouls/shots from a player's full club season —
    # a much larger sample than national caps for these markets. Blended like the TM club data.
    ECLUB_W = 0.6        # weight per club game, capped at 40 games
    ECLUB_COL = {"fouls_committed": "fc_pg", "fouls_suffered": "fa_pg",
                 "shots": "shots_pg", "sot": "sot_pg"}

    def _eclub(self):
        if not hasattr(self, "_eclub_df"):
            path = os.path.join(DATA, "player_club_rates.csv")
            if os.path.exists(path):
                df = pd.read_csv(path)
                self._eclub_df = {(r.team, r.nname): r for r in df.itertuples()}
            else:
                self._eclub_df = None
        return self._eclub_df

    def per90(self, player, team, stat, k=6.0):
        import unicodedata
        rows = self.p[(self.p.player == player) & (self.p.team == team)]
        pos = rows["position"].mode().iloc[0] if len(rows) else None
        prior = self.pos_means[stat].get(pos, self.pos_means[stat]["_all"])
        num, den = 0.0, 0.0
        if len(rows):
            w = rows["w"].values
            mins = rows["minutes_est"].values
            rate = np.average(rows[stat] / mins * 90, weights=w * mins / 90)
            n_eff = (w * mins / 90).sum()
            num, den = n_eff * rate, n_eff
        cdf = self._club()
        if cdf is not None and stat in self.CLUB_COL:
            nn = unicodedata.normalize("NFKD", str(player)).encode("ascii", "ignore").decode().lower()
            nn = " ".join(nn.replace("-", " ").split())
            if nn in cdf.index:
                c = cdf.loc[nn]
                ce = self.CLUB_W * float(c["mins"]) / 90.0
                num += ce * float(c[self.CLUB_COL[stat]])
                den += ce
        edf = self._eclub()
        if edf is not None and stat in self.ECLUB_COL:
            nnp = unicodedata.normalize("NFKD", str(player)).encode("ascii", "ignore").decode().lower()
            nnp = " ".join(nnp.replace("-", " ").split())
            rec = edf.get((team, nnp))
            if rec is not None:
                ce = self.ECLUB_W * min(float(rec.games), 40.0)
                num += ce * float(getattr(rec, self.ECLUB_COL[stat]))
                den += ce
        if den == 0:
            return prior, 0, 75.0
        shrunk = (num + k * prior) / (den + k)
        avg_min_start = (rows[rows.starter]["minutes_est"].mean()
                         if len(rows) and rows.starter.any() else 70.0)
        return float(shrunk), len(rows), float(avg_min_start)

# ---------------- match simulation ----------------
STAGE_CARD_MULT = {"group": 1.0, "r32": 1.08, "r16": 1.1, "qf": 1.15, "sf": 1.15, "final": 1.2}

def nb_draw(mean, phi, n=N_SIM):
    """NB1: variance = phi * mean. phi <= 1 collapses to Poisson."""
    if phi <= 1.0 + 1e-9 or mean <= 0:
        return RNG.poisson(max(mean, 1e-9), n)
    r_ = mean / (phi - 1.0)
    return RNG.negative_binomial(r_, 1.0 / phi, n)

def load_tempo():
    """Tournament-tempo multipliers from completed WC26 matches (1.0 = neutral).
    Skipped for historical/backtest runs and when disabled."""
    if os.environ.get("WC26_NO_TEMPO"):
        return {}
    p = os.path.join(DATA, "tempo.json")
    if os.path.exists(p):
        return json.load(open(p))
    return {}

class MatchModel:
    def __init__(self, asof=None, team_csv=None):
        self.ts = TeamStats(team_csv=team_csv, asof=asof)
        self.rs = RefStats(asof=asof)
        self.elo = compute_elo(cutoff=asof, cache=asof is None)
        self.gc = fit_goal_curve(self.elo, cutoff=asof)
        # tempo only for live (non-historical) predictions
        self.tempo = load_tempo() if asof is None else {}

    def lambdas(self, home, away, ref=None, stage="group", rivalry=False):
        rh, ra = to_results_name(home), to_results_name(away)
        eh, ea = self.elo.get(rh, 1500), self.elo.get(ra, 1500)
        a, b = self.gc[0], self.gc[1]
        yr = int(pd.Timestamp.now().year)
        q = squad_q()
        qh, qa = q.get((rh, yr)), q.get((ra, yr))
        qd0 = (qh - qa) if (qh is not None and qa is not None) else 0.0
        w = sqv_weight(abs(eh - ea) / 100)
        out = {}
        # goals: elo curve + owner's small squad-value tilt in big-gap matchups
        for me, you, d, qd in ((home, away, (eh - ea) / 100, qd0),
                               (away, home, (ea - eh) / 100, -qd0)):
            base = np.exp(a + b * d + SQV_G * w * qd)
            att, _ = self.ts.factor(me, "goals", "for")
            dfn, _ = self.ts.factor(you, "goals", "against")
            out.setdefault("goals", {})[me] = (base * (att * dfn) ** 0.5
                                               * self.tempo.get("goals", 1.0))
        ref_mult, ref_n = self.rs.multiplier(ref)
        stage_m = STAGE_CARD_MULT.get(stage, 1.0) * (1.2 if rivalry else 1.0)
        for s in ["corners", "shots", "sot", "fouls", "yellows", "reds",
                  "offsides", "tackles", "saves"]:
            out[s] = {}
            beta = self.ts.elo_beta.get(s, 0.0)
            for me, you, d in ((home, away, (eh - ea) / 100), (away, home, (ea - eh) / 100)):
                f, _ = self.ts.factor(me, s, "for")
                g, _ = self.ts.factor(you, s, "against")
                lam = self.ts.means[s] * f * g * np.exp(beta * d) / np.exp(beta * 0)
                if s in ("yellows", "reds"):
                    lam *= ref_mult * stage_m
                lam *= self.tempo.get(s, 1.0)
                out[s][me] = float(lam)
        out["_meta"] = {"elo": {home: eh, away: ea}, "ref_mult": ref_mult, "ref_n": ref_n}
        return out

    def simulate(self, home, away, stat_mult=None, **kw):
        lam = self.lambdas(home, away, **kw)
        if stat_mult:                       # lineup-aware tilt: scale a stat's rate per team
            for s, perteam in stat_mult.items():
                if s in lam:
                    for t, mlt in perteam.items():
                        if t in lam[s]:
                            lam[s][t] *= mlt
        sims = {}
        for s in ["goals", "corners", "shots", "sot", "fouls", "yellows", "reds",
                  "offsides", "tackles", "saves"]:
            phi = 1.0 if s == "goals" else self.ts.disp.get(s, 1.0)
            sims[s] = {t: nb_draw(lam[s][t], phi) for t in (home, away)}
        # first-half thinning
        sims["goals_1h"] = {t: RNG.binomial(sims["goals"][t], self.ts.p1h_goals)
                            for t in (home, away)}
        cards = {t: sims["yellows"][t] + sims["reds"][t] for t in (home, away)}
        sims["cards_1h"] = {t: RNG.binomial(cards[t], self.ts.p1h_cards) for t in (home, away)}
        return lam, sims

def market_family(key):
    """Map a market key to its calibration family (matches backtest.py grouping)."""
    k = key or ""
    if any(k.startswith(x) for x in ("result", "double_chance", "dnb", "win_margin",
                                     "score_", "ht_score", "htft", "half_most")):
        return "result"
    if ("goals" in k) or ("btts" in k) or ("goal_both" in k):
        return "goals"
    if "corners" in k:
        return "corners"
    if "cards" in k:
        return "cards"
    if "offsides" in k:
        return "offsides"
    if "tackles" in k:
        return "tackles"
    if "saves" in k:
        return "saves"
    if ("shots" in k) or ("sot" in k):
        return "shots"
    return "fouls"


def market_probs(sims, home, away):
    """Compute probabilities for the standard market menu."""
    out = {}
    g_h, g_a = sims["goals"][home], sims["goals"][away]
    tot = g_h + g_a
    for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
        out[f"goals_over_{line}"] = float((tot > line).mean())
        out[f"goals_under_{line}"] = float((tot < line).mean())
    out["btts_yes"] = float(((g_h > 0) & (g_a > 0)).mean())
    out["btts_no"] = 1 - out["btts_yes"]
    for t, g in ((home, g_h), (away, g_a)):
        for line in [0.5, 1.5, 2.5]:
            out[f"team_goals_{t}_over_{line}"] = float((g > line).mean())
    c_h, c_a = sims["corners"][home], sims["corners"][away]
    ct = c_h + c_a
    for line in [7.5, 8.5, 9.5, 10.5, 11.5]:
        out[f"corners_over_{line}"] = float((ct > line).mean())
        out[f"corners_under_{line}"] = float((ct < line).mean())
    for t, c in ((home, c_h), (away, c_a)):
        for line in [2.5, 3.5, 4.5, 5.5]:
            out[f"team_corners_{t}_over_{line}"] = float((c > line).mean())
    y_h, y_a = sims["yellows"][home], sims["yellows"][away]
    r_h, r_a = sims["reds"][home], sims["reds"][away]
    cards = y_h + y_a + r_h + r_a
    for line in [2.5, 3.5, 4.5, 5.5]:
        out[f"cards_over_{line}"] = float((cards > line).mean())
        out[f"cards_under_{line}"] = float((cards < line).mean())
    for t, y, r in ((home, y_h, r_h), (away, y_a, r_a)):
        for line in [0.5, 1.5, 2.5]:
            out[f"team_cards_{t}_over_{line}"] = float(((y + r) > line).mean())
    s_h, s_a = sims["shots"][home], sims["shots"][away]
    st_h, st_a = sims["sot"][home], sims["sot"][away]
    for t, s_, st_ in ((home, s_h, st_h), (away, s_a, st_a)):
        for line in [8.5, 10.5, 12.5]:
            out[f"team_shots_{t}_over_{line}"] = float((s_ > line).mean())
        for line in [2.5, 3.5, 4.5]:
            out[f"team_sot_{t}_over_{line}"] = float((st_ > line).mean())
    for line in [20.5, 22.5, 24.5, 26.5]:
        out[f"shots_over_{line}"] = float(((s_h + s_a) > line).mean())
        out[f"shots_under_{line}"] = float(((s_h + s_a) < line).mean())
    for line in [5.5, 6.5, 7.5, 8.5]:
        out[f"sot_over_{line}"] = float(((st_h + st_a) > line).mean())
        out[f"sot_under_{line}"] = float(((st_h + st_a) < line).mean())
    f_h, f_a = sims["fouls"][home], sims["fouls"][away]
    for line in [19.5, 21.5, 23.5]:
        out[f"fouls_over_{line}"] = float(((f_h + f_a) > line).mean())
        out[f"fouls_under_{line}"] = float(((f_h + f_a) < line).mean())
    # --- result family (from goals sims) ---
    out[f"result_{home}"] = float((g_h > g_a).mean())
    out["result_draw"] = float((g_h == g_a).mean())
    out[f"result_{away}"] = float((g_h < g_a).mean())
    out[f"double_chance_{home}_draw"] = out[f"result_{home}"] + out["result_draw"]
    out[f"double_chance_{away}_draw"] = out[f"result_{away}"] + out["result_draw"]
    out[f"double_chance_{home}_{away}"] = out[f"result_{home}"] + out[f"result_{away}"]
    nd = out[f"result_{home}"] + out[f"result_{away}"]
    if nd > 0:
        out[f"dnb_{home}"] = out[f"result_{home}"] / nd
        out[f"dnb_{away}"] = out[f"result_{away}"] / nd
    for t, m in ((home, g_h - g_a), (away, g_a - g_h)):
        out[f"win_margin_{t}_1"] = float((m == 1).mean())
        out[f"win_margin_{t}_2"] = float((m == 2).mean())
        out[f"win_margin_{t}_3plus"] = float((m >= 3).mean())
    # correct scores (common)
    for i in range(5):
        for j in range(5):
            p = float(((g_h == i) & (g_a == j)).mean())
            if p >= 0.02:
                out[f"score_{i}_{j}"] = p
    # goals ranges
    for lo, hi, name in [(0, 1, "0_1"), (2, 3, "2_3"), (2, 4, "2_4"), (1, 3, "1_3")]:
        out[f"goals_range_{name}"] = float(((tot >= lo) & (tot <= hi)).mean())
    out["goals_4plus"] = float((tot >= 4).mean())
    for t, g in ((home, g_h), (away, g_a)):
        out[f"team_goals_range_{t}_0_1"] = float((g <= 1).mean())
        out[f"team_goals_range_{t}_2plus"] = float((g >= 2).mean())
    # --- 1st / 2nd half ---
    h1 = sims["goals_1h"][home] + sims["goals_1h"][away]
    h2 = tot - h1
    for line in [0.5, 1.5, 2.5]:
        out[f"goals_1h_over_{line}"] = float((h1 > line).mean())
        out[f"goals_1h_under_{line}"] = float((h1 < line).mean())
        out[f"goals_2h_over_{line}"] = float((h2 > line).mean())
    out["goal_both_halves"] = float(((h1 > 0) & (h2 > 0)).mean())
    out["half_most_goals_1h"] = float((h1 > h2).mean())
    out["half_most_goals_2h"] = float((h2 > h1).mean())
    out["half_most_goals_tie"] = float((h1 == h2).mean())
    gh1_h, gh1_a = sims["goals_1h"][home], sims["goals_1h"][away]
    for i in range(3):
        for j in range(3):
            p = float(((gh1_h == i) & (gh1_a == j)).mean())
            if p >= 0.03:
                out[f"ht_score_{i}_{j}"] = p
    # HT/FT
    for htr, htm in (("H", gh1_h > gh1_a), ("D", gh1_h == gh1_a), ("A", gh1_h < gh1_a)):
        for ftr, ftm in (("H", g_h > g_a), ("D", g_h == g_a), ("A", g_h < g_a)):
            out[f"htft_{htr}{ftr}"] = float((htm & ftm).mean())
    c1 = sims["cards_1h"][home] + sims["cards_1h"][away]
    for line in [0.5, 1.5, 2.5]:
        out[f"cards_1h_over_{line}"] = float((c1 > line).mean())
        out[f"cards_1h_under_{line}"] = float((c1 < line).mean())
    # --- corners 3-way + alternative ---
    for n in range(4, 13):
        out[f"corners_3w_over_{n}"] = float((ct > n).mean())
        out[f"corners_3w_exactly_{n}"] = float((ct == n).mean())
        out[f"corners_3w_under_{n}"] = float((ct < n).mean())
    out[f"most_corners_{home}"] = float((c_h > c_a).mean())
    out[f"most_corners_{away}"] = float((c_a > c_h).mean())
    out["most_corners_tie"] = float((c_h == c_a).mean())
    # --- cards extras ---
    tc_h, tc_a = y_h + r_h, y_a + r_a
    out["btt_cards_yes"] = float(((tc_h > 0) & (tc_a > 0)).mean())
    out["btt_cards_no"] = 1 - out["btt_cards_yes"]
    out[f"most_cards_{home}"] = float((tc_h > tc_a).mean())
    out[f"most_cards_{away}"] = float((tc_a > tc_h).mean())
    out["most_cards_tie"] = float((tc_h == tc_a).mean())
    out["red_card_yes"] = float(((r_h + r_a) > 0).mean())
    out["red_card_no"] = 1 - out["red_card_yes"]
    for line in [1.5, 6.5, 7.5]:
        out[f"cards_over_{line}"] = float((cards > line).mean())
        out[f"cards_under_{line}"] = float((cards < line).mean())
    # --- offsides / tackles / saves ---
    o_h, o_a = sims["offsides"][home], sims["offsides"][away]
    for line in [1.5, 2.5, 3.5, 4.5]:
        out[f"offsides_over_{line}"] = float(((o_h + o_a) > line).mean())
        out[f"offsides_under_{line}"] = float(((o_h + o_a) < line).mean())
    # tackles markets dropped: failed backtest (59% hit at 72%+ claimed — data too noisy)
    sv_h, sv_a = sims["saves"][home], sims["saves"][away]
    for t, sv in ((home, sv_h), (away, sv_a)):
        for line in [1.5, 2.5, 3.5, 4.5]:
            out[f"gk_saves_{t}_over_{line}"] = float((sv > line).mean())
    return out

def player_prop_probs(ps: PlayerStats, mm: MatchModel, player, team, opponent,
                      ref=None, starter=True, minutes=None):
    """Poisson probs for player shots/SoT/fouls + booking."""
    out = {}
    eo = mm.elo.get(to_results_name(opponent), 1500)
    et = mm.elo.get(to_results_name(team), 1500)
    d = (et - eo) / 100
    from scipy.stats import poisson
    lams = {}
    for stat, lines in (("shots", [0.5, 1.5, 2.5, 3.5, 4.5]), ("sot", [0.5, 1.5, 2.5, 3.5]),
                        ("fouls_committed", [0.5, 1.5, 2.5]), ("fouls_suffered", [0.5, 1.5, 2.5]),
                        ("goals", [0.5, 1.5]), ("assists", [0.5]), ("saves", [1.5, 2.5, 3.5, 4.5])):
        rate, n, avgmin = ps.per90(player, team, stat)
        mins = minutes or (avgmin if starter else 30.0)
        beta = mm.ts.elo_beta.get("shots", 0.06) if stat in ("shots", "sot", "goals", "assists") else 0.0
        if stat == "saves":  # keeper workload scales with OPPONENT attack strength
            beta = -abs(mm.ts.elo_beta.get("sot", 0.06))
        lam = rate * mins / 90 * np.exp(beta * d)
        lams[stat] = lam
        for line in lines:
            out[f"{player}_{stat}_over_{line}"] = float(1 - poisson.cdf(int(line), lam))
        out[f"_{stat}_matches"] = n
    out[f"{player}_score_or_assist"] = float(1 - np.exp(-(lams["goals"] + lams["assists"])))
    yc_rate, n, avgmin = ps.per90(player, team, "yellows")
    mins = minutes or (avgmin if starter else 30.0)
    ref_mult, _ = mm.rs.multiplier(ref)
    lam = yc_rate * mins / 90 * ref_mult
    out[f"{player}_to_be_booked"] = float(1 - np.exp(-lam))
    return out
