'use strict';
const $ = id => document.getElementById(id);
const KEY = 'tribun-manager-pro09';
const P = [], FORM = window.TribunClubData.formations;
const defaults = {formation:'4-3-3',starters:[8,9,10,7,5,6,4,2,3,1,0],tactics:{...window.TribunTactics.defaults},special:{captain:9,penalty:9,free:7,corner:8},trainingDate:'',trainingUsed:0,gameDay:Date.now()+86400000};
const routes = ['squad','training','analysis'];
let saved = null, initialPage = 'squad';
try { saved = JSON.parse(localStorage.getItem(KEY)||'null'); } catch {}
try {
  const hash = decodeURIComponent(location.hash.slice(1));
  if (routes.includes(hash)) initialPage = hash;
  else if (hash) {
    const transfer = JSON.parse(hash);
    if (transfer && typeof transfer === 'object' && transfer.tactics) {
      saved = transfer;
      if (routes.includes(transfer.uiPage)) initialPage = transfer.uiPage;
      history.replaceState(null,'',location.pathname+location.search+'#'+initialPage);
    }
  }
} catch {}
saved=window.TribunTransfers?.current(saved)||saved;
P.push(...window.TribunClubData.loadRoster(saved));
const state = {...defaults,...saved,tactics:window.TribunTactics.normalize(saved?.tactics),special:{...defaults.special,...saved?.special}};
if (!FORM[state.formation]) state.formation = defaults.formation;
state.starters=window.TribunClubData.repairStarters(state.starters,P,state.formation);
let picked = null, benchFilter = 'all', toastTimer = null;
const escapeHtml = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const posName = pos => ({GK:'Kaleci',DEF:'Savunma',MID:'Orta saha',ATT:'Hücum'}[pos]||pos);
const posShort = pos => ({GK:'KL',DEF:'DF',MID:'OS',ATT:'FV'}[pos]||pos);
const icon = name => window.TribunUI?.icon(name)||'';
function store() {
  const latest=window.TribunTransfers?.cached();
  if(latest?.transferRevision>Number(state.transferRevision||0)){
    P.splice(0,P.length,...window.TribunClubData.loadRoster(latest));state.starters=window.TribunClubData.repairStarters(state.starters,P,state.formation);
    for(const k of ['transferRevision','transferProfileId','trainingDate','trainingUsed'])state[k]=latest[k];
  }
  try { localStorage.setItem(KEY,JSON.stringify({...state,players:P})); } catch {}
}
function notify(text) {
  const el = $('toast'); el.textContent = text; el.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(()=>el.classList.remove('show'),3200);
}
function portrait(p) { return `assets/face${Math.abs(Number(p.face)||0)%11}.png`; }
function playersInBench() { return P.filter(p=>p.owned!==false&&!state.starters.includes(p.id)); }
function roleFit(p,slot) { return window.TribunClubData.fit(p,slot); }
function quality(p,slot) { return Math.round(p.rating*roleFit(p,slot)*(.83+.17*p.fitness/100)*(.91+.09*p.form/100)); }
function strength() { return state.starters.reduce((s,id,i)=>s+quality(P[id],FORM[state.formation][i][0]),0)/11; }
function chemistry() { return Math.round(100*state.starters.reduce((s,id,i)=>s+roleFit(P[id],FORM[state.formation][i][0]),0)/11); }
function readiness() { return Math.round(.55*state.starters.reduce((s,id)=>s+P[id].fitness,0)/11+.45*chemistry()); }
function riskName() { return +state.tactics.aggression>=78?'YÜKSEK':+state.tactics.aggression>=55||+state.tactics.press>=80?'ORTA':'DÜŞÜK'; }
function card(p,slot) {
  // Rotate only the roster board. Simulation coordinates remain unchanged.
  const left = 100-(8+slot[2]*.84), top = 8+slot[1]*.84;
  const description = `${p.name}, ${posName(p.pos)}, güç ${quality(p,slot[0])}, kondisyon %${p.fitness}`;
  return `<button type="button" class="player ${picked===p.id?'select':''}" data-id="${p.id}" aria-pressed="${picked===p.id}" aria-label="${escapeHtml(description)}" style="--field-left:${left}%;--field-top:${top}%;--mobile-left:${5+slot[1]*.90}%;--mobile-top:${8+slot[2]*.84}%" title="${escapeHtml(description)}"><img src="${portrait(p)}" alt=""><span class="cardtext"><span class="cardtop"><b>${quality(p,slot[0])}</b><span>${posShort(slot[0])}</span></span><strong>${p.number} ${escapeHtml(p.name.split(' ').at(-1))}</strong><span class="minibar" aria-hidden="true"><i style="--pct:${p.fitness}%;--bar:#94cf8c"></i><i style="--pct:${p.form}%;--bar:#f4c77d"></i></span></span></button>`;
}
function renderPitch() {
  $('pitchPlayers').innerHTML = state.starters.map((id,i)=>card(P[id],FORM[state.formation][i])).join('');
  $('formationName').textContent = state.formation;
  $('field').dataset.formation = state.formation;
  $('topTeamRating').textContent = Math.round(strength());
  $('cancelSelection').hidden = picked===null;
  $('selectionHint').textContent = picked===null?'Bir futbolcu seç. Ardından yerini değiştirmek istediğin oyuncuya dokun.':`${P[picked].name} seçili. Yerini değiştireceğin futbolcuyu seç.`;
  document.querySelectorAll('#pitchPlayers .player').forEach(b=>b.onclick=()=>selectPlayer(+b.dataset.id));
}
function renderBench() {
  const all = playersInBench().filter(p=>benchFilter==='all'||p.pos===benchFilter);
  $('benchCount').textContent = playersInBench().length+' oyuncu';
  $('benchList').innerHTML = all.length?all.map(p=>`<button type="button" class="bench-item ${picked===p.id?'active':''}" data-id="${p.id}" aria-pressed="${picked===p.id}" aria-label="${escapeHtml(p.name)}, ${posName(p.pos)}, güç ${p.rating}, kondisyon %${p.fitness}"><span class="rating">${p.rating}</span><img src="${portrait(p)}" alt=""><span class="bench-copy"><b>${p.number} ${escapeHtml(p.name)}</b><small>${posName(p.pos)}</small></span><span class="fitness">${p.fitness}%<i style="--fitness:${p.fitness}%" aria-hidden="true"></i></span></button>`).join(''):'<p class="bench-empty">Bu mevkide yedek oyuncu yok.</p>';
  document.querySelectorAll('.bench-item').forEach(b=>b.onclick=()=>selectPlayer(+b.dataset.id));
}
function reconcileSpecialRoles() {
  for (const role of Object.keys(state.special)) if (!state.starters.includes(state.special[role])) {
    state.special[role] = state.starters.filter(id=>P[id].pos!=='GK').sort((a,b)=>P[b].rating-P[a].rating)[0]??state.starters[0];
  }
}
function selectPlayer(id) {
  if (picked===null) picked=id;
  else if (id===picked) picked=null;
  else {
    const ia=state.starters.indexOf(picked), ib=state.starters.indexOf(id);
    if (ia<0&&ib<0) picked=id;
    else if (ia>=0&&ib>=0) {
      [state.starters[ia],state.starters[ib]]=[state.starters[ib],state.starters[ia]];
      picked=null; notify('Oyuncuların sahadaki yerleri değiştirildi.');
    } else {
      state.starters[ia>=0?ia:ib]=ia>=0?id:picked;
      picked=null; reconcileSpecialRoles(); notify('Oyuncu değişikliği kaydedildi.');
    }
  }
  store(); renderAll();
  document.querySelector(`[data-manager-page="squad"] [data-id="${id}"]`)?.focus({preventScroll:true});
}
function renderSpecial() {
  reconcileSpecialRoles();
  $('specialGrid').innerHTML = [['captain','Kaptan'],['penalty','Penaltı'],['free','Serbest vuruş'],['corner','Korner']].map(([key,name])=>{
    const p=P[state.special[key]];
    return `<div class="spec"><strong>${name}</strong><img src="${portrait(p)}" alt=""><select aria-label="${name}" data-spec="${key}">${state.starters.map(id=>`<option value="${id}" ${id===p.id?'selected':''}>${escapeHtml(P[id].name.split(' ').at(-1))} (${P[id].rating})</option>`).join('')}</select></div>`;
  }).join('');
  document.querySelectorAll('[data-spec]').forEach(el=>el.onchange=()=>{state.special[el.dataset.spec]=+el.value;store();renderSpecial();notify('Duran top sorumlusu güncellendi.');});
}
function renderAnalysis() {
  const a=+state.tactics.aggression,p=+state.tactics.press,t=+state.tactics.tempo,risk=riskName(),ready=readiness();
  $('readyScore').textContent=ready; $('avgMetric').textContent=Math.round(strength());
  $('fitMetric').textContent='%'+chemistry(); $('riskMetric').textContent=risk;
  $('riskMetric').dataset.risk=risk==='YÜKSEK'?'high':risk==='ORTA'?'medium':'low';
  $('readyMetric').textContent=ready+'/100'; $('readinessDialValue').textContent=ready;
  $('readinessDial').setAttribute('stroke-dasharray',`${(ready*345.58/100).toFixed(2)} 346`);
  const items=[];
  if(chemistry()<94)items.push('Bazı futbolcular alışık olmadıkları mevkide. Dizilişi veya ilk 11’i değiştirmek takım uyumunu artırır.');
  if(a>=75)items.push('Sert mücadele ikili mücadele başarısını artırabilir; kart ve penaltı riski de yükselir.');
  if(p>=78&&t>=70)items.push('Yüksek pres ve hızlı tempo kondisyonu daha hızlı tüketebilir. Maçın ikinci yarısını da planla.');
  if(state.tactics.offside==='on'&&state.tactics.line==='low')items.push('Ofsayt tuzağı ile geride savunma hattı uyumsuz olabilir.');
  if(state.tactics.playstyle==='wing'&&state.formation==='3-5-2')items.push('3-5-2 ile kanat oyunu, kenar oyuncularının kondisyonuna daha çok ihtiyaç duyar.');
  if(!items.length)items.push('Takım dengeli görünüyor. Sonucu rakibin oyun planı, oyuncu kalitesi ve maçın gelişimi birlikte belirler.');
  $('insights').innerHTML='<ul>'+items.slice(0,3).map(x=>`<li>${x}</li>`).join('')+'</ul>';
  $('analysisText').textContent=`${state.formation} dizilişi. İlk 11’in kondisyonu ve mevki uyumu birlikte değerlendiriliyor. Oyuncu değişiklikleri bu değerleri anında günceller.`;
  const plan=window.TribunTactics.describe(state.tactics);
  $('analysisPlan').textContent=`${$('playstyle').selectedOptions[0].textContent} · Pres ${p}/100 · Tempo ${t}/100 · Sertlik ${a}/100. ${plan.attack}`;
  const attributes=[['passing','Pas'],['shooting','Bitiricilik'],['tackling','Müdahale'],['dribbling','Dripling'],['pace','Hız'],['heading','Kafa vuruşu'],['crossing','Orta'],['fitness','Kondisyon']];
  $('attributeBars').innerHTML=attributes.map(([key,label])=>{const value=Math.round(state.starters.reduce((sum,id)=>sum+Number(P[id][key]||0),0)/11);return `<div class="attribute-row"><div><span>${label}</span><b>${value}</b></div><div class="attribute-track" role="meter" aria-label="İlk 11 ${label.toLocaleLowerCase('tr-TR')} ortalaması" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${value}"><i style="--value:${value}%"></i></div></div>`;}).join('');
  $('tacticsExplainer').textContent=a>=75?'Agresif mücadele: müdahale ve pres girişimleri daha sert, kart olasılığı daha yüksek.':a<=35?'Dikkatli mücadele: kart riski düşük; rakibi baskı altında tutmak daha zor olabilir.':'Dengeli mücadele: fiziksel mücadele ile disiplin riski arasında orta yol.';
}
const trainingAreas={
  passing:['Pas ve oyun görüşü','Pas kalitesi ve takım arkadaşlarıyla bağlantılar üzerine çalış.'],
  shooting:['Bitiricilik','Kaleyi hedefleme ve son vuruş becerisini geliştir.'],
  tackling:['Savunma ve müdahale','İkili mücadele ve top kazanma becerisini geliştir.'],
  fitness:['Kondisyon','Dinlenme ve toparlanma çalışmasıyla fiziksel hazırlığı artır.'],
  dribbling:['Dripling','Top sürme ve rakipten sıyrılma becerisini geliştir.'],
  pace:['Hız','İvmelenme ve koşu hızı üzerine çalış.'],
  heading:['Kafa vuruşu','Hava toplarında son vuruş becerisini geliştir.'],
  crossing:['Orta','Kanattan ceza sahasına top gönderme becerisini geliştir.']
};
function resetTrainingDay() {
  const today=new Date().toISOString().slice(0,10);
  if(state.trainingDate!==today){state.trainingDate=today;state.trainingUsed=0;store();}
}
function renderTrainingPreview() {
  const player=P[+$('trainPlayer').value]||P[0],focus=$('trainFocus').value;
  const current=player[focus],next=Math.min(focus==='fitness'?100:99,current+(focus==='fitness'?5:3));
  $('trainingFocusCopy').textContent=trainingAreas[focus][1]+` Bu çalışmada ${Math.max(0,next-current)} puan gelişim${focus==='fitness'?'.':'; kondisyon en fazla 2 puan azalır.'}`;
  $('trainingPlayerPreview').innerHTML=`<div class="training-player-top"><img src="${portrait(player)}" alt="${escapeHtml(player.name)}"><div><small>${player.number} / ${posName(player.pos)}</small><h3>${escapeHtml(player.name)}</h3><p>Genel güç ${player.rating} · Kondisyon %${player.fitness}</p></div></div><div class="training-gain"><span>${trainingAreas[focus][0]}<br><small>${state.trainingUsed>=2?'Sonraki çalışma için öngörü':'Çalışma sonrası öngörü'}</small></span><div><span>${current}</span>${icon('arrow')}<b>${next}</b></div></div>`;
}
function renderTraining() {
  resetTrainingDay();
  const selected=$('trainPlayer').value,remaining=Math.max(0,2-state.trainingUsed);
  $('trainingLeft').textContent=remaining?`Bugün ${remaining} antrenman hakkın var.`:'Bugünkü çalışmalar tamamlandı.';
  $('trainingUseVisual').innerHTML=[0,1].map(i=>`<i class="${i<state.trainingUsed?'used':''}"></i>`).join('');
  $('trainButton').disabled=!remaining;
  $('trainPlayer').innerHTML=P.filter(p=>p.owned!==false).map(p=>`<option value="${p.id}">${escapeHtml(p.name)} (${p.rating})</option>`).join('');
  if(selected!==''&&P[+selected]?.owned!==false)$('trainPlayer').value=selected;
  renderTrainingPreview();
}
async function train() {
  if(window.TribunTransfers?.hasSession()){
    $('trainButton').disabled=true;
    try{const result=await window.TribunTransfers.command('train',{playerId:+$('trainPlayer').value,focus:$('trainFocus').value});notify(result.result.message);}
    catch(e){notify(e.message);}
    finally{renderTraining();renderAll();}return;
  }
  resetTrainingDay();
  if(state.trainingUsed>=2)return notify('Günlük antrenman hakkın bitti.');
  const p=P[+$('trainPlayer').value],focus=$('trainFocus').value;
  if(focus==='fitness')p.fitness=Math.min(100,p.fitness+5);
  else {p[focus]=Math.min(99,p[focus]+3);p.xp+=3;if(p.xp>=6){p.rating=Math.min(99,p.rating+1);p.xp-=6;}p.fitness=Math.max(50,p.fitness-2);}
  state.trainingUsed++;store();renderTraining();renderAll();notify(p.name+' · Antrenman tamamlandı.');
}
function renderAll(){renderPitch();renderBench();renderSpecial();renderAnalysis();}
function showManagerPage(page,updateHash=false) {
  if(!routes.includes(page))page='squad';
  document.querySelectorAll('[data-manager-page]').forEach(el=>el.hidden=el.dataset.managerPage!==page);
  document.querySelectorAll('[data-page]').forEach(b=>{const current=b.dataset.page===page;b.classList.toggle('selected',current);if(current)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  const copy={squad:['KULÜP MERKEZİ / MAÇ ÖNCESİ','SAHA SENİN.<br><em>KARAR SENİN.</em>','Kadronu hazırla. Oyunun kimliğini belirle. Takımını maç gününe taşı.'],training:['HAZIRLIK SAHASI / OYUNCU GELİŞİMİ','BUGÜN ÇALIŞ.<br><em>YARIN FARK YARAT.</em>','Futbolcunu seç. Geliştirmek istediğin alana odaklan. Değişimi takip et.'],analysis:['TEKNİK MERKEZ / TAKIM ANALİZİ','VERİYİ OKU.<br><em>OYUNU YÖNET.</em>','İlk 11’inin güçlü yanlarını, kondisyonunu ve taktik risklerini birlikte gör.']}[page];
  $('managerEyebrow').textContent=copy[0];$('managerHeroHeading').innerHTML=copy[1];$('managerHeroCopy').textContent=copy[2];
  document.title=({squad:'Kadro',training:'Antrenman',analysis:'Takım analizi'}[page])+' · Tribün Manager';
  if(page==='training')renderTraining();
  if(updateHash&&location.hash!=='#'+page)history.pushState(null,'','#'+page);
  document.querySelector('.app-header')?.removeAttribute('data-nav-open');
  document.querySelector('[data-menu-toggle]')?.setAttribute('aria-expanded','false');
}
function openForm() {
  $('formationModal').hidden=false;
  document.querySelectorAll('[data-form]').forEach(b=>{const active=b.dataset.form===state.formation;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));});
}
function openTactics() {store();location.href='tactics.html#'+encodeURIComponent(JSON.stringify({...state,players:P}));}
function openMatch() {
  store();const cfg={formation:state.formation,starters:state.starters,players:P,tactics:state.tactics,matchMinutes:state.matchMinutes||5,special:state.special,quality:strength(),readiness:readiness(),transferProfileId:state.transferProfileId,transferRevision:state.transferRevision};
  try{sessionStorage.setItem('tribun-match-config',JSON.stringify(cfg));}catch{}
  location.href='match.html#'+encodeURIComponent(JSON.stringify(cfg));
}
function tick() {
  const s=Math.max(0,Math.floor((state.gameDay-Date.now())/1000));
  $('countdown').textContent=[String(Math.floor(s/3600)).padStart(2,'0'),String(Math.floor(s%3600/60)).padStart(2,'0'),String(s%60).padStart(2,'0')].join(':');
}
function init() {
  reconcileSpecialRoles();store();
  for(const [id,value] of Object.entries(state.tactics))if($(id))$(id).value=value;
  for(const id of ['press','tempo','aggression'])$(id+'Val').textContent=state.tactics[id];
  document.querySelectorAll('.tactics-grid input,.tactics-grid select').forEach(el=>el.addEventListener('input',()=>{state.tactics[el.id]=el.value;if($(el.id+'Val'))$(el.id+'Val').textContent=el.value;store();renderAnalysis();}));
  $('formationToggle').onclick=openForm;
  $('closeModal').onclick=()=>{$('formationModal').hidden=true;};
  $('formationModal').onclick=e=>{if(e.target.id==='formationModal')$('formationModal').hidden=true;};
  $('formationChoices').innerHTML=Object.keys(FORM).map(f=>`<button type="button" data-form="${f}">${f}</button>`).join('');
  document.querySelectorAll('[data-form]').forEach(b=>b.onclick=()=>{state.formation=b.dataset.form;state.starters=window.TribunClubData.reorder(state.starters,state.formation,P);store();$('formationModal').hidden=true;renderAll();notify(state.formation+' dizilişine geçildi.');});
  document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{benchFilter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>{x.classList.toggle('sel',x===b);x.setAttribute('aria-pressed',String(x===b));});renderBench();});
  document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{if(b.dataset.page==='tactics')openTactics();else{showManagerPage(b.dataset.page,true);$('managerHeroHeading').setAttribute('tabindex','-1');$('managerHeroHeading').focus({preventScroll:true});$('mainContent').scrollIntoView?.({behavior:window.TribunUI?.motionEnabled()?'smooth':'instant',block:'start'});}});
  document.querySelectorAll('a[href="tactics.html"]').forEach(link=>link.onclick=e=>{e.preventDefault();openTactics();});
  $('cancelSelection').onclick=()=>{picked=null;renderPitch();renderBench();};
  $('trainPlayer').onchange=renderTrainingPreview;$('trainFocus').onchange=renderTrainingPreview;$('trainButton').onclick=train;
  $('demoMatch').onclick=openMatch;
  window.addEventListener('hashchange',()=>showManagerPage(location.hash.slice(1)));
  window.addEventListener('popstate',()=>showManagerPage(location.hash.slice(1)));
  renderTraining();renderAll();showManagerPage(initialPage);setInterval(tick,1000);tick();
}
window.addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
window.addEventListener('tribun:roster',e=>{
 const data=e.detail;if(!data?.players)return;
 P.splice(0,P.length,...window.TribunClubData.loadRoster(data));Object.assign(state,data);state.starters=window.TribunClubData.repairStarters(state.starters,P,state.formation);picked=null;renderTraining();renderAll();
});
init();
if(window.TribunTransfers?.hasSession())window.TribunTransfers.sync().catch(e=>notify(e.message));
