'use strict';
(()=>{
const $=id=>document.getElementById(id),Rig=window.TribunHumanoidRig,Scenarios=window.TribunAnimationScenarios;
const scene=new Stadium3D($('animationCanvas'));scene.camera='portrait';scene.cameraSmoothing=[4.4,3.5,5.5];scene.cameraTarget=[0,.9,0];
const notes={run:['Koşu','Adım uzunluğu hızla değişir. Zemine basan ayağı ve diğer ayağın öne geçişini incele.'],turn:['Fren ve dönüş','Oyuncu yavaşlar, durur ve dönüş sırasında küçük yerleştirme adımları atar.'],pass:['Pas','Destek ayağı zeminde kalır. Vuruş ayağı topa ulaşır, ardından takip hareketi yapar.'],shoot:['Şut','Hazırlık, temas ve takip hareketini zaman çizgisinden ayrı ayrı incele.'],'dive-left':['Sola kurtarış','Kaleci gövdesini yana yatırır, iki eldivenini topa uzatır ve tekrar doğrulur.'],'dive-right':['Sağa kurtarış','Aynı kurtarışın ters yönünü ve eldivenlerin topa erişimini incele.']};
let state=Scenarios.create(),time=0,paused=false,speed=1,accumulator=0;
function update(dt){Scenarios.sample(state,time,Rig);Rig.update(state.p,dt);}
function seek(t){Rig.reset(state.p);state=Scenarios.create(state.mode);time=0;update(0);for(;time+1/60<=t+1e-8;){time+=1/60;update(1/60);}const rest=t-time;if(rest>1e-8){time=t;update(rest);}accumulator=0;refresh();}
function refresh(){const p=Rig.getPose(state.p);$('feetStatus').textContent=p.legs.filter(l=>l.stance).length+' / 2';$('timeStatus').textContent=time.toFixed(2)+' sn';$('timeLabel').textContent=time.toFixed(2)+' sn';$('timeline').value=time;$('play').textContent=paused?'Devam et':'Duraklat';}
function select(mode){state=Scenarios.create(mode);time=0;accumulator=0;Rig.reset(state.p);$('clipName').textContent=notes[mode][0];$('clipNote').textContent=scene.gl?notes[mode][1]:'WebGL kapalı. Eklem hareketlerini görmek için grafik hızlandırması açık bir tarayıcı kullan.';document.querySelectorAll('[data-mode]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.mode===mode)));$('contact').disabled=!['pass','shoot','dive-left','dive-right'].includes(mode);update(0);refresh();}
document.querySelectorAll('[data-mode]').forEach(el=>el.onclick=()=>select(el.dataset.mode));
$('play').onclick=()=>{paused=!paused;refresh();};$('slow').onclick=()=>{speed=speed===1?.25:speed===.25?.5:1;$('slow').textContent='Hız: '+speed+'×';};
$('step').onclick=()=>{paused=true;if(time+1/60>=8)select(state.mode);else{time+=1/60;update(1/60);}refresh();};
$('contact').onclick=()=>{paused=true;seek(state.mode==='shoot'?.38:state.mode==='pass'?.31:.34);};
$('timeline').oninput=e=>{paused=true;seek(Number(e.target.value));};
$('skeleton').onclick=()=>{scene.debugRig=!scene.debugRig;$('skeleton').textContent=scene.debugRig?'İskeleti gizle':'İskeleti göster';};
$('camera').onclick=()=>{scene.camera=scene.camera==='portrait'?'close':'portrait';$('camera').textContent=scene.camera==='portrait'?'Kamera: Yakın':'Kamera: Saha';};
$('renderMode').textContent=scene.gl?(scene.playerRenderer?'YENİ MODEL · WEBGL':'ÖNCEKİ MODEL · YEDEK GÖRÜNÜM'):'2D YEDEK · WEBGL KAPALI';if(!scene.gl){$('skeleton').disabled=true;$('clipNote').textContent='Tarayıcı WebGL açamadı. Eklem hareketlerini görmek için grafik hızlandırması açık bir tarayıcı kullan.';}
select('run');let last=performance.now();function frame(now){const dt=Math.min(.25,(now-last)/1000);last=now;if(!paused){accumulator+=dt*speed;while(accumulator>=1/60){accumulator-=1/60;time+=1/60;if(time>=8){select(state.mode);break;}update(1/60);}refresh();}scene.render([state.p],state.ball,[state.p.x,state.p.z],{},dt);requestAnimationFrame(frame);}requestAnimationFrame(frame);
})();
