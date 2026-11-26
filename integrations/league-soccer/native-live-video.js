'use strict';
(function(root){
 function playlist(text){
  const lines=text.trim().split(/\r?\n/);
  if(lines[0]!=='#EXTM3U'||!lines.includes('#EXT-X-MAP:URI="init.mp4"')||lines.some(l=>l.startsWith('#EXT-X-DISCONTINUITY')||l.startsWith('#EXT-X-KEY:')))throw Error('Unsupported playlist');
  const seq=lines.find(l=>l.startsWith('#EXT-X-MEDIA-SEQUENCE:'));
  if(seq&&seq!=='#EXT-X-MEDIA-SEQUENCE:0')throw Error('Unexpected sequence');
  const files=lines.filter(l=>l&&!l.startsWith('#'));
  if(files.length>500||files.some((f,i)=>f!=='segment-'+String(i).padStart(5,'0')+'.m4s'))throw Error('Invalid segment list');
  return {files,done:lines.includes('#EXT-X-ENDLIST')};
 }
 function codec(bytes){
  const a=new Uint8Array(bytes);
  for(let i=4;i+8<a.length;i++)if(a[i]===97&&a[i+1]===118&&a[i+2]===99&&a[i+3]===67&&a[i+4]===1){
   const size=new DataView(a.buffer,a.byteOffset+i-4,4).getUint32(0);
   if(size<15||i-4+size>a.length)continue;
   return 'video/mp4; codecs="avc1.'+[a[i+5],a[i+6],a[i+7]].map(n=>n.toString(16).padStart(2,'0')).join('')+'"';
  }
  throw Error('AVC configuration missing');
 }
 if(typeof module!=='undefined'&&module.exports){module.exports={playlist,codec};return;}
 const v=document.querySelector('#video'),button=document.querySelector('#start'),status=document.querySelector('#status');
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));let running=false,objectUrl=null;
 async function get(name,binary=false){const r=await fetch(name,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return binary?r.arrayBuffer():r.text();}
 async function waitPlaylist(){
  for(let i=0;i<240;i++){
   try{const p=playlist(await get('live.m3u8'));if(p.files.length)return p;}catch(e){if(e.message!=='HTTP 404')throw e;}
   await sleep(500);
  }throw Error('Yayın zaman aşımına uğradı.');
 }
 function event(el,name){return new Promise((resolve,reject)=>{const ok=()=>{el.removeEventListener('error',bad);resolve();},bad=()=>{el.removeEventListener(name,ok);reject(Error('Video buffer error'));};el.addEventListener(name,ok,{once:true});el.addEventListener('error',bad,{once:true});});}
 async function play(){
  if(running)return;running=true;button.disabled=true;status.textContent='İlk video parçası bekleniyor…';
  try{
   let p=await waitPlaylist();
   if(v.canPlayType('application/vnd.apple.mpegurl')){
    v.src='live.m3u8';await v.play();status.textContent='Native HLS oynatılıyor.';return;
   }
   if(!root.MediaSource)throw Error('Bu tarayıcı HLS veya MediaSource desteklemiyor.');
   const init=await get('init.mp4',true),mime=codec(init);
   if(!MediaSource.isTypeSupported(mime))throw Error('H.264 desteği bulunamadı.');
   const ms=new MediaSource();objectUrl=URL.createObjectURL(ms);
   const opened=event(ms,'sourceopen');v.src=objectUrl;await opened;
   const sb=ms.addSourceBuffer(mime);
   const append=async bytes=>{const finished=event(sb,'updateend');sb.appendBuffer(bytes);await finished;};
   await append(init);
   let next=Math.max(0,p.files.length-3),started=false,emptyPolls=0;
   while(true){
    const before=next;
    for(;next<p.files.length;next++){
     await append(await get(p.files[next],true));
     if(v.buffered.length){
      const start=v.buffered.start(0),end=v.buffered.end(v.buffered.length-1);
      if(!started){v.currentTime=start;await v.play();started=true;status.textContent='Orijinal motor görüntüsü oynatılıyor.';}
      else if(end-v.currentTime>8)v.currentTime=Math.max(start,end-2);
      if(v.currentTime-start>35){const finished=event(sb,'updateend');sb.remove(start,v.currentTime-15);await finished;}
     }
    }
    if(p.done){ms.endOfStream();status.textContent='Motor kaydı tamamlandı.';break;}
    emptyPolls=next===before?emptyPolls+1:0;
    if(emptyPolls>60)throw Error('Yeni video parçası alınamadı.');
    await sleep(500);p=playlist(await get('live.m3u8'));
   }
  }catch(e){status.textContent='Yayın açılamadı: '+e.message;running=false;button.disabled=false;v.pause();v.removeAttribute('src');v.load();if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;}
 }
 button.addEventListener('click',play);
 root.addEventListener('pagehide',()=>{if(objectUrl)URL.revokeObjectURL(objectUrl);});
})(typeof window!=='undefined'?window:globalThis);
