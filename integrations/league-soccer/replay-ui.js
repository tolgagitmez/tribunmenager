'use strict';
(function(){
const $=id=>document.getElementById(id);
const rig=window.TribunHumanoidRig,api=window.TribunNativeReplay,scene=new Stadium3D($('pitch'));
scene.setPerformanceMode('balanced');
$('renderMode').textContent=scene.gl?'WebGL 3D':'2D yedek görünüm';
let replay=null,frames=null,manifest=null,position=0,playing=false,last=null,generation=0,current=null;
function stop(){playing=false;last=null;$('play').textContent='Oynat';}
function reset(){replay?.reset(rig);scene.resetAnimation();last=null;}
function draw(dt=0){
 if(!replay){current=null;scene.render([],{x:0,y:.11,z:0,vx:0,vy:0,vz:0},[0,0],{},0);return;}
 current=replay.sample(position,rig,dt);
 const {players,ball,score,matchMs,done,stats}=current;
 scene.render(players,ball,[ball.x,ball.z],{},dt);
 $('seek').value=position;
 $('score').textContent=Math.floor(matchMs/60000)+"′  "+score.join(' – ')+(done?' · MS':'');
 const labels={shots:'Şut',onTarget:'İsabetli şut',passes:'Pas denemesi',completed:'Başarılı pas',fouls:'Faul'};
 const rows=stats?Object.entries(labels).map(([k,v])=>v+': '+stats[k].join(' – ')):[];
 if(stats){const [a,b]=stats.possessionMs;if(a+b)rows.push('Topa sahip olma: %'+Math.round(a/(a+b)*100)+' – %'+Math.round(b/(a+b)*100));}
 $('stats').textContent=rows.join('\n')||'Bu kayıt istatistik içermiyor.';
}
function load(){
 stop();reset();replay=null;position=0;$('play').disabled=$('seek').disabled=true;$('score').textContent='Kayıt seçin';$('stats').textContent='İstatistik kaydı yok.';
 if(!frames){draw();return;}
 try{
  replay=api.create(frames,manifest);$('seek').max=replay.duration;$('seek').value=0;$('play').disabled=$('seek').disabled=false;
  $('status').textContent=replay.frames+' motor karesi · '+(replay.complete?'Tam maç kaydı':'Eksik kayıt')+' · '+(manifest?'Kadro eşleştirildi':'Kadro dosyası yok');draw();
 }catch(e){$('status').textContent=e.message;draw();}
}
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
$('play').onclick=()=>{if(!replay)return;if(playing){stop();return;}if(position>=replay.duration){position=0;reset();}playing=true;last=null;$('play').textContent='Duraklat';};
$('seek').oninput=()=>{stop();position=Number($('seek').value);reset();draw();};
$('camera').onclick=()=>{scene.camera=scene.camera==='tv'?'close':scene.camera==='close'?'tactical':'tv';$('camera').textContent='Kamera: '+({tv:'TV',close:'Yakın',tactical:'Taktik'}[scene.camera]);};
$('quality').onchange=()=>scene.setPerformanceMode($('quality').value);
document.addEventListener('visibilitychange',()=>{last=null;});
function loop(now){
 const dt=last===null?0:Math.min(.1,Math.max(0,(now-last)/1000));last=now;
 if(playing&&replay&&!document.hidden){position=Math.min(replay.duration,position+dt*1000*Number($('speed').value));if(position>=replay.duration)stop();}
 scene.observeFrame(dt,!playing);draw(playing?dt:0);requestAnimationFrame(loop);
}
window.TRIBUN_NATIVE_REPLAY_TEST={state:()=>current&&({score:current.score,players:current.players.length,ball:current.ball,done:current.done}),webgl:()=>!!scene.gl};
requestAnimationFrame(loop);
})();
