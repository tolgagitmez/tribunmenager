'use strict';
(() => {
 const status=document.getElementById('originalStatus'), launch=document.getElementById('originalLaunch'), refresh=document.getElementById('originalRefresh');
 const saveNote=document.getElementById('nativeSaveStoreStatus');
 function renderSaveStore(s){
  if(!saveNote)return;
  const store=s.saveStore;
  if(!store){saveNote.textContent='Lig kayıt deposu bu ortamda kullanılamıyor.';return;}
  if(!store.valid){saveNote.textContent='Lig kayıt deposu incelenemedi; terminali kontrol et. Kayıtları silme.';return;}
  let message=store.hasSnapshot?'Saklanmış lig kayıtları mevcut.':'Henüz saklanmış lig kaydı yok.';
  if(store.recoveryCount)message+=' '+store.recoveryCount+' kurtarma klasörü var; otomatik yüklenmez.';
  if(store.interruptedSessionCount)message+=' '+store.interruptedSessionCount+' çalışma klasörü var; başka oturum açık olabilir. Silmeden önce kontrol et.';
  if(store.inventoryTruncated)message+=' Kayıt deposu incelemesi sınırlandırıldı.';
  saveNote.textContent=message;
 }
 let busy=false;
 function render(s) {
  renderSaveStore(s);
  launch.disabled=busy||!s.supported||!s.installed||s.running;
  status.textContent=!s.supported?'Bu işletim sistemi henüz desteklenmiyor.':!s.installed?'Motor paketi bulunamadı. Terminalden kurulum yap.':s.running?'Masaüstü motoru başlatılıyor veya çalışıyor.':s.lastExitCode!==null&&s.lastExitCode!==0?'Motor kapandı veya doğrulama başarısız oldu. Terminali kontrol et.':'Motor paketi mevcut. Başlatırken bütünlüğü doğrulanacak.';
 }
 let resultsSequence=0;
 async function updateResults() {
  const seq=++resultsSequence;
  const note=document.getElementById('nativeResultStatus'), list=document.getElementById('nativeResultList');
  const fragment=document.createDocumentFragment();
  try {
   const response=await fetch('/api/original/results',{cache:'no-store'});
   if(!response.ok)throw Error();
   const {report}=await response.json();
   if(seq!==resultsSequence)return;
   list.replaceChildren();
   if(!report){note.textContent='Henüz tamamlanmış bir motor oturumu kaydı yok.';return;}
   if(report.exitCode!==0){note.textContent='Son motor oturumu hatayla kapandı; sonuç aktarılmadı.';return;}
   let count=0;
   for(const save of report.saves){
    const heading=document.createElement('h3');heading.textContent=save.saveName;fragment.append(heading);
    if(save.managedTeam){
     const club=document.createElement('p');club.textContent='Yönetilen takım: '+save.managedTeam.name;fragment.append(club);
    }
    if(save.managedSquad){
     const squad=save.managedSquad;
     const panel=document.createElement('details');
     const summary=document.createElement('summary');summary.textContent='Saklanmış takım kadrosu ve taktikleri';panel.append(summary);
     const note=document.createElement('p');note.className='micro';note.textContent='Son kaydedilen yerel lig verisi. Canlı ilk 11 değildir; motora veya web kadrosuna yazılmaz.';panel.append(note);
     function group(title,values){
      const h=document.createElement('h5');h.textContent=title;panel.append(h);
      const ul=document.createElement('ul');
      for(const value of values){const li=document.createElement('li');li.textContent=value;ul.append(li);}
      panel.append(ul);
     }
     group('Kayıtlı kulüp oyuncuları',squad.players.map(p=>p.name+' · '+(p.role??'—')+' · sıra: '+(p.formationOrder??'—')));
     if(squad.truncated){const p=document.createElement('p');p.textContent='Kadro 128 oyuncuyla sınırlandırıldı.';panel.append(p);}
     group('Kayıtlı diziliş yuvaları',squad.formation?.length?squad.formation.map(p=>p.slot+' · '+(p.role??'—')+' · '+(p.rawPosition?.join(', ')??'—')):['Diziliş bilgisi okunamadı.']);
     group('Kayıtlı motor taktikleri',squad.tactics?.length?squad.tactics.map(t=>t.label+' : '+t.value+(t.source==='upstream-memory-default'?' (motorun varsayılan değeri)':'')):['Taktik bilgisi okunamadı.']);
     fragment.append(panel);
    }
    if(Array.isArray(save.pendingFixtures)){
     const next=document.createElement('h4');next.textContent='Oynanmamış fikstürler';fragment.append(next);
     const pending=document.createElement('ul');
     for(const match of save.pendingFixtures){
      const row=document.createElement('li');row.textContent=match.nativeDate+' · '+match.homeTeam+' – '+match.awayTeam;pending.append(row);
     }
     if(!save.pendingFixtures.length){const row=document.createElement('li');row.textContent='Bekleyen fikstür bulunamadı.';pending.append(row);}
     fragment.append(pending);
     if(save.pendingTruncated){const p=document.createElement('p');p.textContent='İlk 30 oynanmamış fikstür gösteriliyor.';fragment.append(p);}
     const played=document.createElement('h4');played.textContent='Tamamlanmış maç kayıtları';fragment.append(played);
    }
    if(save.standings&&Array.isArray(save.standings.rows)){
     const h=document.createElement('h4');h.textContent='Puan durumu · '+save.standings.league;fragment.append(h);
     const wrap=document.createElement('div');wrap.style.overflowX='auto';
     const table=document.createElement('table');table.setAttribute('aria-label','Orijinal lig puan durumu');
     const header=table.createTHead().insertRow();
     for(const name of ['#','Takım','O','G','B','M','A','Y','AV','P','Form']){
      const cell=document.createElement('th');cell.scope='col';cell.textContent=name;header.append(cell);
     }
     const body=table.createTBody();
     for(const item of save.standings.rows){
      const tr=body.insertRow();
      const values=[item.position,item.name+(item.managed?' (Senin takımın)':''),item.played,item.won,item.drawn,item.lost,item.goalsFor,item.goalsAgainst,item.goalDifference,item.points,item.form||'—'];
      for(const value of values)tr.insertCell().textContent=value;
     }
     wrap.append(table);fragment.append(wrap);
     const scope=document.createElement('p');scope.className='micro';
     scope.textContent='Orijinal motorun kayıtlı sonuçlarından hesaplandı; motorun puan durumu kuralları tüm oynanmış müsabakaları sayar. Web ligine yazılmaz.';fragment.append(scope);
    }
    const rows=document.createElement('ul');
    for(const result of save.results){
     const row=document.createElement('li');
     row.textContent=result.nativeDate+' · '+result.homeTeam+' '+result.homeGoals+' - '+result.awayGoals+' '+result.awayTeam;
     rows.append(row);count++;
    }
    fragment.append(rows);
    if(save.truncated){const p=document.createElement('p');p.textContent='Yalnızca son 100 kayıt gösteriliyor.';fragment.append(p);}
   }
   const history=report.matchHistory;
   if(history&&Array.isArray(history.records)){
    const section=document.createElement('section');
    const h=document.createElement('h3');h.textContent=history.scope==='retained-native-history'?'Saklanan 3D maç istatistikleri':'Son oturumun 3D maç istatistikleri';section.append(h);
    const scope=document.createElement('p');scope.textContent='Motorun maç geçmişinden okunur. Lig fikstürleriyle eşleştirilmez; hızlı maç ve kariyer maçı da olabilir. Canlı veri değildir.';section.append(scope);
    const value=(v,percent=false)=>v==null?'—':String(v)+(percent?'%':'');
    const performance=history.teamPerformance;
    if(performance&&Array.isArray(performance.teams)&&performance.teams.length){
     const panel=document.createElement('details');panel.open=true;
     const title=document.createElement('summary');title.textContent='Takım performans karşılaştırması';panel.append(title);
     const description=document.createElement('p');description.className='micro';
     description.textContent=performance.sampleMatches+' geçerli maç · Son 30 kayıt içindeki örneklem. Takımlar tam adlarına göre gruplanır; farklı maç modları karışık olabilir. Sezon puan durumu veya taktik etkisi ölçümü değildir.';
     if(performance.excludedSameNameMatches)description.textContent+=' Aynı adlı takımların '+performance.excludedSameNameMatches+' karşılaşması dışarıda bırakıldı.';
     panel.append(description);
     const wrap=document.createElement('div');wrap.style.overflowX='auto';
     const table=document.createElement('table');table.setAttribute('aria-label','3D takım performansı');
     const columns=[['Takım','teamName'],['Maç','played'],['G','won'],['B','drawn'],['M','lost'],['Gol/maç','goalsPerMatch'],['Şut/maç','shotsPerMatch'],['İsabet/maç','shotsOnTargetPerMatch'],['Şut isabeti','shotAccuracyPct',true],['Pas başarısı','passAccuracyPct',true],['Ort. topa sahip olma','meanPossessionPct',true]];
     const header=table.createTHead().insertRow();
     for(const [label] of columns){const th=document.createElement('th');th.scope='col';th.textContent=label;header.append(th);}
     const body=table.createTBody();
     for(const team of performance.teams){const row=body.insertRow();for(const [,key,percent] of columns)row.insertCell().textContent=value(team[key],percent);}
     wrap.append(table);panel.append(wrap);section.append(panel);
    }
    if(Array.isArray(history.teamTrends)&&history.teamTrends.length){
     const trend=document.createElement('details');
     const title=document.createElement('summary');title.textContent='Son beş maç performansı';trend.append(title);
     const desc=document.createElement('p');desc.className='micro';desc.textContent='Son 30 geçmiş kaydındaki en fazla beş geçerli karşılaşma, eskiden yeniye. Aynı adlı takımlar gruplanır; farklı maç modları ve süreleri olabilir. Eksik maçlar tahmin edilmez.';trend.append(desc);
     const label=document.createElement('label');label.textContent='Takım: ';
     const select=document.createElement('select');select.setAttribute('aria-label','Performans grafiği takımı');
     for(const [index,item] of history.teamTrends.entries()){
      const option=document.createElement('option');option.value=String(index);option.textContent=item.teamName;select.append(option);
     }
     label.append(select);trend.append(label);
     const graph=document.createElement('div');trend.append(graph);
     const ns='http://www.w3.org/2000/svg';
     function draw(){
      graph.replaceChildren();
      const item=history.teamTrends[Number(select.value)];
      if(!item||!item.matches.length)return;
      const matches=item.matches;
      const caption=document.createElement('p');caption.textContent=item.teamName+' · '+matches.length+' maç';graph.append(caption);
      for(const [name,left,right] of [['Goller','goalsFor','goalsAgainst'],['Şutlar','shots','shotsAgainst'],['İsabetli şutlar','shotsOnTarget','shotsOnTargetAgainst']]){
       const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 340 150');svg.setAttribute('width','100%');svg.style.maxWidth='520px';svg.setAttribute('role','img');svg.setAttribute('aria-label',name+' grafiği');
       function el(tag,attrs,text){
        const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;svg.append(e);return e;
       }
       const max=Math.max(1,...matches.flatMap(m=>[m[left],m[right]]));
       el('text',{x:12,y:15,fill:'currentColor','font-size':11},name+' · mavi: takım, turuncu: rakip');
       el('line',{x1:22,y1:118,x2:330,y2:118,stroke:'currentColor','stroke-opacity':.4});
       const step=300/matches.length;
       matches.forEach((m,i)=>{
        const x=25+step*i+(step-32)/2;
        for(const [j,key,color] of [[0,left,'#60a5fa'],[1,right,'#f59e0b']]){
         const n=m[key],h=85*n/max;
         el('rect',{x:x+j*17,y:118-h,width:14,height:h,fill:color});
         el('text',{x:x+j*17+7,y:114-h,fill:'currentColor','font-size':10,'text-anchor':'middle'},String(n));
        }
        el('text',{x:x+15,y:134,fill:'currentColor','font-size':10,'text-anchor':'middle'},String(i+1));
       });
       graph.append(svg);
      }
      const wrap=document.createElement('div');wrap.style.overflowX='auto';
      const table=document.createElement('table');table.setAttribute('aria-label','Son beş maç verileri');
      const header=table.createTHead().insertRow();
      for(const name of ['#','Rakip','Saha','Gol','Yenilen','Şut','Rakip şut','İsabet','Rakip isabet','Topa sahip olma','Pas başarısı']){
       const th=document.createElement('th');th.scope='col';th.textContent=name;header.append(th);
      }
      const body=table.createTBody();
      matches.forEach((m,i)=>{
       const row=body.insertRow();
       for(const v of [i+1,m.opponent,m.home?'İç saha':'Deplasman',m.goalsFor,m.goalsAgainst,m.shots,m.shotsAgainst,m.shotsOnTarget,m.shotsOnTargetAgainst,value(m.possessionPct,true),value(m.passAccuracyPct,true)])row.insertCell().textContent=v;
      });
      wrap.append(table);graph.append(wrap);
     }
     select.addEventListener('change',draw);draw();section.append(trend);
    }
    for(const record of history.records){
     const panel=document.createElement('details');
     const title=document.createElement('summary');title.textContent=record.homeTeam+' '+record.homeGoals+' - '+record.awayGoals+' '+record.awayTeam;panel.append(title);
     const table=document.createElement('table');table.setAttribute('aria-label','3D maç istatistikleri');
     const head=table.createTHead().insertRow();
     for(const label of ['İstatistik',record.homeTeam,record.awayTeam]){
      const th=document.createElement('th');th.scope='col';th.textContent=label;head.append(th);
     }
     const body=table.createTBody();
     for(const [label,key,percent] of [['Şut','shots',false],['İsabetli şut','shotsOnTarget',false],['Topa sahip olma','possessionPct',true],['Pas','passAttempts',false],['Başarılı pas','passesCompleted',false],['Pas başarısı','passAccuracyPct',true],['Faul','fouls',false]]){
      const row=body.insertRow();const th=document.createElement('th');th.scope='row';th.textContent=label;row.append(th);
      for(const v of record[key]||[null,null])row.insertCell().textContent=value(v,percent);
     }
     panel.append(table);section.append(panel);
    }
    if(!history.records.length||history.skipped||history.truncated){
     const warning=document.createElement('p');warning.textContent=!history.records.length?'Geçerli 3D maç kaydı bulunamadı.':'Bazı maçlar atlandı veya son 30 kayıtla sınırlandırıldı.';section.append(warning);
    }
    fragment.append(section);
   }else if(report.matchHistoryUnavailable){
    const p=document.createElement('p');p.textContent='3D maç geçmişi okunamadı; lig verileri ayrı olarak gösteriliyor.';fragment.append(p);
   }
   list.replaceChildren(fragment);
   note.textContent=count?count+' kayıt · Son tamamlanan oturum': 'Son oturumda okunabilir lig maçı kaydı bulunamadı.';
   if(report.skippedSaves||report.saveLimitReached)note.textContent+=' Bazı kayıtlar incelenemedi veya sınır nedeniyle atlandı.';
   if(report.createdAtUtc){
    const date=new Date(report.createdAtUtc);
    if(Number.isFinite(date.getTime()))note.textContent+=' · Rapor zamanı: '+date.toLocaleString('tr-TR');
   }
   if(report.snapshotConsistency==='different-saved-snapshot')note.textContent+=' Uyarı: Rapor güncel saklanmış lig kaydına ait değil.';
   else if(report.snapshotConsistency==='matches-saved-snapshot')note.textContent+=' · Saklanmış kayıt sürümüyle eşleşiyor (canlı veri değil).';
   else note.textContent+=' · Kayıt sürümü eşleşmesi doğrulanamadı.';
  } catch{if(seq===resultsSequence){list.replaceChildren();note.textContent='Yerel sonuç bağlantısı kullanılamıyor.';}}
 }
 let statusSequence=0,watchedRunning=false,pollTimer=null;
 function stopPoll(){if(pollTimer!==null){clearTimeout(pollTimer);pollTimer=null;}}
 function schedulePoll(){
  stopPoll();
  if(watchedRunning&&!busy&&!document.hidden)
   pollTimer=setTimeout(()=>{pollTimer=null;void update(false);},2000);
 }
 async function update(includeReport=true) {
  if(busy)return;
  stopPoll();
  const seq=++statusSequence;
  const wasRunning=watchedRunning;
  try{
   const r=await fetch('/api/original/status',{cache:'no-store'});
   if(!r.ok)throw Error();
   const state=await r.json();
   if(seq!==statusSequence||busy)return;
   watchedRunning=state.running===true;
   render(state);
   if(includeReport||wasRunning&&!watchedRunning)await updateResults();
  }catch{
   if(seq!==statusSequence||busy)return;
   launch.disabled=true;
   if(saveNote)saveNote.textContent='Lig kayıt deposu durumu alınamadı.';
   status.textContent='Yerel motor bağlantısı kullanılamıyor. Oyunu varsayılan yerel sunucudan aç.';
   if(includeReport)await updateResults();
  }finally{if(seq===statusSequence)schedulePoll();}
 }
 refresh.addEventListener('click',()=>void update(true));
 document.addEventListener('visibilitychange',()=>{
  if(document.hidden)stopPoll();
  else void update(true);
 });
 window.addEventListener('pagehide',stopPoll);
 window.addEventListener('pageshow',e=>{if(e.persisted)void update(true);});
 launch.addEventListener('click',async()=>{
  if(busy)return;busy=true;stopPoll();statusSequence++;launch.disabled=true;
  try{const r=await fetch('/api/original/launch',{method:'POST',headers:{'X-Tribun-Original':'launch'}});if(!r.ok)throw Error();status.textContent='Başlatma isteği kabul edildi. Masaüstü penceresini ve terminali kontrol et.';}
  catch{status.textContent='Başlatma isteği başarısız. Terminali kontrol et.';}
  finally{busy=false;await update();}
 });
 const team=document.getElementById('nativeTeam'), catalogNote=document.getElementById('nativeCatalogStatus'), details=document.getElementById('nativeCatalogDetails');
 let catalogSequence=0;
 function section(title,values){
  const h=document.createElement('h3');h.textContent=title;details.append(h);
  const ul=document.createElement('ul');
  for(const value of values){const li=document.createElement('li');li.textContent=value;ul.append(li);}
  details.append(ul);
 }
 async function loadTeam(){
  const seq=++catalogSequence;
  details.replaceChildren();catalogNote.textContent='Takım okunuyor…';
  try{
   const res=await fetch('/api/original/catalog?team='+encodeURIComponent(team.value),{cache:'no-store'});
   if(!res.ok)throw Error();
   const data=await res.json();if(seq!==catalogSequence)return;
   section('Kayıtlı oyuncular',data.players.map(p=>p.name+' · '+p.role+' · sıra: '+(p.formationOrder??'—')));
   section('Kayıtlı diziliş yuvaları',data.formation.map(p=>p.slot+' · '+(p.role??'—')+' · '+(p.rawPosition?.join(', ')??'—')));
   section('Orijinal taktik değerleri',data.tactics.map(t=>t.label+' : '+t.value+(t.source==='upstream-memory-default'?' (motorun varsayılan değeri)':'')));
   catalogNote.textContent=data.name+(data.truncated?' · Oyuncu listesi sınırlandırıldı.':' · Salt okunur kayıt.');
  }catch{if(seq===catalogSequence)catalogNote.textContent='Takım verisi okunamadı.';}
 }
 async function loadCatalog(){
  try{
   const res=await fetch('/api/original/catalog',{cache:'no-store'});if(!res.ok)throw Error();
   const data=await res.json();team.replaceChildren();
   for(const item of data.teams){const opt=document.createElement('option');opt.value=item.id;opt.textContent=item.name;team.append(opt);}
   team.disabled=!data.teams.length;
   if(data.teams.length)await loadTeam();else catalogNote.textContent='Kayıtlı takım bulunamadı.';
  }catch{team.disabled=true;catalogNote.textContent='Orijinal motor veri tabanı henüz kullanılamıyor.';}
 }
 team.addEventListener('change',loadTeam);
 refresh.addEventListener('click',loadCatalog);
 function loadManagerPlan(){
  const note=document.getElementById('managerPlanStatus'),panel=document.getElementById('managerPlanDetails');
  if(!note||!panel)return;
  panel.replaceChildren();
  let plan=null;
  try{plan=window.TribunOriginalManagerPlan.read(window.localStorage);}catch{}
  if(!plan){note.textContent='Bu tarayıcıda kaydedilmiş menajer planı bulunamadı.';return;}
  note.textContent='Web oyunundan okundu · Orijinal motora uygulanmadı.';
  function rows(title,values){
   const h=document.createElement('h3');h.textContent=title;panel.append(h);
   const ul=document.createElement('ul');
   for(const value of values){const li=document.createElement('li');li.textContent=value;ul.append(li);}
   panel.append(ul);
  }
  if(plan.formation)rows('Diziliş',[plan.formation]);
  if(plan.lineup)rows('Kaydedilmiş ilk 11',plan.lineup.map(p=>p.slot+'. '+p.name+(p.position?' · '+p.position:'')));
  else rows('İlk 11',['Tam ve geçerli bir ilk 11 kaydı bulunamadı.']);
  if(plan.tactics.length)rows('Kaydedilmiş web taktikleri',plan.tactics.map(t=>t.label+' : '+t.value));
 }
 refresh.addEventListener('click',loadManagerPlan);
 loadManagerPlan();
 update();loadCatalog();
})();
