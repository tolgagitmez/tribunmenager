'use strict';
// Local preview only. No uploads, encoding, engine patches or automatic screen sharing.
(function(root){
 function createPreview({mediaDevices,video,onState}){
  let current=null,pending=false,generation=0;
  const stopTracks=stream=>{for(const track of stream?.getTracks()||[])track.stop();};
  const publish=(state,message)=>onState({state,message});
  const supported=!!mediaDevices?.getDisplayMedia;
  function stop(){
   generation++;pending=false;
   const stream=current;current=null;
   video.srcObject=null;stopTracks(stream);
   publish('idle','İzleme kapatıldı.');
  }
  async function start(){
   if(!supported){publish('unsupported','Bu tarayıcı pencere paylaşımını desteklemiyor.');return false;}
   if(pending||current)return false;
   const token=++generation;pending=true;
   publish('choosing','Pencere seçicisinden yalnızca League-Soccer penceresini seç.');
   let stream=null;
   try{
    // The browser always obtains fresh consent; the app cannot select a window silently.
    stream=await mediaDevices.getDisplayMedia({
     video:{displaySurface:'window',frameRate:{ideal:30,max:60}},audio:false,
     selfBrowserSurface:'exclude',surfaceSwitching:'exclude',monitorTypeSurfaces:'exclude'
    });
    if(token!==generation){stopTracks(stream);return false;}
    const tracks=stream.getVideoTracks();
    // Hint alone is not a guarantee. Reject monitor/tab/unknown surfaces.
    if(tracks.length!==1||tracks[0].getSettings().displaySurface!=='window'){
     stopTracks(stream);
     publish('error','Yalnızca ayrı uygulama penceresi paylaşılabilir. Ekran veya sekme seçme.');
     return false;
    }
    current=stream;
    tracks[0].addEventListener('ended',()=>{
     if(current!==stream)return;
     stop();
     publish('idle','Pencere paylaşımı sona erdi.');
    },{once:true});
    // Local muted preview, no server receives the stream.
    video.srcObject=stream;
    await video.play();
    if(token!==generation||current!==stream)return false;
    publish('playing','Seçilen pencere yerel olarak gösteriliyor. Pencerenin doğru motor olduğundan emin ol.');
    return true;
   }catch(error){
    if(current===stream){current=null;video.srcObject=null;}
    stopTracks(stream);
    if(token===generation)publish('error',error?.name==='NotAllowedError'?'Pencere paylaşımı iptal edildi veya izin verilmedi.':'Pencere görüntüsü açılamadı.');
    return false;
   }finally{
    if(token===generation)pending=false;
   }
  }
  return {start,stop,supported};
 }
 if(typeof module!=='undefined'&&module.exports){module.exports={createPreview};return;}
 const video=document.getElementById('originalPreviewVideo');
 const start=document.getElementById('originalPreviewStart'),stop=document.getElementById('originalPreviewStop');
 const status=document.getElementById('originalPreviewStatus');
 if(!video||!start||!stop||!status)return;
 const preview=createPreview({mediaDevices:root.navigator.mediaDevices,video,onState:({state,message})=>{
  status.textContent=message;
  start.disabled=state==='choosing'||state==='playing'||state==='unsupported';
  stop.disabled=state!=='choosing'&&state!=='playing';
 }});
 start.disabled=!preview.supported;
 if(!preview.supported)status.textContent='Yerel pencere paylaşımı bu tarayıcıda desteklenmiyor.';
 start.addEventListener('click',()=>preview.start());
 stop.addEventListener('click',()=>preview.stop());
 root.addEventListener('pagehide',()=>preview.stop());
})(typeof window!=='undefined'?window:globalThis);
