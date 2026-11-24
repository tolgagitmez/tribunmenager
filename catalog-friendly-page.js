'use strict';
(()=>{
const $=id=>document.getElementById(id),F=window.TribunCatalogFriendly,M=window.TribunPlayerModel,T=window.TribunTactics;
let snapshots=[],teams=[],generation=0;
const sides=['home','away'];
const option=(value,label)=>{const o=document.createElement('option');o.value=value;o.textContent=label;return o;};
function select(el,items,selected){el.replaceChildren(...items.map(([value,label])=>option(value,label)));if(items.some(([v])=>String(v)===String(selected)))el.value=selected;}
for(const side of sides){
 select($(side+'Formation'),Object.keys(M.slots).map(k=>[k,k]),'4-3-3');
 select($(side+'Tactic'),T.presets.map(p=>[p.id,p.name]),'balanced');
 for(const [key,label] of [['press','Baskı'],['tempo','Tempo'],['aggression','Sertlik']]){
  const row=document.createElement('label'),v=document.createElement('output'),input=document.createElement('input');
  row.className='catalog-range';row.append(label,v,input);input.type='range';input.min=0;input.max=100;input.id=side+key;
  input.oninput=()=>{v.textContent=input.value;check()};$(side+'Sliders').append(row);
 }
 $(side+'Tactic').onchange=()=>{applyPreset(side);check()};
 $(side+'Formation').onchange=$(side+'Team').onchange=()=>{render(side);check()};
 applyPreset(side);
}
function applyPreset(side){const t=T.presets.find(p=>p.id===$(side+'Tactic').value).tactics;for(const k of ['press','tempo','aggression']){const i=$(side+k);i.value=t[k];i.previousSibling.textContent=i.value;}}
function selected(side){return teams.find(t=>t.teamUid===$(side+'Team').value)}
function render(side){
 const t=selected(side),box=$(side+'XI'),info=$(side+'Info');box.replaceChildren();info.textContent='';
 if(!t)return;
 info.textContent=t.players.length+' futbolcu · veri tarihi '+t.fetchedAt.slice(0,10);
 try{
  const formation=$(side+'Formation').value,xi=F.selectXI(t.players,formation);
  M.slots[formation].forEach((pos,i)=>{
   const row=document.createElement('label'),s=document.createElement('select');row.className='catalog-xi';
   row.append(pos,s);select(s,t.players.filter(p=>M.groups[p.pos].includes(pos)).map(p=>[p.id,p.name+' · '+p.rating]),xi[i]);
   s.setAttribute('aria-label',side+' '+pos+' '+(i+1));s.onchange=check;box.append(row);
  });
 }catch(e){info.textContent=e.message;}
}
function rebuild(){
 teams=snapshots.map(s=>F.load(s,$('ratingMode').value));
 for(const side of sides){const el=$(side+'Team'),old=el.value;select(el,teams.map(t=>[t.teamUid,t.name]),old||teams[side==='home'?0:1]?.teamUid);render(side);}
 check();
}
function cfg(){
 if(!$('rights').checked)throw Error('Yerel kullanım iznini onayla.');
 const home=selected('home'),away=selected('away');if(!home||!away)throw Error('İki farklı takım seç.');
 const opts={};
 for(const side of sides){
  const t={...T.presets.find(p=>p.id===$(side+'Tactic').value).tactics};
  for(const k of ['press','tempo','aggression'])t[k]=Number($(side+k).value);
  const pre=side==='home'?'': 'away';
  opts[pre?pre+'Formation':'formation']=$(side+'Formation').value;
  opts[pre?pre+'Starters':'starters']=[...$(side+'XI').querySelectorAll('select')].map(s=>Number(s.value));
  opts[pre?pre+'Tactics':'tactics']=t;
 }
 return F.build(home,away,opts);
}
function check(){try{cfg();$('status').textContent='İki kadro hazır. Sentetik yeteneklerle yalnızca yerel maç.';$('launch').disabled=false;}catch(e){$('status').textContent=e.message;$('launch').disabled=true;}}
$('rights').onchange=check;
$('ratingMode').onchange=()=>{try{rebuild()}catch(e){$('status').textContent=e.message;$('launch').disabled=true;}};
$('files').onchange=async()=>{
 const token=++generation;snapshots=[];teams=[];$('launch').disabled=true;
 for(const side of sides){$(side+'Team').replaceChildren();render(side);}
 try{
  const list=[...$('files').files];if(list.length<2||list.length>20||list.some(f=>f.size>250000))throw Error('2–20 takım dosyası seç; dosya başına en fazla 250 KB.');
  const raw=await Promise.all(list.map(async f=>JSON.parse(await f.text())));
  if(token!==generation)return;
  const parsed=raw.map(s=>F.load(s));if(new Set(parsed.map(t=>t.teamUid)).size!==parsed.length)throw Error('Aynı takım iki kez yüklenemez.');
  snapshots=raw;rebuild();
 }catch(e){if(token===generation){$('status').textContent='Kadro yüklenemedi: '+e.message;$('launch').disabled=true;}}
};
$('launch').onclick=()=>{try{F.launch(cfg())}catch(e){$('status').textContent='Maç açılamadı: '+e.message;}};
check();
})();
