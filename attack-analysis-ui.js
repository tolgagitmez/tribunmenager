'use strict';
(function(root){
const stages=[['gain','Top kazanımı'],['pressureEscape','Baskıdan çıkış'],['lineBreak','Hat kırma'],['finalThird','Son bölge'],['box','Ceza sahası'],['shot','Şut çıkışı']];
const reasons={'opponent-control':'Rakip kontrolü','pass-interception':'Pas rakibe geçti','pass-intercepted':'Pas rakibe geçti','own-pass-out':'Pas dışarı çıktı','out':'Top dışarı çıktı','out-loss':'Top dışarıda rakibe geçti','out-retained':'Top dışarıda takımda kaldı','offside':'Ofsayt','foul':'Faul / duran top','foul-won':'Kazanılan faul','foul-conceded':'Rakibin kazandığı faul','retained-restart':'Takımda kalan duran top','corner-won':'Kazanılan korner','corner-conceded':'Rakibin kazandığı korner','goal-kick-retained':'Takımın aut atışı','goal-kick-conceded':'Rakibin aut atışı','restart':'Duran top','shot':'Şut çıktı','shot-release':'Şut çıktı','goal':'Gol','opponent-goal':'Rakip golü','loose-control':'Kontrol kaybı','duel-loss':'Mücadele sonrası kayıp','control-recovery-loss':'Kontrolü toparlayamadan kayıp','preparation-loss':'Hazırlık iptali sonrası kayıp','keeper-possession':'Rakip kaleci kontrolü','censored':'Ölçüm sonunda sürüyordu','match-end':'Maç sonunda sürüyordu','unknown':'Ayrıştırılamayan bitiş'};
const number=new Intl.NumberFormat('tr-TR',{maximumFractionDigits:1});
const count=n=>number.format(Number.isFinite(n)?n:0),rate=n=>Number.isFinite(n)?number.format(n):'—';
const clock=n=>{const t=Math.max(0,Math.floor(n||0));return `${String(Math.floor(t/60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`;};
function mount(container,readers){
 const doc=container.ownerDocument,el=(tag,text,className)=>{const n=doc.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;};
 const header=el('header'),heading=el('b','HÜCUM ANALİZİ');heading.id='attackAnalysisTitle';const status=el('span','ÖLÇÜLÜYOR');header.append(heading,status);
 const overview=el('p',undefined,'attack-overview'),note=el('p','Ölçüm süresinde ilerleyen / değerlendirilebilir hücumlar. Süren hücumlar henüz bitmiş sayılmaz. İleride başlayan hücumlar ve baskısız başlangıçlar ayrı tutulur.','attack-note');
 const details=el('details');details.open=true;details.append(el('summary','Hücum zinciri ve bitişler'));
 const table=el('table');table.className='attack-table';const caption=el('caption','Ev sahibi ve konuk takımın hücum aşamaları');caption.className='visually-hidden';table.append(caption);
 const head=el('thead'),headRow=el('tr');for(const label of ['Aşama','Ev sahibi','Konuk'])headRow.append(el('th',label));head.append(headRow);table.append(head);
 const body=el('tbody');table.append(body);details.append(note,table);
 const outcomes=el('div',undefined,'attack-endings'),evidence=el('div',undefined,'attack-evidence'),coverage=el('p',undefined,'attack-note');
 const explanation=el('p','Bitişler gerçekleşen olaylardır. Destek, bekleme ve koşu kayıtları olası açıklamalardır; tek başına hatanın nedenini kanıtlamaz.','attack-note');
 details.append(outcomes,evidence,coverage,explanation);
 const exportButton=el('button','Analizi JSON olarak indir','control-button');exportButton.type='button';exportButton.id='downloadAttackAnalysis';
 const error=el('p',undefined,'attack-analysis-error');error.hidden=true;error.setAttribute('role','status');container.replaceChildren(header,overview,details,exportButton,error);
 function render(summary){
  const r=summary||readers.summary(),teams=r.teams||[],c=r.clock||{};
  status.textContent=r.valid===false?'KAYIT EKSİK':'CANLI ÖLÇÜM';
  overview.textContent=`Top oyunda ${clock(c.inPlaySeconds)} · Duran top / ara ${clock(c.deadBallSeconds)} · Ölçülen ${clock(c.observedSeconds)}. Şut / 10 dakika top oyunda: ${rate(teams[0]?.rates?.shotsPer10InPlay)} – ${rate(teams[1]?.rates?.shotsPer10InPlay)}.`;
  body.replaceChildren();
  for(const [key,label]of stages){const row=el('tr'),name=el('th',label);name.scope='row';row.append(name);for(const team of teams.slice(0,2)){const eligible=team.stageEligibility?.[key],reached=team.eligibleReached?.[key]??team.stageCounts?.[key],cell=el('td',eligible>0?`${count(reached)} / ${count(eligible)}`:'—');if(team.startedBeyond?.[key])cell.append(el('small',`Başlangıçta ileride: ${count(team.startedBeyond[key])}`));if(team.notRequired?.[key])cell.append(el('small',`Gerekmedi: ${count(team.notRequired[key])}`));row.append(cell);}body.append(row);}
  outcomes.replaceChildren();evidence.replaceChildren();
  for(const [i,team]of teams.slice(0,2).entries()){
   const section=el('section'),title=el('h3',`${i?'Konuk':'Ev sahibi'} · ${count(team.attacks)} hücum`),list=el('ul');section.append(title);
   const entries=[];for(const [stage,ends]of Object.entries(team.endedByStage||{}))for(const [reason,n]of Object.entries(ends))if(n)entries.push({stage,reason,n});
   entries.sort((a,b)=>b.n-a.n);
   for(const item of entries.slice(0,6)){const label=stages.find(s=>s[0]===item.stage)?.[1]||'Aşama öncesi';list.append(el('li',`${label} · ${reasons[item.reason]||'Diğer kayıtlı bitiş'}: ${count(item.n)}`));}
   if(!entries.length)list.append(el('li','Henüz tamamlanan hücum yok.'));
   section.append(list,el('p',`Süren ${count(team.pending)} · Ölçüm sınırında ${count(team.censored)}`,'attack-note'));outcomes.append(section);
   const e=team.evidence||{},facts=el('section');facts.append(el('h3',`${i?'Konuk':'Ev sahibi'} · saha kayıtları`),el('p',`Bekleme kararı ${count(e.holdDecisions)} · Bekleme ${rate(e.holdSeconds)} sn · Hareketsiz kontrol ${rate(e.stationaryControlSeconds)} sn`),el('p',`Hedefine yakın destek ${rate(e.readySupportSeconds)} sn · Hedefine uzak destek ${rate(e.supportUnreadySeconds)} sn · Destek görevi yok ${rate(e.supportMissingSeconds)} sn`),el('p',`Pas hazırlığı iptali ${count(e.passPreparationAborts)} · Ceza sahasında görülen koşucu ${count(e.boxRunnerArrivals)}`));evidence.append(facts);
  }
  const cv=r.coverage||{},air=cv.crosses||{},keepers=cv.keepers||{},backs=cv.cutbacks||{};
  coverage.textContent=`Orta ${count(air.releases)} · Alçalan kafa aralığı ${count(air.descendingWindows)} · Kafa teması ${count(air.contacts)} (şut ${count(air.headedShots)}, pas ${count(air.headedPasses)}). Geriye çıkarma ${count(backs.releases)} · Takım alımı ${count(backs.completed)}. Kalecinin işlediği fırsat ${count(keepers.processingOpportunities)} · Tutuş ${count(keepers.catches)} · Çelme ${count(keepers.parries)}. Sıfır örnek, kalite sonucu değildir; ayrıntılı kapsam indirilen rapordadır.`;
  const missing=Number(r.truncatedEpisodes)||0,unobserved=Number(c.unobservedSeconds)||0;error.hidden=r.valid!==false&&!missing&&!unobserved;error.textContent=r.valid===false?'Analiz kaydında eksik var; ayrıntıları indirilen rapordan inceleyebilirsin.':unobserved>0?`${rate(unobserved)} sn örneklenmedi; bu aralık oyunda kalan süreye ve aşama sürelerine eklenmez.`:`Ayrıntılı kaydın ilk ${count(missing)} hücumu sınır dışında; toplamlar korunuyor.`;
 }
 function download(){
  const report=readers.report();if(readers.download){readers.download(report);return;}
  const win=doc.defaultView,url=win.URL.createObjectURL(new win.Blob([JSON.stringify(report,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download='tribun-hucum-analizi.json';doc.body.append(a);a.click();a.remove();win.setTimeout(()=>win.URL.revokeObjectURL(url),0);
 }
 exportButton.addEventListener('click',download);render();
 return {render,destroy(){exportButton.removeEventListener('click',download);container.replaceChildren();}};
}
const api={mount,stages,reasons};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.TribunAttackAnalysisUI=api;
})(typeof window!=='undefined'?window:globalThis);
