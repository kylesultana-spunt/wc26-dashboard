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
