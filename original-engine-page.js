'use strict';
(() => {
 const status=document.getElementById('originalStatus'), launch=document.getElementById('originalLaunch'), refresh=document.getElementById('originalRefresh');
 let busy=false;
 function render(s) {
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
  catch{launch.disabled=true;status.textContent='Yerel motor bağlantısı kullanılamıyor. Oyunu varsayılan yerel sunucudan aç.';}
  await updateResults();
 }
 refresh.addEventListener('click',update);
 launch.addEventListener('click',async()=>{
  if(busy)return;busy=true;launch.disabled=true;
  try{const r=await fetch('/api/original/launch',{method:'POST',headers:{'X-Tribun-Original':'launch'}});if(!r.ok)throw Error();status.textContent='Başlatma isteği kabul edildi. Masaüstü penceresini ve terminali kontrol et.';}
  catch{status.textContent='Başlatma isteği başarısız. Terminali kontrol et.';}
  finally{busy=false;await update();}
 });
 update();
})();
