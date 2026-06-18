window.__FLAGS__={"Mexico": "🇲🇽", "South Africa": "🇿🇦", "South Korea": "🇰🇷", "Czechia": "🇨🇿", "Canada": "🇨🇦", "Bosnia-Herzegovina": "🇧🇦", "Qatar": "🇶🇦", "Switzerland": "🇨🇭", "Brazil": "🇧🇷", "Morocco": "🇲🇦", "Haiti": "🇭🇹", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "United States": "🇺🇸", "Paraguay": "🇵🇾", "Australia": "🇦🇺", "Türkiye": "🇹🇷", "Germany": "🇩🇪", "Curaçao": "🇨🇼", "Ivory Coast": "🇨🇮", "Ecuador": "🇪🇨", "Netherlands": "🇳🇱", "Japan": "🇯🇵", "Sweden": "🇸🇪", "Tunisia": "🇹🇳", "Belgium": "🇧🇪", "Egypt": "🇪🇬", "Iran": "🇮🇷", "New Zealand": "🇳🇿", "Spain": "🇪🇸", "Cape Verde": "🇨🇻", "Saudi Arabia": "🇸🇦", "Uruguay": "🇺🇾", "France": "🇫🇷", "Senegal": "🇸🇳", "Iraq": "🇮🇶", "Norway": "🇳🇴", "Argentina": "🇦🇷", "Algeria": "🇩🇿", "Austria": "🇦🇹", "Jordan": "🇯🇴", "Portugal": "🇵🇹", "Congo DR": "🇨🇩", "Uzbekistan": "🇺🇿", "Colombia": "🇨🇴", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Croatia": "🇭🇷", "Ghana": "🇬🇭", "Panama": "🇵🇦"};window.__GROUP__={"Mexico": "A", "South Africa": "A", "South Korea": "A", "Czechia": "A", "Canada": "B", "Bosnia-Herzegovina": "B", "Qatar": "B", "Switzerland": "B", "Brazil": "C", "Morocco": "C", "Haiti": "C", "Scotland": "C", "United States": "D", "Paraguay": "D", "Australia": "D", "Türkiye": "D", "Germany": "E", "Curaçao": "E", "Ivory Coast": "E", "Ecuador": "E", "Netherlands": "F", "Japan": "F", "Sweden": "F", "Tunisia": "F", "Belgium": "G", "Egypt": "G", "Iran": "G", "New Zealand": "G", "Spain": "H", "Cape Verde": "H", "Saudi Arabia": "H", "Uruguay": "H", "France": "I", "Senegal": "I", "Iraq": "I", "Norway": "I", "Argentina": "J", "Algeria": "J", "Austria": "J", "Jordan": "J", "Portugal": "K", "Congo DR": "K", "Uzbekistan": "K", "Colombia": "K", "England": "L", "Croatia": "L", "Ghana": "L", "Panama": "L"};

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
