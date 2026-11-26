'use strict';
(function(){
const $=id=>document.getElementById(id);
const rig=window.TribunHumanoidRig,api=window.TribunNativeReplay,scene=new Stadium3D($('pitch'));
scene.setPerformanceMode('balanced');
const tv=window.TribunBroadcastDesign.create(document);
$('renderMode').textContent=scene.gl?'WebGL 3D':'2D yedek görünüm';
let replay=null,frames=null,manifest=null,position=0,playing=false,last=null,generation=0,current=null,broadcast=null,broadcastStart=0;
let clipLibrary=null,clipStatus='idle',clipPromise=null;
const scheduler=window.TribunReplayPerformance.create();
let optimized=false,modelSeen=null,layoutKey='',sampleCalls=0,renderCalls=0,lastHud=0;
function invalidate(now=performance.now(),settle=0){scheduler.invalidate(now,settle);}
function stop(){playing=false;last=null;if(current)tv.phase(current.done?'MAÇ SONU':'DURAKLATILDI');$('play').textContent='Oynat';}
function endBroadcast(){broadcast=null;$('betaPresentation').disabled=$('basicPresentation').disabled=false;$('bodyBalance').disabled=$('footPlant').disabled=$('contactSync').disabled=$('strikeMotion').disabled=$('controlMotion').disabled=$('duelMotion').disabled=$('tackleMotion').disabled=$('keeperMotion').disabled=$('aerialMotion').disabled=$('animationBlend').disabled=$('motionMatching').disabled=$('playerMotionIdentity').disabled=$('playerAnatomy').disabled=$('nativeClips').disabled=$('contactPrecision').disabled=$('groundRecovery').disabled=$('keeperCompletion').disabled=false;$('play').disabled=$('seek').disabled=$('speed').disabled=!replay;$('broadcast').disabled=!replay?.complete;$('broadcast').textContent='5 dakikalık yayın';}
function reset(){replay?.reset(rig);scene.resetAnimation();last=null;current=null;if(optimized)scene.replayCameraSnap=true;invalidate();}
function draw(dt=0,renderDt=dt,reuse=false){
 const started=performance.now();
 if(!replay){current=null;scene.render([],{x:0,y:.11,z:0,vx:0,vy:0,vz:0},[0,0],{},renderDt);renderCalls++;scheduler.record(performance.now()-started);return;}
 if(!reuse||!current||Math.abs(current.elapsedMs-position)>1e-6){current=replay.sample(position,rig,dt);sampleCalls++;}
 const {players,ball,score,matchMs,done,stats}=current;
 scene.render(players,ball,[ball.x,ball.z],{},renderDt);renderCalls++;scheduler.record(performance.now()-started);
 if(optimized&&reuse)return;
 tv.update(current,{phase:done?'MAÇ SONU':broadcast?'KAYIT YAYINI':playing?'OYNATILIYOR':'DURAKLATILDI'});
 $('seek').value=position;
 $('score').textContent=Math.floor(matchMs/60000)+"′  "+score.join(' – ')+(done?' · MS':'');
 const labels={shots:'Şut',onTarget:'İsabetli şut',passes:'Pas denemesi',completed:'Başarılı pas',fouls:'Faul'};
 const rows=stats?Object.entries(labels).map(([k,v])=>v+': '+stats[k].join(' – ')):[];
 if(stats){const [a,b]=stats.possessionMs;if(a+b)rows.push('Topa sahip olma: %'+Math.round(a/(a+b)*100)+' – %'+Math.round(b/(a+b)*100));}
 $('stats').textContent=rows.join('\n')||'Bu kayıt istatistik içermiyor.';
}
function load(){
 stop();reset();replay=null;endBroadcast();tv.update(null);$('broadcastClock').textContent='';position=0;$('play').disabled=$('seek').disabled=true;$('score').textContent='Kayıt seçin';$('stats').textContent='İstatistik kaydı yok.';
 if(!frames){draw();return;}
 try{
  replay=api.create(frames,manifest,{bodyBalance:$('bodyBalance').checked,footPlant:$('footPlant').checked,contactSync:$('contactSync').checked,strikeMotion:$('strikeMotion').checked,controlMotion:$('controlMotion').checked,duelMotion:$('duelMotion').checked,tackleMotion:$('tackleMotion').checked,keeperMotion:$('keeperMotion').checked,aerialMotion:$('aerialMotion').checked,animationBlend:$('animationBlend').checked,motionMatching:$('motionMatching').checked,playerMotionIdentity:$('playerMotionIdentity').checked,playerAnatomy:$('playerAnatomy').checked||$('nativeClips').checked,clipLibrary:$('nativeClips').checked?clipLibrary:null,contactPrecision:$('contactPrecision').checked,groundRecovery:$('groundRecovery').checked,keeperCompletion:$('keeperCompletion').checked});$('seek').max=replay.duration;$('seek').value=0;$('play').disabled=$('seek').disabled=$('speed').disabled=false;$('broadcast').disabled=!replay.complete;
  $('status').textContent=replay.frames+' motor karesi · '+(replay.complete?'Tam maç kaydı':'Eksik kayıt')+' · '+(manifest?'Kadro eşleştirildi':'Kadro dosyası yok');draw();
 }catch(e){$('status').textContent=e.message;draw();}
}
async function ensureClips(){
 if(clipLibrary||clipPromise)return;
 clipStatus='loading';$('clipStatus').textContent='Klipler hazırlanıyor; prosedürel hareketler etkin.';
 clipPromise=(async()=>{
  try{
   const module=await import('./native-clip-loader.mjs');
   clipLibrary=await module.loadNativeClipLibrary();clipStatus='ready';
   $('clipStatus').textContent='4 proje klibi hazır; idle/run/shot üst gövde pilotu.';
   if($('nativeClips').checked&&!broadcast){const at=position,wasPlaying=playing;load();position=Math.min(at,replay?.duration||0);draw();if(wasPlaying){playing=true;$('play').textContent='Duraklat';}}
  }catch(e){clipStatus='fallback';$('clipStatus').textContent='Klipler yüklenemedi; prosedürel yedek etkin: '+e.message;}
  finally{clipPromise=null;}
 })();
 return clipPromise;
}
const presentationOptions=['bodyBalance','footPlant','contactSync','strikeMotion','controlMotion','duelMotion','tackleMotion','keeperMotion','aerialMotion','animationBlend','motionMatching','playerMotionIdentity','playerAnatomy','nativeClips','contactPrecision','groundRecovery','keeperCompletion','renderOptimization'];
function applyPreset(enabled){
 if(broadcast)return;
 const at=position,wasPlaying=playing;
 for(const id of presentationOptions)$(id).checked=enabled;
 optimized=enabled;configureGraphics();
 load();position=Math.min(at,replay?.duration||0);reset();draw();
 if(replay&&wasPlaying&&position<replay.duration){playing=true;last=null;$('play').textContent='Duraklat';}
 if(enabled)ensureClips();
}
$('betaPresentation').onclick=()=>applyPreset(true);
$('basicPresentation').onclick=()=>applyPreset(false);
$('nativeClips').onchange=()=>{if(!broadcast){load();if($('nativeClips').checked)ensureClips();}};
$('file').onchange=async()=>{
 const token=++generation;frames=null;manifest=null;$('manifest').value='';load();
 try{
  const f=$('file').files[0];if(!f)return;
  if(f.size>100*1024*1024)throw Error('Kayıt 100 MB sınırını aşıyor.');
  const data=api.parse(await f.text());if(token!==generation)return;frames=data;load();
 }catch(e){if(token===generation)$('status').textContent=e.message;}
};
$('manifest').onchange=async()=>{
 const token=++generation;manifest=null;stop();
 try{
  const f=$('manifest').files[0];if(f){if(f.size>1024*1024)throw Error('Kadro dosyası çok büyük.');const data=JSON.parse(await f.text());if(token!==generation)return;manifest=data;}
  if(token===generation)load();
 }catch(e){if(token===generation){load();$('status').textContent=e.message;}}
};
$('broadcast').onclick=()=>{
 if(broadcast){endBroadcast();stop();return;}
 try{
  broadcast=window.TribunNativeBroadcast.create(frames);
  stop();reset();position=0;broadcastStart=performance.now();
  $('play').disabled=$('seek').disabled=$('speed').disabled=true;$('bodyBalance').disabled=$('footPlant').disabled=$('contactSync').disabled=$('strikeMotion').disabled=$('controlMotion').disabled=$('duelMotion').disabled=$('tackleMotion').disabled=$('keeperMotion').disabled=$('aerialMotion').disabled=$('animationBlend').disabled=$('motionMatching').disabled=$('playerMotionIdentity').disabled=$('playerAnatomy').disabled=$('nativeClips').disabled=$('contactPrecision').disabled=$('groundRecovery').disabled=$('keeperCompletion').disabled=true;
  $('betaPresentation').disabled=$('basicPresentation').disabled=true;
  $('broadcast').textContent='Yayını kapat';
 }catch(e){$('status').textContent=e.message;}
};
$('play').onclick=()=>{if(!replay)return;if(playing){stop();return;}if(position>=replay.duration){position=0;reset();}playing=true;last=null;tv.phase('OYNATILIYOR');$('play').textContent='Duraklat';};
$('seek').oninput=()=>{stop();position=Number($('seek').value);reset();draw();};
$('camera').onclick=()=>{scene.camera=scene.camera==='tv'?'close':scene.camera==='close'?'tactical':'tv';$('camera').textContent='Kamera: '+({tv:'TV',close:'Yakın',tactical:'Taktik'}[scene.camera]);invalidate(performance.now(),1400);};
function configureGraphics(){
 scene.setPerformanceMode($('quality').value);
 const mobile=matchMedia('(max-width: 760px)').matches;
 scene.replayRenderBudget=optimized?window.TribunReplayPerformance.pixelBudget($('quality').value,mobile):null;
 scene.replayCameraSmooth=optimized;
 scene.instancingEnabled=optimized&&$('quality').value==='performance';
 invalidate(performance.now(),300);
}
$('quality').onchange=configureGraphics;
$('renderOptimization').onchange=()=>{optimized=$('renderOptimization').checked;configureGraphics();reset();draw();};
if(typeof ResizeObserver!=='undefined')new ResizeObserver(()=>{configureGraphics();}).observe($('pitch'));
window.addEventListener('resize',configureGraphics);
$('bodyBalance').onchange=$('footPlant').onchange=$('contactSync').onchange=$('strikeMotion').onchange=$('controlMotion').onchange=$('duelMotion').onchange=$('tackleMotion').onchange=$('keeperMotion').onchange=$('aerialMotion').onchange=$('animationBlend').onchange=$('motionMatching').onchange=$('playerMotionIdentity').onchange=$('playerAnatomy').onchange=$('contactPrecision').onchange=$('groundRecovery').onchange=$('keeperCompletion').onchange=()=>{if(!broadcast)load();};
document.addEventListener('visibilitychange',()=>{last=null;invalidate(performance.now(),200);});
function loop(now){
 const rawDt=last===null?0:Math.max(0,(now-last)/1000),dt=Math.min(.1,rawDt);last=now;
 const wasActive=!!(playing||broadcast);
 if(broadcast){
  const t=broadcast.at(now-broadcastStart);position=t.nativeOffsetMs;
  const sec=Math.ceil(t.remainingMs/1000);$('broadcastClock').textContent=String(Math.floor(sec/60)).padStart(2,'0')+':'+String(sec%60).padStart(2,'0')+' kaldı';
  if(t.phase==='finished'){endBroadcast();stop();}
 }
 if(playing&&replay&&!document.hidden){position=Math.min(replay.duration,position+dt*1000*Number($('speed').value));if(position>=replay.duration)stop();}
 if(!optimized){scene.observeFrame(dt,!playing&&!broadcast);draw(playing||broadcast?dt:0,dt);}
 else{
  const model=scene.playerRenderer,rect=$('pitch').getBoundingClientRect();
  const key=[rect.width,rect.height,window.devicePixelRatio||1].join(':');
  if(model!==modelSeen||key!==layoutKey){modelSeen=model;layoutKey=key;invalidate(now,250);}
  if(wasActive&&!playing&&!broadcast)invalidate(now,150);
  const active=!!(playing||broadcast);
  // Broadcast keeps its wall clock even when presentation is skipped.
  // Manual replay retains the existing bounded playback delta.
  if(scheduler.shouldDraw(now,active,document.hidden)){
   scene.observeFrame(rawDt,!active);
   draw(wasActive?dt:0,dt,!wasActive);scheduler.drawn(now);
  }
  if(now-lastHud>=500){
   lastHud=now;const p=scene.performanceMode(),m=scheduler.stats(),s=p.players;
   $('renderStats').textContent='Çizim: '+m.meanMs.toFixed(1)+' ms · '+p.canvas.join('×')+
    ' · '+(s?.drawCalls??0)+' oyuncu çizim çağrısı · '+(s?.triangles??0)+' üçgen · '+m.skipped+' atlanan kare';
  }
 }
 requestAnimationFrame(loop);
}
window.TRIBUN_NATIVE_REPLAY_TEST={state:()=>current&&({score:current.score,players:current.players.length,ball:current.ball,done:current.done,elapsedMs:current.elapsedMs}),webgl:()=>!!scene.gl,modelReady:()=>!!scene.playerRenderer,clipStatus:()=>clipStatus,clipCount:()=>clipLibrary?Object.keys(clipLibrary).length:0,clipSamples:()=>current?.players.filter(p=>rig.getPose(p).nativeClip).length||0,
 performance:()=>({optimized,sampleCalls,renderCalls,scheduler:scheduler.stats(),scene:scene.performanceMode()})};
requestAnimationFrame(loop);
})();
