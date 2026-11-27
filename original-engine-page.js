'use strict';
(() => {
 const status=document.getElementById('originalStatus'), launch=document.getElementById('originalLaunch'), refresh=document.getElementById('originalRefresh');
 let busy=false;
 function render(s) {
  launch.disabled=busy||!s.supported||!s.installed||s.running;
  status.textContent=!s.supported?'Bu işletim sistemi henüz desteklenmiyor.':!s.installed?'Motor paketi bulunamadı. Terminalden kurulum yap.':s.running?'Masaüstü motoru başlatılıyor veya çalışıyor.':s.lastExitCode!==null&&s.lastExitCode!==0?'Motor kapandı veya doğrulama başarısız oldu. Terminali kontrol et.':'Motor paketi mevcut. Başlatırken bütünlüğü doğrulanacak.';
 }
 async function update() {
  if(busy)return;
  try{const r=await fetch('/api/original/status',{cache:'no-store'});if(!r.ok)throw Error();render(await r.json());}
  catch{launch.disabled=true;status.textContent='Yerel motor bağlantısı kullanılamıyor. Oyunu varsayılan yerel sunucudan aç.';}
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
