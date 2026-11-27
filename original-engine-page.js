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
 async function updateResults() {
  const note=document.getElementById('nativeResultStatus'), list=document.getElementById('nativeResultList');
  list.replaceChildren();
  try {
   const response=await fetch('/api/original/results',{cache:'no-store'});
   if(!response.ok)throw Error();
   const {report}=await response.json();
   if(!report){note.textContent='Henüz tamamlanmış bir motor oturumu kaydı yok.';return;}
   if(report.exitCode!==0){note.textContent='Son motor oturumu hatayla kapandı; sonuç aktarılmadı.';return;}
   let count=0;
   for(const save of report.saves){
    const heading=document.createElement('h3');heading.textContent=save.saveName;list.append(heading);
    const rows=document.createElement('ul');
    for(const result of save.results){
     const row=document.createElement('li');
     row.textContent=result.nativeDate+' · '+result.homeTeam+' '+result.homeGoals+' - '+result.awayGoals+' '+result.awayTeam;
     rows.append(row);count++;
    }
    list.append(rows);
    if(save.truncated){const p=document.createElement('p');p.textContent='Yalnızca son 100 kayıt gösteriliyor.';list.append(p);}
   }
   note.textContent=count?count+' kayıt · Son tamamlanan oturum': 'Son oturumda okunabilir lig maçı kaydı bulunamadı.';
   if(report.skippedSaves||report.saveLimitReached)note.textContent+=' Bazı kayıtlar incelenemedi veya sınır nedeniyle atlandı.';
  } catch{note.textContent='Yerel sonuç bağlantısı kullanılamıyor.';}
 }
 async function update() {
  if(busy)return;
  try{const r=await fetch('/api/original/status',{cache:'no-store'});if(!r.ok)throw Error();render(await r.json());}
  catch{launch.disabled=true;if(saveNote)saveNote.textContent='Lig kayıt deposu durumu alınamadı.';status.textContent='Yerel motor bağlantısı kullanılamıyor. Oyunu varsayılan yerel sunucudan aç.';}
  await updateResults();
 }
 refresh.addEventListener('click',update);
 launch.addEventListener('click',async()=>{
  if(busy)return;busy=true;launch.disabled=true;
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
 update();loadCatalog();
})();
