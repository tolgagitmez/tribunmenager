'use strict';
(function(root){
 function target(state,receivedAt,now,rtt){
  if(!state||state.durationSeconds!==300||!Number.isFinite(state.serverTimeMs)||
     !Number.isFinite(state.startTimeMs)||!Number.isFinite(receivedAt)||
     !Number.isFinite(now)||!Number.isFinite(rtt)||rtt<0||now<receivedAt)
   throw Error('Invalid server clock sample');
  return Math.max(0,Math.min(300,(state.serverTimeMs-state.startTimeMs+rtt/2+now-receivedAt)/1000));
 }
 function correction(actual,expected){
  const difference=expected-actual;
  if(Math.abs(difference)>.6)return {seek:expected,rate:1};
  return {seek:null,rate:Math.abs(difference)<.08?1:Math.max(.95,Math.min(1.05,1+difference*.15))};
 }
 function mount(document,fetcher,now){
  const video=document.querySelector('video'),status=document.getElementById('status');
  const sound=document.getElementById('sound');
  let identity=null,busy=false,closed=false,failures=0,timer=null;
  async function tick(){
   if(busy||closed)return;
   busy=true;
   try{
    const before=now();
    const response=await fetcher('/clock',{cache:'no-store',signal:AbortSignal.timeout(2500)});
    if(!response.ok)throw Error('Clock HTTP '+response.status);
    const state=await response.json(),after=now(),rtt=after-before;
    if(!/^[0-9a-f]{64}$/.test(state.replaySha256)||state.liveSimulation!==false||
       (identity&&identity!==state.replaySha256)||rtt>1000)throw Error('Invalid shared replay clock');
    identity=state.replaySha256;
    const expected=target(state,after,now(),rtt);
    if(video.readyState<1){status.textContent='Loading replay';return;}
    if(!Number.isFinite(video.duration)||Math.abs(video.duration-300)>.05)throw Error('Unexpected replay duration');
    if(expected>=300){
     video.pause();video.playbackRate=1;video.currentTime=video.duration;
     status.textContent='Replay finished';closed=true;clearInterval(timer);return;
    }
    if(expected===0&&state.phase==='waiting'){
     video.pause();video.currentTime=0;status.textContent='Waiting for server start';return;
    }
    const fix=correction(video.currentTime,expected);
    if(!video.seeking&&fix.seek!==null)video.currentTime=fix.seek;
    video.playbackRate=fix.rate;
    if(video.paused)await video.play();
    status.textContent='Shared replay · '+expected.toFixed(2)+' s';
    root.replayDiagnostics={identity,expected,current:video.currentTime,rtt,failures,phase:state.phase};
   }catch(error){
    failures++;video.pause();video.playbackRate=1;
    status.textContent='Waiting for shared clock connection';
    root.replayDiagnostics={identity,failures,error:String(error)};
   }finally{busy=false;}
  }
  sound.addEventListener('click',()=>{video.muted=!video.muted;});
  timer=setInterval(tick,500);tick();
  root.addEventListener('pagehide',()=>{closed=true;clearInterval(timer);video.pause();});
 }
 if(typeof module!=='undefined'&&module.exports){module.exports={target,correction};return;}
 mount(root.document,root.fetch.bind(root),()=>performance.now());
})(typeof window!=='undefined'?window:globalThis);
