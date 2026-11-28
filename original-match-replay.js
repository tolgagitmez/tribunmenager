'use strict';
(function(root){
 function validDuration(seconds){
  return Number.isFinite(seconds)&&seconds>0&&seconds<=300;
 }
 function mount(document,urls){
  const input=document.getElementById('nativeReplayFile');
  const video=document.getElementById('nativeReplayVideo');
  const note=document.getElementById('nativeReplayStatus');
  const clear=document.getElementById('nativeReplayClear');
  if(!input||!video||!note||!clear)return;
  let url=null,generation=0;
  function reset(message,resetInput=true){
   generation++;
   video.pause();video.hidden=true;video.controls=false;
   video.onloadedmetadata=null;video.onerror=null;
   video.removeAttribute('src');video.load();
   if(url!==null){urls.revokeObjectURL(url);url=null;}
   if(resetInput)input.value='';
   clear.disabled=true;note.textContent=message;
  }
  input.addEventListener('change',()=>{
   const file=input.files&&input.files[0];
   reset('Kayıt seçilmedi.',false);
   if(!file)return;
   if(!/\.mp4$/i.test(file.name)||file.size<=0||file.size>2*1024*1024*1024){
    reset('Geçerli, en fazla 2 GB boyutunda MP4 kaydı seç.');return;
   }
   const id=generation;
   try{url=urls.createObjectURL(file);}catch{reset('Yerel kayıt açılamadı.');return;}
   clear.disabled=false;note.textContent='Kayıt süresi kontrol ediliyor…';
   video.onloadedmetadata=()=>{
    if(id!==generation)return;
    if(!validDuration(video.duration)||!video.videoWidth||!video.videoHeight){
     reset('Kayıt geçersiz veya 300 saniyeden uzun. Önce yerel dönüşümü tamamla.');return;
    }
    video.controls=true;video.hidden=false;
    note.textContent='Yerel tekrar · '+video.duration.toFixed(2)+' saniye · Canlı değil.';
   };
   video.onerror=()=>{if(id===generation)reset('Video okunamadı veya biçim desteklenmiyor.');};
   video.src=url;
  });
  clear.addEventListener('click',()=>reset('Kayıt kapatıldı.'));
  root.addEventListener('pagehide',()=>reset('Kayıt kapatıldı.'));
 }
 if(typeof module!=='undefined'&&module.exports){module.exports={validDuration,mount};return;}
 mount(root.document,root.URL);
})(typeof window!=='undefined'?window:globalThis);
