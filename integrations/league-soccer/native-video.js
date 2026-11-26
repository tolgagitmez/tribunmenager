'use strict';
(function(){
 const input=document.querySelector('#nativeVideo'),video=document.querySelector('#nativeVideoPlayer'),status=document.querySelector('#nativeVideoStatus');
 let url=null;
 function clear(){video.pause();video.removeAttribute('src');video.load();if(url)URL.revokeObjectURL(url);url=null;}
 input.addEventListener('change',()=>{
  clear();const f=input.files[0];if(!f){status.textContent='Yerel dosya seçilmedi.';return;}
  if(!/\.mp4$/i.test(f.name)||f.size===0||f.size>1024*1024*1024){status.textContent='Geçerli, en fazla 1 GB MP4 seç.';return;}
  url=URL.createObjectURL(f);status.textContent='Yerel video açılıyor…';video.src=url;
 });
 video.addEventListener('loadedmetadata',()=>{if(url)status.textContent='Yerel video hazır. Motor kaydının doğruluğu bu sayfada doğrulanmaz.';});
 video.addEventListener('error',()=>{if(url)status.textContent='Video oynatılamadı. MP4/H.264 uyumluluğunu kontrol et.';});
 window.addEventListener('pagehide',clear);
})();
