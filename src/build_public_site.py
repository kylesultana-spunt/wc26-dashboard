"""Build the public Statz-style static site from site_data/*.json.

Outputs to site/:
  index.html              homepage (hero, fixtures, results, group tables, favourites)
  match/<eid>.html        per-fixture page (slip builder, expected stats, market browser)
  assets/site.css         shared dark-violet theme (matches the dashboard palette)
  assets/site.js          shared helpers (flags, odds, labels) + homepage logic
  assets/match.js         match-page logic (slip builder + market browser)

Run:  python3 src/build_public_site.py   (after build_predictions.py)
The site is 100% static — open site/index.html or host the folder anywhere.
"""
import json, os, sys, html

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "site_data")
SITE = os.path.join(HERE, "..", "site")
ASSETS = os.path.join(SITE, "assets")
MATCHDIR = os.path.join(SITE, "match")

BRAND = "PITCHIQ"          # <- change this one line to rename the site
TAGLINE = "Model-priced World Cup 2026 — every market, every match, fully backtested."

# Verified credibility numbers (from README / BETTING_VALIDATION / CALIBRATION_REVIEW)
STATS = [
    ("81.2%", "hit rate at the 72%+ bet rule"),
    ("22,700", "held-out market predictions"),
    ("104", "World Cup 2026 fixtures covered"),
    ("450+", "priced markets per match"),
]

GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Bosnia-Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Türkiye"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "Congo DR", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}
TEAM_GROUP = {t: g for g, ts in GROUPS.items() for t in ts}

FLAGS = {
    "Mexico": "🇲🇽", "South Africa": "🇿🇦", "South Korea": "🇰🇷", "Czechia": "🇨🇿",
    "Canada": "🇨🇦", "Bosnia-Herzegovina": "🇧🇦", "Qatar": "🇶🇦", "Switzerland": "🇨🇭",
    "Brazil": "🇧🇷", "Morocco": "🇲🇦", "Haiti": "🇭🇹", "Scotland": "🏴\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F",
    "United States": "🇺🇸", "Paraguay": "🇵🇾", "Australia": "🇦🇺", "Türkiye": "🇹🇷",
    "Germany": "🇩🇪", "Curaçao": "🇨🇼", "Ivory Coast": "🇨🇮", "Ecuador": "🇪🇨",
    "Netherlands": "🇳🇱", "Japan": "🇯🇵", "Sweden": "🇸🇪", "Tunisia": "🇹🇳",
    "Belgium": "🇧🇪", "Egypt": "🇪🇬", "Iran": "🇮🇷", "New Zealand": "🇳🇿",
    "Spain": "🇪🇸", "Cape Verde": "🇨🇻", "Saudi Arabia": "🇸🇦", "Uruguay": "🇺🇾",
    "France": "🇫🇷", "Senegal": "🇸🇳", "Iraq": "🇮🇶", "Norway": "🇳🇴",
    "Argentina": "🇦🇷", "Algeria": "🇩🇿", "Austria": "🇦🇹", "Jordan": "🇯🇴",
    "Portugal": "🇵🇹", "Congo DR": "🇨🇩", "Uzbekistan": "🇺🇿", "Colombia": "🇨🇴",
    "England": "🏴\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F", "Croatia": "🇭🇷", "Ghana": "🇬🇭", "Panama": "🇵🇦",
}

# ---------------------------------------------------------------- CSS
CSS = r"""
:root{
  --bg:#0b0a12; --panel:#15121f; --panel2:#201a33; --line:#2c2347;
  --txt:#ece8f6; --dim:#9b93b3; --mag:#d946ef; --vio:#8b5cf6; --pink:#f472b6;
  --green:#22c55e; --greenbg:rgba(34,197,94,.10); --amber:#fbbf24; --red:#f87171;
  --glow:0 0 28px rgba(217,70,239,.20);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:radial-gradient(1200px 600px at 80% -10%,rgba(139,92,246,.18),transparent),
  radial-gradient(900px 500px at 0% 0%,rgba(217,70,239,.12),transparent),var(--bg);
  color:var(--txt);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;min-height:100vh}
a{color:inherit;text-decoration:none}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
.muted{color:var(--dim)}
/* header */
header.nav{position:sticky;top:0;z-index:50;backdrop-filter:blur(12px);
  background:rgba(11,10,18,.72);border-bottom:1px solid var(--line)}
.nav .wrap{display:flex;align-items:center;gap:18px;height:62px}
.brand{font-weight:800;letter-spacing:.5px;font-size:20px;display:flex;align-items:center;gap:9px}
.brand .dot{width:11px;height:11px;border-radius:50%;background:var(--mag);box-shadow:var(--glow)}
.brand small{font-weight:600;color:var(--dim);font-size:11px;letter-spacing:2px;border:1px solid var(--line);
  padding:2px 7px;border-radius:20px}
.nav a.link{color:var(--dim);font-weight:600;font-size:14px}
.nav a.link:hover{color:var(--txt)}
.nav .spacer{flex:1}
/* hero */
.hero{padding:54px 0 30px}
.hero h1{font-size:40px;line-height:1.08;margin:0 0 14px;font-weight:800;max-width:760px}
.hero h1 .g{background:linear-gradient(90deg,var(--mag),var(--vio));-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p.sub{font-size:17px;color:var(--dim);max-width:620px;margin:0 0 26px}
.statgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:8px 0 6px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.stat b{display:block;font-size:26px;font-weight:800;color:var(--txt)}
.stat span{font-size:12.5px;color:var(--dim)}
/* sections */
section{padding:30px 0}
.h{display:flex;align-items:baseline;gap:12px;margin:0 0 16px}
.h h2{font-size:22px;margin:0;font-weight:800}
.h .muted{font-size:13px}
/* fixture cards */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.fx{display:block;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;
  transition:transform .12s,border-color .12s,box-shadow .12s}
.fx:hover{transform:translateY(-2px);border-color:var(--mag);box-shadow:var(--glow)}
.fx .top{display:flex;justify-content:space-between;align-items:center;font-size:11.5px;color:var(--dim);margin-bottom:10px}
.fx .grp{border:1px solid var(--line);border-radius:20px;padding:1px 8px;font-weight:700;color:var(--vio)}
.fx .teams{display:flex;flex-direction:column;gap:7px}
.fx .row{display:flex;align-items:center;gap:9px;font-weight:700;font-size:15.5px}
.fx .row .fl{font-size:19px;width:24px;text-align:center}
.fx .row .sc{margin-left:auto;font-variant-numeric:tabular-nums;color:var(--dim);font-weight:800}
.fx .pick{margin-top:11px;border-top:1px solid var(--line);padding-top:9px;font-size:12.5px;color:var(--dim)}
.fx .pick b{color:var(--pink);font-weight:700}
.chip{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;
  border:1px solid var(--line)}
.chip.live{color:var(--green);border-color:rgba(34,197,94,.4);background:var(--greenbg)}
.chip.done{color:var(--dim)}
/* tables / groups / favourites */
.gwrap{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.gtab{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.gtab h4{margin:0 0 8px;font-size:13px;color:var(--vio);letter-spacing:1px}
.gtab table{width:100%;border-collapse:collapse;font-size:13px}
.gtab td,.gtab th{padding:4px 2px;text-align:left}
.gtab th{color:var(--dim);font-weight:600;font-size:11px}
.gtab td.n{text-align:right;font-variant-numeric:tabular-nums;color:var(--dim)}
.gtab td.pts{color:var(--txt);font-weight:800}
.gtab tr.qual td:first-child{color:var(--green)}
.bar{height:8px;border-radius:5px;background:var(--panel2);overflow:hidden}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--vio),var(--mag))}
.favrow{display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid var(--line)}
.favrow .fl{font-size:20px;width:26px;text-align:center}
.favrow .nm{font-weight:700;width:150px}
.favrow .bar{flex:1}
.favrow .el{width:54px;text-align:right;color:var(--dim);font-variant-numeric:tabular-nums;font-size:13px}
/* footer */
footer{border-top:1px solid var(--line);margin-top:40px;padding:26px 0 50px;color:var(--dim);font-size:12.5px}
footer a{color:var(--vio)}
.rg{margin-top:10px;font-size:11.5px;opacity:.8}
/* ============ match page ============ */
.mhead{padding:30px 0 6px}
.mhead .crumb{font-size:12.5px;color:var(--dim);margin-bottom:14px}
.mhead .crumb a{color:var(--vio)}
.matchup{display:flex;align-items:center;justify-content:center;gap:26px;margin:6px 0 4px}
.matchup .t{display:flex;flex-direction:column;align-items:center;gap:6px;width:200px}
.matchup .t .fl{font-size:46px}
.matchup .t .nm{font-weight:800;font-size:18px;text-align:center}
.matchup .t .el{font-size:12px;color:var(--dim)}
.matchup .mid{text-align:center;min-width:90px}
.matchup .mid .vs{font-size:13px;color:var(--dim);font-weight:700}
.matchup .mid .sc{font-size:34px;font-weight:800;font-variant-numeric:tabular-nums}
.metarow{text-align:center;color:var(--dim);font-size:12.5px;margin:6px 0 4px}
.layout{display:grid;grid-template-columns:1.15fr .85fr;gap:22px;align-items:start;padding-top:18px}
@media(max-width:880px){.layout{grid-template-columns:1fr}.statgrid{grid-template-columns:repeat(2,1fr)}
  .matchup .t{width:120px}.hero h1{font-size:30px}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px 16px}
.panel h3{margin:0 0 12px;font-size:15px;font-weight:800}
/* slip styles tabs */
.styles{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.sty>*{}
.sbtn{display:flex;align-items:center;gap:8px;border:1px solid var(--line);background:var(--panel);
  border-radius:24px;padding:7px 13px;cursor:pointer;font-weight:700;font-size:13px;color:var(--dim);
  transition:all .12s}
.sbtn .od{font-weight:800;color:var(--txt)}
.sbtn.active{border-color:var(--mag);color:var(--txt);box-shadow:var(--glow);background:var(--panel2)}
.sbtn .star{color:var(--amber)}
/* legs */
.slip{}
.sliphead{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.sliphead .legs{font-size:12.5px;color:var(--dim)}
.sliphead .odds{font-size:13px;color:var(--dim)}
.sliphead .odds b{color:var(--txt);font-size:18px}
.leg{display:flex;align-items:center;gap:11px;padding:11px 4px;border-bottom:1px solid var(--line)}
.leg .av{width:34px;height:34px;border-radius:50%;background:var(--panel2);display:flex;align-items:center;
  justify-content:center;font-size:17px;flex:none;border:1px solid var(--line)}
.leg .body{flex:1;min-width:0}
.leg .nm{font-weight:700;font-size:14px;display:flex;align-items:center;gap:7px}
.leg .pos{font-size:10px;font-weight:800;color:var(--vio);border:1px solid var(--line);border-radius:10px;
  padding:0 6px}
.leg .sub{font-size:12px;color:var(--dim);margin-top:2px;display:flex;align-items:center;gap:8px}
.pips{display:flex;gap:3px}
.pip{width:15px;height:15px;border-radius:4px;background:var(--panel2);font-size:9px;font-weight:800;
  display:flex;align-items:center;justify-content:center;color:var(--dim)}
.pip.hit{background:var(--green);color:#06210f}
.leg .od{font-weight:800;font-size:15px;font-variant-numeric:tabular-nums;width:52px;text-align:right}
/* stake box */
.stake{margin-top:14px;background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:13px}
.stake .qk{display:flex;gap:7px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
.stake input{background:var(--bg);border:1px solid var(--line);color:var(--txt);border-radius:9px;
  padding:8px 10px;width:90px;font-size:15px;font-weight:700}
.stake .q{border:1px solid var(--line);border-radius:8px;padding:6px 10px;cursor:pointer;font-size:12.5px;
  color:var(--dim);font-weight:700}
.stake .q:hover{border-color:var(--mag);color:var(--txt)}
.stake .ret{display:flex;justify-content:space-between;align-items:center;font-size:13px;color:var(--dim)}
.stake .ret b{font-size:20px;color:var(--green);font-weight:800}
.bet365{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;margin-top:12px;
  background:linear-gradient(90deg,#1f8a4c,#15803d);color:#fff;font-weight:800;border:none;border-radius:11px;
  padding:13px;font-size:15px;cursor:pointer}
.bet365:hover{filter:brightness(1.07)}
.note{font-size:11px;color:var(--dim);text-align:center;margin-top:8px}
/* expected stats bars */
.exp .erow{margin:11px 0}
.exp .lab{display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:5px}
.exp .lab .l{color:var(--dim);font-weight:700;text-transform:uppercase;letter-spacing:1px;font-size:10.5px}
.exp .ebar{display:flex;height:22px;border-radius:7px;overflow:hidden;background:var(--panel2)}
.exp .ebar .hh{background:linear-gradient(90deg,var(--vio),var(--mag));display:flex;align-items:center;
  padding:0 7px;font-size:11px;font-weight:800;color:#fff}
.exp .ebar .aa{background:var(--panel2);margin-left:auto;display:flex;align-items:center;padding:0 7px;
  font-size:11px;font-weight:800;color:var(--pink);justify-content:flex-end}
.exp .act{font-size:11px;color:var(--dim);margin-top:3px}
.exp .act b{color:var(--amber)}
/* market browser */
.filters{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:12px}
.fchip{border:1px solid var(--line);border-radius:20px;padding:5px 11px;cursor:pointer;font-size:12px;
  font-weight:700;color:var(--dim)}
.fchip.active{border-color:var(--vio);color:var(--txt);background:var(--panel2)}
#msearch{width:100%;background:var(--bg);border:1px solid var(--line);color:var(--txt);border-radius:10px;
  padding:9px 12px;margin-bottom:10px;font-size:13px}
.mkt{display:flex;align-items:center;gap:10px;padding:8px 4px;border-bottom:1px solid var(--line);font-size:13px}
.mkt .k{flex:1;min-width:0}
.mkt .p{width:48px;text-align:right;font-weight:800;font-variant-numeric:tabular-nums}
.mkt .f{width:54px;text-align:right;color:var(--dim);font-variant-numeric:tabular-nums}
.mkt.flagged{background:linear-gradient(90deg,rgba(217,70,239,.10),transparent);border-radius:7px}
.mkt.flagged .p{color:var(--mag)}
.tag{font-size:9.5px;font-weight:800;padding:1px 6px;border-radius:10px;border:1px solid var(--line);color:var(--dim)}
.res{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:5px;
  font-size:11px;font-weight:800;margin-left:6px}
.res.win{background:var(--green);color:#06210f}
.res.lose{background:var(--red);color:#2a0707}
.res.void{background:var(--panel2);color:var(--dim)}
.banner{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:10px 14px;
  margin-bottom:14px;font-size:13px;color:var(--dim)}
.banner b{color:var(--txt)}
/* ============ animations + glow ============ */
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes glowpulse{0%,100%{box-shadow:0 0 12px rgba(217,70,239,.55)}50%{box-shadow:0 0 24px rgba(217,70,239,.95)}}
@keyframes grow{from{width:0}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
.reveal{animation:fadeUp .55s both}
.brand .dot{animation:glowpulse 2.6s ease-in-out infinite}
.bar>i{animation:grow 1.1s cubic-bezier(.2,.8,.2,1) both}
.fx,.stat,.gtab,.teamcard,.orow,.panel,.pp{animation:fadeUp .5s both}
.cards .fx:nth-child(2),.cards .teamcard:nth-child(2){animation-delay:.04s}
.cards .fx:nth-child(3),.cards .teamcard:nth-child(3){animation-delay:.08s}
.cards .fx:nth-child(4),.cards .teamcard:nth-child(4){animation-delay:.12s}
.cards .fx:nth-child(5){animation-delay:.16s}.cards .fx:nth-child(6){animation-delay:.2s}
/* page hero (sub-pages) */
.phead{padding:38px 0 8px}
.phead h1{font-size:30px;margin:0 0 6px;font-weight:800}
.phead p{margin:0;color:var(--dim)}
/* segmented + filter bar */
.toolbar{position:sticky;top:62px;z-index:30;background:rgba(11,10,18,.82);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line);padding:12px 0;margin-bottom:18px}
.toolbar .wrap{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.seg{display:flex;background:var(--panel);border:1px solid var(--line);border-radius:24px;padding:3px}
.seg button{border:none;background:none;color:var(--dim);font-weight:700;font-size:13px;padding:6px 14px;
  border-radius:20px;cursor:pointer}
.seg button.active{background:var(--panel2);color:var(--txt);box-shadow:var(--glow)}
.gchips{display:flex;gap:6px;flex-wrap:wrap}
.gchip{border:1px solid var(--line);border-radius:18px;width:30px;height:30px;display:flex;align-items:center;
  justify-content:center;font-weight:800;font-size:12.5px;color:var(--dim);cursor:pointer;transition:all .12s}
.gchip:hover{color:var(--txt);border-color:var(--vio)}
.gchip.active{border-color:var(--mag);color:var(--txt);background:var(--panel2);box-shadow:var(--glow)}
.gchip.all{width:auto;padding:0 12px}
.srch{flex:1;min-width:160px;background:var(--bg);border:1px solid var(--line);color:var(--txt);
  border-radius:22px;padding:8px 14px;font-size:13px}
.empty{color:var(--dim);padding:30px;text-align:center}
/* date heading in fixtures */
.dhead{grid-column:1/-1;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--vio);
  font-weight:800;margin:14px 0 2px}
/* teams grid */
.teamcard{display:flex;align-items:center;gap:12px;background:var(--panel);border:1px solid var(--line);
  border-radius:14px;padding:13px 15px;transition:transform .12s,border-color .12s,box-shadow .12s}
.teamcard:hover{transform:translateY(-2px);border-color:var(--mag);box-shadow:var(--glow)}
.teamcard .fl{font-size:30px}
.teamcard .nm{font-weight:800}
.teamcard .meta{font-size:11.5px;color:var(--dim)}
.teamcard .gp{margin-left:auto;text-align:right}
.teamcard .gp .el{font-weight:800;font-variant-numeric:tabular-nums}
.teamcard .gp .gr{font-size:11px;color:var(--vio)}
.qbadge{font-size:9.5px;font-weight:800;padding:1px 7px;border-radius:10px;border:1px solid var(--line);color:var(--dim)}
.qbadge.q{color:var(--green);border-color:rgba(34,197,94,.4);background:var(--greenbg)}
/* team profile */
.tphero{display:flex;align-items:center;gap:22px;padding:30px 0 10px;flex-wrap:wrap}
.tphero .big{font-size:74px;line-height:1;filter:drop-shadow(0 0 18px rgba(217,70,239,.35))}
.tphero h1{margin:0;font-size:34px;font-weight:800}
.tphero .sub{color:var(--dim);margin-top:4px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.kpi{display:flex;gap:12px;margin-left:auto;flex-wrap:wrap}
.kpi .k{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 16px;text-align:center}
.kpi .k b{display:block;font-size:22px;font-weight:800}
.kpi .k span{font-size:11px;color:var(--dim)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start;padding-top:14px}
@media(max-width:820px){.cols{grid-template-columns:1fr}.tphero .big{font-size:54px}}
.form{display:flex;gap:6px;margin:4px 0}
.fp{width:26px;height:26px;border-radius:7px;display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:12px}
.fp.W{background:var(--green);color:#06210f}.fp.D{background:var(--panel2);color:var(--dim)}
.fp.L{background:var(--red);color:#2a0707}
.rrow{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13.5px}
.rrow .op{flex:1}.rrow .sc{font-weight:800;font-variant-numeric:tabular-nums}
.pp{display:flex;align-items:center;gap:11px;padding:10px 0;border-bottom:1px solid var(--line)}
.pp .av{width:32px;height:32px;border-radius:50%;background:var(--panel2);border:1px solid var(--line);
  display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;color:var(--vio)}
.pp .nm{font-weight:700;font-size:14px}.pp .st{font-size:11.5px;color:var(--dim)}
.pp .mini{margin-left:auto;width:120px}
.pp .mini .lab{display:flex;justify-content:space-between;font-size:10.5px;color:var(--dim)}
.pp .mini .bar{height:6px;margin-top:3px}
/* outrights */
.orow{display:flex;align-items:center;gap:14px;background:var(--panel);border:1px solid var(--line);
  border-radius:13px;padding:12px 16px;margin-bottom:10px;transition:transform .12s,box-shadow .12s,border-color .12s}
.orow:hover{transform:translateX(3px);border-color:var(--mag);box-shadow:var(--glow)}
.orow .rk{font-size:18px;font-weight:800;color:var(--dim);width:30px}
.orow.top .rk{color:var(--amber)}
.orow .fl{font-size:26px}
.orow .nm{font-weight:800;width:150px}
.orow .bar{flex:1}
.orow .pc{width:62px;text-align:right;font-weight:800;font-variant-numeric:tabular-nums}
.orow .od{width:64px;text-align:right;color:var(--dim);font-variant-numeric:tabular-nums;font-size:13px}
.crosslinks{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}
.clink{border:1px solid var(--line);border-radius:20px;padding:6px 14px;font-weight:700;font-size:13px;
  color:var(--dim);transition:all .12s}
.clink:hover{color:var(--txt);border-color:var(--mag);box-shadow:var(--glow)}
.hide{display:none!important}
"""

# ---------------------------------------------------------------- shared JS
SITE_JS = r"""
const FLAGS = window.__FLAGS__ || {};
const GROUP = window.__GROUP__ || {};
function flag(t){return FLAGS[t]||"⚽";}
function fmtOdds(o){return o.toFixed(2);}
function decToFrac(o){ // crude decimal->fractional for flavour
  const n=o-1; if(n<=0)return "1/1";
  const den=[1,2,3,4,5,6,7,8,9,10,11,12,13,16,20,25];
  let best=[Math.round(n),1],bd=1e9;
  for(const d of den){const num=Math.round(n*d);const err=Math.abs(n-num/d);if(err<bd&&num>0){bd=err;best=[num,d];}}
  return best[0]+"/"+best[1];
}
function kickoff(d){const dt=new Date(d.replace(" ","T"));
  return dt.toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'})+
   " · "+dt.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});}
"""

# ---------------------------------------------------------------- interactive (fixtures + teams)
APP_JS = r"""
// generic card filtering for fixtures.html and teams.html.
// cards carry data-group, data-status, data-team (space-joined names, lowercase).
(function(){
  let G='all', S='all', Q='';
  function apply(){
    const cards=document.querySelectorAll('[data-fcard]');
    let shown=0;
    cards.forEach(c=>{
      const okG = G==='all' || c.dataset.group===G;
      const okS = S==='all' || c.dataset.status===S;
      const okQ = !Q || (c.dataset.team||'').includes(Q);
      const vis = okG&&okS&&okQ;
      c.classList.toggle('hide', !vis); if(vis)shown++;
    });
    // hide date headers with no visible cards under them
    document.querySelectorAll('.dhead').forEach(h=>{
      let n=h.nextElementSibling, any=false;
      while(n && !n.classList.contains('dhead')){ if(n.hasAttribute('data-fcard')&&!n.classList.contains('hide'))any=true; n=n.nextElementSibling;}
      h.classList.toggle('hide',!any);
    });
    const e=document.getElementById('empty'); if(e)e.classList.toggle('hide',shown>0);
  }
  window.__bindFilters=function(){
    document.querySelectorAll('.gchip').forEach(b=>b.onclick=()=>{
      G=b.dataset.g; document.querySelectorAll('.gchip').forEach(x=>x.classList.toggle('active',x===b)); apply();});
    document.querySelectorAll('.seg button').forEach(b=>b.onclick=()=>{
      S=b.dataset.s; document.querySelectorAll('.seg button').forEach(x=>x.classList.toggle('active',x===b)); apply();});
    const s=document.getElementById('srch'); if(s)s.oninput=e=>{Q=e.target.value.toLowerCase().trim(); apply();};
    apply();
  };
})();
document.addEventListener('DOMContentLoaded',()=>window.__bindFilters&&window.__bindFilters());
"""

# ---------------------------------------------------------------- match JS
MATCH_JS = r"""
const FX = window.FX;
const H=FX.home, A=FX.away;

// ---- market label prettifier ----
function titleCase(s){return s.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());}
function labelKey(k){
  // player props: "Name_stat_over_x" / _score_or_assist / _to_be_booked
  const players=(FX.tips||[]).filter(t=>t.player).map(t=>t.player);
  for(const t of (FX.markets||[])){}
  if(k.includes('_over_')||k.endsWith('_score_or_assist')||k.endsWith('_to_be_booked')){
    // detect player name prefix (contains a space + capitalised)
  }
  let m;
  // generic patterns first
  const repl={H:H,A:A};
  if((m=k.match(/^goals_(over|under)_([\d.]+)$/))) return `Total goals ${m[1]} ${m[2]}`;
  if((m=k.match(/^corners_(over|under)_([\d.]+)$/))) return `Total corners ${m[1]} ${m[2]}`;
  if((m=k.match(/^corners_3w_(over|under|exactly)_(\d+)$/))) return `Corners ${m[1]} ${m[2]}`;
  if((m=k.match(/^cards_(over|under)_([\d.]+)$/))) return `Total cards ${m[1]} ${m[2]}`;
  if((m=k.match(/^cards_1h_(over|under)_([\d.]+)$/))) return `1st-half cards ${m[1]} ${m[2]}`;
  if((m=k.match(/^fouls_(over|under)_([\d.]+)$/))) return `Total fouls ${m[1]} ${m[2]}`;
  if((m=k.match(/^shots_(over|under)_([\d.]+)$/))) return `Total shots ${m[1]} ${m[2]}`;
  if((m=k.match(/^sot_(over|under)_([\d.]+)$/))) return `Shots on target ${m[1]} ${m[2]}`;
  if((m=k.match(/^offsides_(over|under)_([\d.]+)$/))) return `Total offsides ${m[1]} ${m[2]}`;
  if((m=k.match(/^goals_(1h|2h)_(over|under)_([\d.]+)$/))) return `${m[1]==='1h'?'1st':'2nd'}-half goals ${m[2]} ${m[3]}`;
  if(k==='btts_yes') return 'Both teams to score – Yes';
  if(k==='btts_no') return 'Both teams to score – No';
  if(k==='btt_cards_yes') return 'Both teams booked – Yes';
  if(k==='red_card_yes') return 'Red card in match – Yes';
  if(k==='goal_both_halves') return 'Goal in both halves';
  if(k==='goals_4plus') return '4+ goals in match';
  if((m=k.match(/^result_(.+)$/))) return (m[1]==='draw'?'Match drawn':titleCase(m[1])+' to win');
  if((m=k.match(/^double_chance_(.+)$/))) return 'Double chance '+m[1].replace(/_/g,' / ');
  if((m=k.match(/^dnb_(.+)$/))) return titleCase(m[1])+' (draw no bet)';
  if((m=k.match(/^win_margin_(.+)_(\d\w*)$/))) return titleCase(m[1])+` by ${m[2].replace('plus','+')}`;
  if((m=k.match(/^score_(\d)_(\d)$/))) return `Correct score ${m[1]}-${m[2]}`;
  if((m=k.match(/^ht_score_(\d)_(\d)$/))) return `Half-time ${m[1]}-${m[2]}`;
  if((m=k.match(/^most_corners_(.+)$/))) return (m[1]==='tie'?'Most corners – Tie':titleCase(m[1])+' most corners');
  if((m=k.match(/^most_cards_(.+)$/))) return (m[1]==='tie'?'Most cards – Tie':titleCase(m[1])+' most cards');
  if((m=k.match(/^team_(corners|cards|goals|shots|sot)_(.+)_over_([\d.]+)$/)))
    return `${m[2]} ${({corners:'corners',cards:'cards',goals:'goals',shots:'shots',sot:'shots on target'})[m[1]]} over ${m[3]}`;
  if((m=k.match(/^team_goals_range_(.+)_(\dplus|\d_\d)$/))) return `${m[1]} ${m[2].replace('plus','+').replace('_','-')} goals`;
  if((m=k.match(/^gk_saves_(.+)_over_([\d.]+)$/))) return `${m[1]} GK saves over ${m[2]}`;
  if((m=k.match(/^(.+)_(shots|sot|goals|assists|saves)_over_([\d.]+)$/)))
    return `${m[1]} ${({shots:'shots',sot:'shots on target',goals:'goals',assists:'assists',saves:'saves'})[m[2]]} ${parseFloat(m[3])+0.5|0}+`.replace(/\b0\+/,'');
  if((m=k.match(/^(.+)_fouls_committed_over_([\d.]+)$/))) return `${m[1]} fouls committed ${Math.ceil(parseFloat(m[2]))}+`;
  if((m=k.match(/^(.+)_fouls_suffered_over_([\d.]+)$/))) return `${m[1]} fouls won ${Math.ceil(parseFloat(m[2]))}+`;
  if((m=k.match(/^(.+)_score_or_assist$/))) return `${m[1]} to score or assist`;
  if((m=k.match(/^(.+)_to_be_booked$/))) return `${m[1]} to be booked`;
  return titleCase(k);
}

// ---- build leg objects for the slip styles ----
const MK = FX.markets;
const byKey = {}; MK.forEach(m=>byKey[m.market]=m);
function over(m){return !/_(under|no)$|_under_/.test(m.market) && !/^cards_under|^goals_under|^corners_under|^sot_under|^shots_under|^fouls_under|^offsides_under/.test(m.market);}
function avatarFor(leg){return leg.player?flag(leg.team):'⚽';}

function legFromTip(t){
  return {name: t.player?t.player:labelKey(t.mk), pos:t.pos||'', sub: t.player?legSub(t):famLabel(t.fam),
          odds:t.fair, fam:t.fam, player:t.player, team:t.team, form:t.form||null, mk:t.mk, p:t.p};
}
function legSub(t){const s=labelKey(t.mk); return s.replace(t.player,'').trim();}
function famLabel(f){return ({fouls:'Fouls',cards:'Cards',corners:'Corners',offsides:'Offsides',
  saves:'Saves',shots:'Shots',goals:'Goals',result:'Match'})[f]||'Market';}
function legFromMk(m){return {name:labelKey(m.market),pos:'',sub:famLabel(m.fam),odds:m.fair,fam:m.fam,
  form:null,mk:m.market,p:m.p};}

function pick(arr,n){return arr.slice(0,n);}
function distinctFam(cands,n){const out=[],seen={};for(const c of cands){const f=c.fam;if((seen[f]||0)>=1)continue;out.push(c);seen[f]=1;if(out.length>=n)break;}
  if(out.length<n){for(const c of cands){if(out.includes(c))continue;out.push(c);if(out.length>=n)break;}}return out;}

const tips=FX.tips||[];
const tPlayers=tips.filter(t=>t.cat==='player');
const tTeam=tips.filter(t=>t.cat==='team');
const tMatch=tips.filter(t=>t.cat==='match');

// strongest balanced acca
const star=[...tips].sort((a,b)=>b.p-a.p);
const SLIPS={};
SLIPS['picks']={icon:'★',legs:distinctFam([...tPlayers,...tTeam].sort((a,b)=>b.p-a.p),4).map(legFromTip)};
// safer: lowest odds overs (high prob) across markets
const safe=MK.filter(over).filter(m=>m.p>=0.74 && m.fair>1.01).sort((a,b)=>a.fair-b.fair);
SLIPS['safer']={icon:'🛡',legs:distinctFam(safe,4).map(legFromMk)};
// long shot: bigger odds legs
const longs=MK.filter(over).filter(m=>m.fair>=3.2 && m.fair<=15 && m.p>0.05).sort((a,b)=>b.fair-a.fair);
SLIPS['long']={icon:'🚀',legs:distinctFam(longs.slice().reverse(),4).map(legFromMk)};
// goals + shots
const gs=[];
['btts_yes','goals_over_1.5','goals_over_2.5'].forEach(k=>{if(byKey[k])gs.push(legFromMk(byKey[k]));});
tPlayers.filter(t=>t.stat==='shots'||t.stat==='sot').slice(0,3).forEach(t=>gs.push(legFromTip(t)));
SLIPS['goals']={icon:'⚽',legs:distinctFam(gs,4)};
// match lines (singles, shown stacked)
const ml=[];
['result_'+H,'result_'+A,'result_draw'].map(k=>byKey[k]).filter(Boolean)
  .sort((a,b)=>b.p-a.p).slice(0,1).forEach(m=>ml.push(legFromMk(m)));
['goals_over_2.5','goals_under_2.5'].map(k=>byKey[k]).filter(Boolean).sort((a,b)=>b.p-a.p).slice(0,1).forEach(m=>ml.push(legFromMk(m)));
if(byKey['btts_yes'])ml.push(legFromMk(byKey['btts_yes']));
if(byKey['double_chance_'+H+'_draw'])ml.push(legFromMk(byKey['double_chance_'+H+'_draw']));
SLIPS['lines']={icon:'≡',legs:ml,singles:true};

const STYLE_META=[['picks',BRAND+' Picks','★'],['safer','Safer Slip','🛡'],
  ['long','Long Shot','🚀'],['goals','Goals + Shots','⚽'],['lines','Match Lines','≡']];

function comboOdds(legs){return legs.reduce((a,l)=>a*l.odds,1);}
let active='picks', stake=10;

function renderStyles(){
  const el=document.getElementById('styles');el.innerHTML='';
  STYLE_META.forEach(([id,label,icon])=>{
    const legs=SLIPS[id].legs; if(!legs.length)return;
    const od=SLIPS[id].singles?Math.max(...legs.map(l=>l.odds)):comboOdds(legs);
    const b=document.createElement('div');b.className='sbtn'+(id===active?' active':'');
    b.innerHTML=`<span class="${icon==='★'?'star':''}">${icon}</span> ${label} <span class="od">@ ${fmtOdds(od)}</span>`;
    b.onclick=()=>{active=id;renderStyles();renderSlip();};el.appendChild(b);
  });
}
function pips(form){if(!form)return '';
  return '<span class="pips">'+form.map(p=>`<span class="pip ${p.hit?'hit':''}">${p.v}</span>`).join('')+'</span>';}
function renderSlip(){
  const S=SLIPS[active], legs=S.legs;
  const od=S.singles?null:comboOdds(legs);
  const wrap=document.getElementById('slip');
  let h='';
  h+=`<div class="sliphead"><span class="legs">${S.singles?legs.length+' single'+(legs.length>1?'s':''):legs.length+' legs'}</span>`;
  h+= S.singles?'<span class="odds muted">best @ <b>'+fmtOdds(Math.max(...legs.map(l=>l.odds)))+'</b></span>'
     :`<span class="odds">combined <b>${fmtOdds(od)}</b></span>`;
  h+='</div>';
  legs.forEach(l=>{
    h+=`<div class="leg"><div class="av">${l.player?flag(l.team):(l.icon||'⚽')}</div>
      <div class="body"><div class="nm">${l.player?l.player:l.name}${l.pos?`<span class="pos">${l.pos}</span>`:''}</div>
      <div class="sub">${l.player?l.sub:l.sub}${pips(l.form)}</div></div>
      <div class="od">${fmtOdds(l.odds)}</div></div>`;
  });
  wrap.innerHTML=h;
  renderStake(od||Math.max(...legs.map(l=>l.odds)),S.singles);
}
function renderStake(odds,singles){
  const ret=(stake*odds);
  document.getElementById('stakebox').innerHTML=`
    <div class="qk"><span class="muted" style="font-weight:700">£</span>
      <input id="stk" type="number" value="${stake}" min="1">
      ${[5,10,20,50].map(v=>`<span class="q" data-v="${v}">£${v}</span>`).join('')}</div>
    <div class="ret"><span>${singles?'Top single returns':'Returns'} @ ${fmtOdds(odds)}</span><b>£${ret.toFixed(2)}</b></div>
    <button class="bet365" onclick="window.open('https://www.bet365.com','_blank')">Bet at Bet365 🅱</button>
    <div class="note">Odds shown are the model's fair price — shop for the best book line before staking. Returns include stake.</div>`;
  document.getElementById('stk').oninput=e=>{stake=parseFloat(e.target.value)||0;renderSlip();};
  document.querySelectorAll('.q').forEach(q=>q.onclick=()=>{stake=parseFloat(q.dataset.v);renderSlip();});
}

// ---- expected stats ----
function renderExp(){
  const box=document.getElementById('exp');let h='';
  const gmap={}; (FX.exp_graded||[]).forEach(e=>gmap[e.label]=e);
  FX.exp_pred.forEach(e=>{
    const tot=e.eh+e.ea||1, hp=Math.max(8,100*e.eh/tot), ap=Math.max(8,100*e.ea/tot);
    h+=`<div class="erow"><div class="lab"><span class="l">${e.label}</span>
      <span class="muted">${e.eh} – ${e.ea}</span></div>
      <div class="ebar"><span class="hh" style="width:${hp}%">${e.eh}</span>
      <span class="aa" style="width:${ap}%">${e.ea}</span></div>`;
    const g=gmap[e.label]; if(g) h+=`<div class="act">actual: <b>${g.ah} – ${g.aa}</b></div>`;
    h+='</div>';
  });
  box.innerHTML=h;
}

// ---- market browser ----
const FAMS=[['all','All'],['goals','Goals'],['corners','Corners'],['cards','Cards'],
  ['shots','Shots/SoT'],['fouls','Fouls'],['offsides','Offsides'],['saves','Saves'],
  ['result','Result/Score'],['player','Players']];
let ffam='all', fq='';
function isPlayer(m){return /_(shots|sot|goals|assists|saves|fouls_committed|fouls_suffered|score_or_assist|to_be_booked)/.test(m.market)
  && /[A-Z][a-z]+ /.test(m.market);}
function renderFilters(){
  const el=document.getElementById('filters');el.innerHTML='';
  FAMS.forEach(([id,l])=>{const c=document.createElement('span');c.className='fchip'+(id===ffam?' active':'');
    c.textContent=l;c.onclick=()=>{ffam=id;renderFilters();renderMarkets();};el.appendChild(c);});
}
const gradedByMk={}; (FX.graded||[]).forEach(t=>{gradedByMk[t.mk]=t.hit;});
function renderMarkets(){
  let rows=MK.filter(over);
  if(ffam==='player') rows=rows.filter(isPlayer);
  else if(ffam==='shots') rows=rows.filter(m=>m.fam==='shots'&&!isPlayer(m));
  else if(ffam!=='all') rows=rows.filter(m=>m.fam===ffam&&!isPlayer(m));
  if(fq) rows=rows.filter(m=>labelKey(m.market).toLowerCase().includes(fq));
  rows.sort((a,b)=>b.p-a.p);
  const box=document.getElementById('markets');
  box.innerHTML=rows.slice(0,160).map(m=>{
    const fl=m.flag&&m.flag.startsWith('bet');
    let res='';if(m.market in gradedByMk){const hr=gradedByMk[m.market];
      res=hr===null?'<span class="res void">–</span>':hr?'<span class="res win">✓</span>':'<span class="res lose">✗</span>';}
    return `<div class="mkt ${fl?'flagged':''}"><span class="k">${labelKey(m.market)}${res}</span>
      <span class="p">${(m.p*100).toFixed(0)}%</span><span class="f">${fmtOdds(m.fair)}</span>
      ${fl?'<span class="tag" style="color:var(--mag);border-color:var(--mag)">VALUE</span>':''}</div>`;
  }).join('')||'<div class="muted" style="padding:10px">No markets.</div>';
}

renderStyles();renderSlip();renderExp();renderFilters();renderMarkets();
const ms=document.getElementById('msearch');if(ms)ms.oninput=e=>{fq=e.target.value.toLowerCase();renderMarkets();};
"""


def esc(s):
    return html.escape(str(s), quote=True)


def head(title, depth):
    a = "../" if depth else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(TAGLINE)}">
<link rel="stylesheet" href="{a}assets/site.css"></head><body>
<header class="nav"><div class="wrap">
<a class="brand" href="{a}index.html"><span class="dot"></span>{BRAND}<small>WC 2026</small></a>
<div class="spacer"></div>
<a class="link" href="{a}fixtures.html">Fixtures</a>
<a class="link" href="{a}groups.html">Groups</a>
<a class="link" href="{a}teams.html">Teams</a>
<a class="link" href="{a}outrights.html">Outrights</a>
<a class="link" href="{a}index.html#model">Model</a>
</div></header>"""


def foot(depth):
    return f"""<footer><div class="wrap">
<b style="color:var(--txt)">{BRAND}</b> — predictions from a Monte-Carlo model (Elo + Dixon-Coles goals,
negative-binomial corners/shots/fouls, referee-adjusted cards, per-90 player props), Platt-calibrated
per market family and validated on Euro 2024, Copa América 2024 & WC 2022. Odds shown are the model's
fair price, not a bookmaker offer.
<div class="rg">18+ · Gamble responsibly · Past performance and model projections do not guarantee future
results. If gambling is a problem, seek support (e.g. BeGambleAware).</div>
</div></footer></body></html>"""


def fav_label(t):
    return f"{FLAGS.get(t,'⚽')} {t}"


def build_index(index, fixtures_data):
    body = ['<main class="wrap">']
    # hero
    body.append('<section class="hero"><h1>The World Cup, <span class="g">priced by a model that '
                'shows its work.</span></h1>'
                f'<p class="sub">{esc(TAGLINE)} No black box: every projection is backtested and '
                'calibrated, with results graded in the open.</p>'
                '<div class="statgrid">'
                + ''.join(f'<div class="stat"><b>{v}</b><span>{l}</span></div>' for v, l in STATS)
                + '</div>'
                '<div class="crosslinks" style="margin-top:18px">'
                '<a class="clink" href="fixtures.html">📅 All fixtures</a>'
                '<a class="clink" href="groups.html">🏆 Group tables</a>'
                '<a class="clink" href="teams.html">🌍 48 teams</a>'
                '<a class="clink" href="outrights.html">⭐ Outright odds</a>'
                '</div></section>')

    # split fixtures
    fixtures = index["fixtures"]
    def card(f):
        eid = f["eid"]; h, a = f["home"], f["away"]; grp = TEAM_GROUP.get(h, "")
        done = f["done"]; sc = f.get("score")
        fd = fixtures_data.get(eid, {})
        toppick = ""
        tips = fd.get("tips", [])
        if tips:
            best = max(tips, key=lambda t: t["p"])
            toppick = f'<div class="pick">Top pick: <b>{esc(best["k"])}</b> · {best["p"]*100:.0f}%</div>'
        status = (f'<span class="chip done">FT {esc(sc)}</span>' if done and sc
                  else '<span class="chip live">Upcoming</span>')
        scH = f'<span class="sc">{sc.split("-")[0]}</span>' if (done and sc) else ''
        scA = f'<span class="sc">{sc.split("-")[1]}</span>' if (done and sc) else ''
        return (f'<a class="fx" href="match/{eid}.html"><div class="top">'
                f'<span><span class="grp">Group {grp}</span> &nbsp;{kickoff_py(f["date"])}</span>{status}</div>'
                f'<div class="teams">'
                f'<div class="row"><span class="fl">{FLAGS.get(h,"⚽")}</span>{esc(h)}{scH}</div>'
                f'<div class="row"><span class="fl">{FLAGS.get(a,"⚽")}</span>{esc(a)}{scA}</div>'
                f'</div>{toppick}</a>')

    upcoming = [f for f in fixtures if not f["done"]]
    done = [f for f in fixtures if f["done"]]
    body.append('<section id="fixtures"><div class="h"><h2>Upcoming fixtures</h2>'
                f'<span class="muted">{len(upcoming)} matches · model-priced</span></div>'
                '<div class="cards">' + ''.join(card(f) for f in upcoming[:18]) + '</div></section>')
    if done:
        body.append('<section id="results"><div class="h"><h2>Results & graded picks</h2>'
                    '<span class="muted">our calls, scored after kickoff</span></div>'
                    '<div class="cards">' + ''.join(card(f) for f in reversed(done)) + '</div></section>')

    # group tables (standings from graded scores)
    body.append(build_groups(fixtures))

    # favourites by Elo
    teams = index["teams"]
    ranked = sorted(teams.items(), key=lambda kv: -kv[1]["elo"])[:10]
    mx = ranked[0][1]["elo"]; mn = ranked[-1][1]["elo"] - 40
    favrows = ""
    for t, d in ranked:
        w = max(8, 100 * (d["elo"] - mn) / (mx - mn))
        favrows += (f'<div class="favrow"><span class="fl">{FLAGS.get(t,"⚽")}</span>'
                    f'<span class="nm">{esc(t)}</span><span class="bar"><i style="width:{w:.0f}%"></i></span>'
                    f'<span class="el">{d["elo"]:.0f}</span></div>')
    body.append('<section id="favourites"><div class="h"><h2>Tournament favourites</h2>'
                '<span class="muted">by model Elo rating</span></div>' + favrows + '</section>')

    # model section
    body.append('<section id="model"><div class="h"><h2>Why trust these numbers</h2></div>'
                '<div class="panel"><p style="margin:0 0 10px">Most prediction sites hand you a number '
                'with no track record. We don\'t. The same model that prices these matches was run on three '
                'completed tournaments — <b>22,700 held-out market predictions</b> — and the picks at our '
                '72%+ bet rule landed <b>81.2%</b> of the time. Probabilities are Platt-calibrated per market '
                'family and capped where the model was shown to be overconfident.</p>'
                '<p class="muted" style="margin:0">Goals use an Elo-driven Dixon-Coles curve; corners, shots '
                'and fouls a negative-binomial with opponent and Elo-gap adjustment; cards are '
                'referee-adjusted (blending each official\'s international and ~88k club matches); player props '
                'are per-90 with shrinkage. 12,000 Monte-Carlo simulations per fixture.</p></div></section>')

    body.append('</main>')
    return head(f"{BRAND} — World Cup 2026 model predictions & odds", 0) + "".join(body) + foot(0)


def compute_standings(fixtures):
    table = {g: {t: {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "Pts": 0}
                 for t in ts} for g, ts in GROUPS.items()}
    for f in fixtures:
        if not (f["done"] and f.get("score")):
            continue
        h, a = f["home"], f["away"]; g = TEAM_GROUP.get(h)
        if not g or h not in table[g] or a not in table[g]:
            continue
        try:
            gh, ga = [int(x) for x in f["score"].split("-")]
        except Exception:
            continue
        for t, gf, gaa in ((h, gh, ga), (a, ga, gh)):
            r = table[g][t]; r["P"] += 1; r["GF"] += gf; r["GA"] += gaa
        if gh > ga:
            table[g][h]["W"] += 1; table[g][h]["Pts"] += 3; table[g][a]["L"] += 1
        elif ga > gh:
            table[g][a]["W"] += 1; table[g][a]["Pts"] += 3; table[g][h]["L"] += 1
        else:
            table[g][h]["D"] += 1; table[g][a]["D"] += 1
            table[g][h]["Pts"] += 1; table[g][a]["Pts"] += 1
    return table


ELO = {}  # populated in main(); used to break level standings by model rating


def group_order(table, g):
    return sorted(GROUPS[g], key=lambda t: (-table[g][t]["Pts"],
                  -(table[g][t]["GF"] - table[g][t]["GA"]), -table[g][t]["GF"],
                  -ELO.get(t, 1500)))


def qual_rank(table):
    """team -> 1-based position within its group (for qualification badges)."""
    out = {}
    for g in GROUPS:
        for i, t in enumerate(group_order(table, g)):
            out[t] = i + 1
    return out


def build_groups(fixtures):
    table = compute_standings(fixtures)
    out = ['<section id="groups"><div class="h"><h2>Group tables</h2>'
           '<span class="muted">live standings from played matches</span></div><div class="gwrap">']
    for g in GROUPS:
        rows = group_order(table, g)
        trs = ""
        for i, t in enumerate(rows):
            r = table[g][t]
            cls = ' class="qual"' if i < 2 else ''
            trs += (f'<tr{cls}><td><a href="{tslug(t)}">{FLAGS.get(t,"")} {esc(t)}</a></td>'
                    f'<td class="n">{r["P"]}</td><td class="n">{r["GF"]-r["GA"]:+d}</td>'
                    f'<td class="n pts">{r["Pts"]}</td></tr>')
        out.append(f'<div class="gtab"><h4>GROUP {g}</h4><table>'
                   f'<tr><th>Team</th><th style="text-align:right">P</th>'
                   f'<th style="text-align:right">GD</th><th style="text-align:right">Pts</th></tr>'
                   f'{trs}</table></div>')
    out.append('</div></section>')
    return "".join(out)


# ---------------------------------------------------------------- slugs / shared bits
import re as _re, unicodedata as _ud


def slugify(t):
    s = _ud.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return _re.sub(r"[^a-z0-9]+", "-", s).strip("-")


SLUG = {t: slugify(t) for t in TEAM_GROUP}


def tslug(t, depth=0):
    a = "../" if depth else ""
    return f"{a}team/{SLUG.get(t, slugify(t))}.html"


def outright_probs(teams):
    """Model rating-based outright win probabilities (Elo softmax)."""
    import math
    T = 145.0
    mx = max(d["elo"] for d in teams.values())
    raw = {t: math.exp((d["elo"] - mx) / T) for t, d in teams.items()}
    s = sum(raw.values())
    return {t: raw[t] / s for t in raw}


def status_of(f):
    return "results" if f["done"] else "upcoming"


def kickoff_py(d):
    import datetime
    try:
        dt = datetime.datetime.fromisoformat(d)
        return dt.strftime("%a %d %b · %H:%M")
    except Exception:
        return d


def build_match(fx):
    h, a, eid = fx["home"], fx["away"], fx["eid"]
    grp = TEAM_GROUP.get(h, "")
    done = fx.get("done"); sc = fx.get("score")
    mid = (f'<div class="sc">{esc(sc)}</div><div class="vs">FULL TIME</div>' if done and sc
           else '<div class="vs">VS</div><div class="muted" style="font-size:12px">'
                + kickoff_py(fx["date"]) + '</div>')
    banner = ""
    if done and sc:
        hits = sum(1 for t in fx.get("graded", []) if t.get("hit") == 1)
        tot = sum(1 for t in fx.get("graded", []) if t.get("hit") is not None)
        banner = (f'<div class="banner">Final score <b>{esc(sc)}</b>. '
                  f'Our locked picks landed <b>{hits}/{tot}</b> · scroll the markets to see each call graded.</div>')
    body = f"""<main class="wrap">
<div class="mhead"><div class="crumb"><a href="../index.html">{BRAND}</a> ›
<a href="../groups.html">Group {grp}</a> › {esc(h)} v {esc(a)}</div>
<div class="matchup">
  <a class="t" href="{tslug(h,1)}" style="text-decoration:none">
    <span class="fl">{FLAGS.get(h,"⚽")}</span><span class="nm">{esc(h)}</span>
    <span class="el">Elo {fx['elo'][h]:.0f}</span></a>
  <div class="mid">{mid}</div>
  <a class="t" href="{tslug(a,1)}" style="text-decoration:none">
    <span class="fl">{FLAGS.get(a,"⚽")}</span><span class="nm">{esc(a)}</span>
    <span class="el">Elo {fx['elo'][a]:.0f}</span></a>
</div>
<div class="metarow">Group {grp} · {esc(kickoff_py(fx['date']))}{' · Ref ' + esc(fx['ref']) if fx.get('ref') else ''}</div>
</div>
{banner}
<div class="layout">
  <div class="panel">
    <h3>Build a slip</h3>
    <div class="styles" id="styles"></div>
    <div class="slip" id="slip"></div>
    <div class="stake" id="stakebox"></div>
  </div>
  <div style="display:flex;flex-direction:column;gap:22px">
    <div class="panel exp"><h3>Model projection</h3><div id="exp"></div></div>
    <div class="panel"><h3>All markets · {len(fx['markets'])} priced</h3>
      <input id="msearch" placeholder="Search markets (e.g. corners, Dzeko, btts)…">
      <div class="filters" id="filters"></div>
      <div id="markets"></div>
    </div>
  </div>
</div></main>"""
    data_js = (f"<script>window.FX={json.dumps(fx, ensure_ascii=False)};"
               f"const BRAND={json.dumps(BRAND)};</script>")
    return (head(f"{esc(h)} v {esc(a)} — {BRAND} predictions & odds", 1) + body
            + data_js + f'<script src="../assets/match.js"></script>' + foot(1))


def fx_card(f, fixtures_data, depth=0):
    a = "../" if depth else ""
    eid = f["eid"]; h, aw = f["home"], f["away"]; grp = TEAM_GROUP.get(h, "")
    done = f["done"]; sc = f.get("score")
    fd = fixtures_data.get(eid, {})
    tips = fd.get("tips", [])
    toppick = ""
    if tips:
        best = max(tips, key=lambda t: t["p"])
        toppick = f'<div class="pick">Top pick: <b>{esc(best["k"])}</b> · {best["p"]*100:.0f}%</div>'
    status = (f'<span class="chip done">FT {esc(sc)}</span>' if done and sc
              else '<span class="chip live">Upcoming</span>')
    scH = f'<span class="sc">{sc.split("-")[0]}</span>' if (done and sc) else ''
    scA = f'<span class="sc">{sc.split("-")[1]}</span>' if (done and sc) else ''
    team_attr = f"{h} {aw}".lower()
    return (f'<a class="fx" data-fcard data-group="{grp}" data-status="{status_of(f)}" '
            f'data-team="{esc(team_attr)}" href="{a}match/{eid}.html"><div class="top">'
            f'<span><span class="grp">Group {grp}</span> &nbsp;{esc(kickoff_py(f["date"]))}</span>{status}</div>'
            f'<div class="teams">'
            f'<div class="row"><span class="fl">{FLAGS.get(h,"⚽")}</span>{esc(h)}{scH}</div>'
            f'<div class="row"><span class="fl">{FLAGS.get(aw,"⚽")}</span>{esc(aw)}{scA}</div>'
            f'</div>{toppick}</a>')


def group_chips():
    chips = '<div class="gchip all active" data-g="all">All groups</div>'
    chips += ''.join(f'<div class="gchip" data-g="{g}">{g}</div>' for g in GROUPS)
    return f'<div class="gchips">{chips}</div>'


def build_fixtures_page(index, fixtures_data):
    fixtures = sorted(index["fixtures"], key=lambda f: f["date"])
    # group by date
    body = ['<main class="wrap"><div class="phead"><h1>Fixtures</h1>'
            '<p>All 72 group-stage matches, model-priced. Filter by group, status or team.</p></div></main>',
            '<div class="toolbar"><div class="wrap">'
            '<div class="seg"><button class="active" data-s="all">All</button>'
            '<button data-s="upcoming">Upcoming</button><button data-s="results">Results</button></div>'
            + group_chips() +
            '<input id="srch" class="srch" placeholder="Search team…"></div></div>',
            '<main class="wrap"><div class="cards" id="fxgrid">']
    cur = None
    for f in fixtures:
        d = f["date"][:10]
        if d != cur:
            cur = d
            body.append(f'<div class="dhead">{esc(kickoff_py(f["date"]).split(" · ")[0])} '
                        f'{esc(d)}</div>')
        body.append(fx_card(f, fixtures_data))
    body.append('<div class="empty hide" id="empty">No matches match those filters.</div>')
    body.append('</div></main>')
    return (head(f"Fixtures — {BRAND} World Cup 2026", 0) + "".join(body)
            + '<script src="assets/app.js"></script>' + foot(0))


def build_groups_page(index, fixtures_data):
    table = compute_standings(index["fixtures"])
    fx_by_team = {}
    for f in index["fixtures"]:
        fx_by_team.setdefault(f["home"], []).append(f)
        fx_by_team.setdefault(f["away"], []).append(f)
    body = ['<main class="wrap"><div class="phead"><h1>Groups</h1>'
            '<p>Live standings (top two qualify) with every group fixture and our top pick.</p></div>',
            '<div class="gwrap">']
    for g in GROUPS:
        rows = group_order(table, g)
        trs = ""
        for i, t in enumerate(rows):
            r = table[g][t]
            cls = ' class="qual"' if i < 2 else ''
            trs += (f'<tr{cls}><td><a href="{tslug(t)}">{FLAGS.get(t,"")} {esc(t)}</a></td>'
                    f'<td class="n">{r["P"]}</td><td class="n">{r["W"]}-{r["D"]}-{r["L"]}</td>'
                    f'<td class="n">{r["GF"]-r["GA"]:+d}</td><td class="n pts">{r["Pts"]}</td></tr>')
        # group's fixtures
        gfx = sorted([f for f in index["fixtures"] if TEAM_GROUP.get(f["home"]) == g],
                     key=lambda f: f["date"])
        fxhtml = ""
        for f in gfx:
            sc = f.get("score"); res = f'{esc(sc)}' if (f["done"] and sc) else 'vs'
            fxhtml += (f'<a class="rrow" href="match/{f["eid"]}.html" style="text-decoration:none">'
                       f'<span class="op">{FLAGS.get(f["home"],"")} {esc(f["home"])}</span>'
                       f'<span class="sc">{res}</span>'
                       f'<span class="op" style="text-align:right">{esc(f["away"])} {FLAGS.get(f["away"],"")}</span></a>')
        body.append(f'<div class="gtab"><h4>GROUP {g}</h4><table>'
                    f'<tr><th>Team</th><th style="text-align:right">P</th>'
                    f'<th style="text-align:right">W-D-L</th><th style="text-align:right">GD</th>'
                    f'<th style="text-align:right">Pts</th></tr>{trs}</table>'
                    f'<div style="margin-top:10px">{fxhtml}</div></div>')
    body.append('</div></main>')
    return head(f"Groups — {BRAND} World Cup 2026", 0) + "".join(body) + foot(0)


def build_teams_page(index, teams_data):
    table = compute_standings(index["fixtures"])
    qr = qual_rank(table)
    ranked = sorted(TEAM_GROUP, key=lambda t: -index["teams"].get(t, {}).get("elo", 1500))
    elo_rank = {t: i + 1 for i, t in enumerate(ranked)}
    body = ['<main class="wrap"><div class="phead"><h1>Teams</h1>'
            '<p>All 48 nations — model rating, group and squad. Search or filter by group.</p></div></main>',
            '<div class="toolbar"><div class="wrap">' + group_chips()
            + '<input id="srch" class="srch" placeholder="Search team…"></div></div>',
            '<main class="wrap"><div class="cards" id="teamgrid">']
    for t in sorted(TEAM_GROUP):
        g = TEAM_GROUP[t]; elo = index["teams"].get(t, {}).get("elo", 1500)
        q = qr.get(t, 9)
        qb = (f'<span class="qbadge q">{"1st" if q==1 else "2nd"} · qualifying</span>' if q <= 2
              else f'<span class="qbadge">{q}{"rd" if q==3 else "th"} in group</span>')
        body.append(f'<a class="teamcard" data-fcard data-group="{g}" data-status="all" '
                    f'data-team="{esc(t.lower())}" href="{tslug(t)}">'
                    f'<span class="fl">{FLAGS.get(t,"⚽")}</span>'
                    f'<span><div class="nm">{esc(t)}</div>'
                    f'<div class="meta">Group {g} · #{elo_rank[t]} by rating</div>{qb}</span>'
                    f'<span class="gp"><div class="el">{elo:.0f}</div><div class="gr">Elo</div></span></a>')
    body.append('<div class="empty hide" id="empty">No teams match.</div></div></main>')
    return (head(f"Teams — {BRAND} World Cup 2026", 0) + "".join(body)
            + '<script src="assets/app.js"></script>' + foot(0))


def _statbar(label, val, vmax):
    w = max(4, min(100, 100 * val / vmax)) if vmax else 4
    return (f'<div class="mini"><div class="lab"><span>{label}</span><span>{val:.2f}</span></div>'
            f'<div class="bar"><i style="width:{w:.0f}%"></i></div></div>')


def build_team_profile(t, index, fixtures_data, teams_data):
    R = "../"
    g = TEAM_GROUP[t]; elo = index["teams"].get(t, {}).get("elo", 1500)
    table = compute_standings(index["fixtures"])
    qr = qual_rank(table); rnk = qr.get(t, 0)
    ranked = sorted(TEAM_GROUP, key=lambda x: -index["teams"].get(x, {}).get("elo", 1500))
    elo_rank = ranked.index(t) + 1
    op = outright_probs(index["teams"])
    win = op.get(t, 0) * 100

    # results + upcoming
    myfx = sorted([f for f in index["fixtures"] if t in (f["home"], f["away"])],
                  key=lambda f: f["date"])
    form, results_html, upcoming_html = [], "", ""
    for f in myfx:
        opp = f["away"] if f["home"] == t else f["home"]
        homeaway = "vs" if f["home"] == t else "@"
        if f["done"] and f.get("score"):
            gh, ga = [int(x) for x in f["score"].split("-")]
            mine, theirs = (gh, ga) if f["home"] == t else (ga, gh)
            r = "W" if mine > theirs else ("L" if mine < theirs else "D")
            form.append(r)
            results_html += (f'<a class="rrow" href="{R}match/{f["eid"]}.html" style="text-decoration:none">'
                             f'<span class="fp {r}">{r}</span>'
                             f'<span class="op">{homeaway} {FLAGS.get(opp,"")} {esc(opp)}</span>'
                             f'<span class="sc">{mine}-{theirs}</span></a>')
        else:
            fd = fixtures_data.get(f["eid"], {}); tips = fd.get("tips", [])
            pk = (f' · <b style="color:var(--pink)">{esc(max(tips,key=lambda x:x["p"])["k"])}</b>'
                  if tips else "")
            upcoming_html += (f'<a class="rrow" href="{R}match/{f["eid"]}.html" style="text-decoration:none">'
                              f'<span class="op">{homeaway} {FLAGS.get(opp,"")} {esc(opp)}'
                              f'<span class="muted" style="font-size:11.5px"> · {esc(kickoff_py(f["date"]))}</span></span>'
                              f'<span class="muted">{pk}</span></a>')
    fp = "".join(f'<span class="fp {r}">{r}</span>' for r in form) or '<span class="muted">no matches yet</span>'

    # key players
    players = teams_data.get(t, {}).get("players", [])
    pmax = {k: max([p.get(k, 0) for p in players] + [0.1]) for k in ("shots", "goals", "fouls_committed", "sot")}
    pp_html = ""
    for p in players:
        initials = "".join(w[0] for w in p["name"].split()[:2]).upper()
        pp_html += (f'<div class="pp"><span class="av">{esc(initials)}</span>'
                    f'<span><div class="nm">{esc(p["name"])}</div>'
                    f'<div class="st">{esc(p.get("pos") or "—")} · {p.get("n",0)} caps tracked</div></span>'
                    f'{_statbar("shots/90", p.get("shots",0), pmax["shots"])}</div>')

    qb = (f'<span class="qbadge q">{"1st" if rnk==1 else "2nd"} · in qualifying spots</span>' if rnk and rnk <= 2
          else f'<span class="qbadge">{rnk}{"rd" if rnk==3 else "th"} in group</span>' if rnk else "")
    body = f"""<main class="wrap">
<div class="crumb" style="padding-top:18px;font-size:12.5px;color:var(--dim)">
<a href="{R}index.html" style="color:var(--vio)">{BRAND}</a> › <a href="{R}teams.html" style="color:var(--vio)">Teams</a> › {esc(t)}</div>
<div class="tphero">
  <div class="big">{FLAGS.get(t,"⚽")}</div>
  <div><h1>{esc(t)}</h1><div class="sub">Group {g} · World Cup 2026 {qb}</div>
    <div class="crosslinks"><a class="clink" href="{R}groups.html">Group {g} table</a>
    <a class="clink" href="{R}outrights.html">Outright odds</a></div></div>
  <div class="kpi">
    <div class="k"><b>{elo:.0f}</b><span>Elo · #{elo_rank}/48</span></div>
    <div class="k"><b>{win:.1f}%</b><span>to win it (model)</span></div>
  </div>
</div>
<div class="form">{fp}</div>
<div class="cols">
  <div class="panel"><h3>Fixtures &amp; results</h3>
    {('<div style="margin-bottom:6px" class="muted">Results</div>'+results_html) if results_html else ''}
    {('<div style="margin:10px 0 6px" class="muted">Upcoming</div>'+upcoming_html) if upcoming_html else ''}
  </div>
  <div class="panel"><h3>Squad — players we price</h3>
    {pp_html or '<div class="muted">Squad data unavailable.</div>'}
    <div class="note" style="text-align:left;margin-top:10px">Per-90 rates from tracked internationals,
    shrunk to position priors and blended with club form — the same inputs behind each match's player props.</div>
  </div>
</div></main>"""
    return head(f"{esc(t)} — {BRAND} World Cup 2026 profile", 1) + body + foot(1)


def build_outrights(index):
    op = outright_probs(index["teams"])
    ranked = sorted(op.items(), key=lambda kv: -kv[1])
    mx = ranked[0][1]
    rows = ""
    for i, (t, p) in enumerate(ranked):
        w = max(3, 100 * p / mx)
        cls = " top" if i < 3 else ""
        odds = 1 / p if p > 0 else 999
        rows += (f'<a class="orow{cls}" href="{tslug(t)}" style="text-decoration:none">'
                 f'<span class="rk">{i+1}</span><span class="fl">{FLAGS.get(t,"⚽")}</span>'
                 f'<span class="nm">{esc(t)}</span>'
                 f'<span class="bar"><i style="width:{w:.0f}%"></i></span>'
                 f'<span class="pc">{p*100:.1f}%</span>'
                 f'<span class="od">{odds:.0f}/1</span></a>')
    body = (f'<main class="wrap"><div class="phead"><h1>Outright winner</h1>'
            f'<p>Model win probabilities for all 48 nations, from their ratings — with the implied fair price. '
            f'These are rating-based, not a full bracket simulation.</p></div>{rows}</main>')
    return head(f"Outright odds — {BRAND} World Cup 2026", 0) + body + foot(0)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(MATCHDIR, exist_ok=True)
    os.makedirs(os.path.join(SITE, "team"), exist_ok=True)
    index = json.load(open(os.path.join(DATA, "_index.json")))
    teams_data = json.load(open(os.path.join(DATA, "_teams.json")))
    ELO.update({t: d.get("elo", 1500) for t, d in index["teams"].items()})

    fixtures_data = {}
    for f in index["fixtures"]:
        fixtures_data[f["eid"]] = json.load(open(os.path.join(DATA, f"{f['eid']}.json")))

    # assets
    open(os.path.join(ASSETS, "site.css"), "w").write(CSS)
    flags_js = (f"window.__FLAGS__={json.dumps(FLAGS, ensure_ascii=False)};"
                f"window.__GROUP__={json.dumps(TEAM_GROUP, ensure_ascii=False)};\n")
    open(os.path.join(ASSETS, "site.js"), "w").write(flags_js + SITE_JS)
    open(os.path.join(ASSETS, "match.js"), "w").write(flags_js + SITE_JS + MATCH_JS)
    open(os.path.join(ASSETS, "app.js"), "w").write(flags_js + SITE_JS + APP_JS)

    open(os.path.join(SITE, "index.html"), "w").write(build_index(index, fixtures_data))
    open(os.path.join(SITE, "fixtures.html"), "w").write(build_fixtures_page(index, fixtures_data))
    open(os.path.join(SITE, "groups.html"), "w").write(build_groups_page(index, fixtures_data))
    open(os.path.join(SITE, "teams.html"), "w").write(build_teams_page(index, teams_data))
    open(os.path.join(SITE, "outrights.html"), "w").write(build_outrights(index))
    for t in TEAM_GROUP:
        open(os.path.join(SITE, "team", f"{SLUG[t]}.html"), "w").write(
            build_team_profile(t, index, fixtures_data, teams_data))
    for eid, fx in fixtures_data.items():
        open(os.path.join(MATCHDIR, f"{eid}.html"), "w").write(build_match(fx))

    n = 5 + len(TEAM_GROUP) + len(fixtures_data)
    print(f"built {n} pages: index, fixtures, groups, teams, outrights, "
          f"{len(TEAM_GROUP)} team profiles, {len(fixtures_data)} match pages -> {SITE}")


if __name__ == "__main__":
    main()
