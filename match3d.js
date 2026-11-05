'use strict';
/* Presentation adapter: football-sim owns rules/positions, this file owns controls and HUD. */
(function(){
const $=id=>document.getElementById(id),Rig=window.TribunHumanoidRig;
const escapeHtml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function config(){if(window.MATCH_CFG)return window.MATCH_CFG;let explicit=null,stored=null;try{if(location.hash)explicit=decodeURIComponent(location.hash.slice(1));}catch{}try{stored=sessionStorage.getItem('tribun-match-config');}catch{}for(const raw of [explicit,stored]){try{if(raw){const value=JSON.parse(raw);if(value&&typeof value==='object'&&!Array.isArray(value))return value;}}catch{}}return {};}

function label(id,text,name){const el=$(id);if(window.TribunUI){el.innerHTML=(name?window.TribunUI.icon(name):'')+'<span>'+text+'</span>';el.setAttribute('aria-label',text);}else el.textContent=text;}
const cfg=config(),scene=new Stadium3D($('stadiumCanvas'));
let game,paused=false,speed=1,accumulator=0,lastMetric=-1,shownFinish=false,overlayTime=0;
const portrait=p=>`assets/face${(p?.portraitId??4)%17}.png`;
const clock=seconds=>{seconds=Math.max(0,Math.floor(seconds+1e-7));return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');};
function init(){
 game=new window.TribunFootball.Match(cfg,Rig);paused=false;speed=1;accumulator=0;lastMetric=-1;shownFinish=false;overlayTime=0;
 $('eventList').innerHTML='';$('finishScreen').hidden=true;$('subPanel').hidden=true;$('bigMoment').classList.remove('show');$('stadiumWrap').classList.remove('goal-flash');
 label('playButton','Duraklat','pause');label('speedButton','1× Hız');label('camButton','Kamera: '+(scene.camera==='close'?'Yakın':scene.camera==='tactical'?'Taktik':'TV'),'target');label('rigButton','İskelet: '+(scene.debugRig?'Açık':'Kapalı'),'studio');label('soundButton','Tribün sesi: '+(crowd.enabled?'Açık':'Kapalı'),'sound');label('restartButton','Baştan oynat','refresh');$('momentum').dataset.left=50;$('momentum').style.setProperty('--homeWidth','50%');
 if($('sessionTitle'))$('sessionTitle').textContent=game.duration===5400?'90 DAKİKA · DENEYSEL MAÇ':`${game.duration/60} DAKİKALIK ${game.duration===300?'DENEME':'KISA MAÇ'}`;
 const t=game.t[0];$('homeFormation').textContent=`${cfg.formation||'4-3-3'} · ${window.TribunTactics.labels.playstyle[t.playstyle]}`;
 $('tacticHome').textContent=t.mentality==='attacking'?'Hücum':t.mentality==='defensive'?'Savunma':'Dengeli';$('tacticHomeText').textContent=window.TribunTactics.describe(t).attack;
 for(const p of game.players)Rig.update(p,0);consume();metrics();renderSubs();
}
function event(e){
 const p=game.players.find(p=>p.id===e.playerId),el=document.createElement('div');el.className='incident '+e.type;
 const icons={goal:'⚽',shot:'◎',save:'✋',tackle:'◆',pass:'↗',throw:'↔',corner:'⚑','goal-kick':'↗',yellow:'■',red:'■',half:'Ⅱ',end:'▣',whistle:'◉',foul:'!',sub:'↕',through:'↗',cross:'⌁',cutback:'↙',header:'◎',clearance:'↗',offside:'⚑'};
 // Text is inserted through textContent so squad names cannot inject markup.
 const minute=document.createElement('div');minute.className='event-min';minute.textContent=clock(e.time);
 const img=document.createElement(p?'img':'div');if(p){img.src=portrait(p);img.alt='';}else{img.className='event-no-face';img.textContent=icons[e.type]||'●';}
 const text=document.createElement('div'),title=document.createElement('b'),desc=document.createElement('p');title.textContent=e.title;desc.textContent=e.desc;text.append(title,desc);
 const symbol=document.createElement('span');symbol.className='event-symbol';symbol.textContent=icons[e.type]||'●';el.append(minute,img,text,symbol);$('eventList').prepend(el);
 while($('eventList').children.length>26)$('eventList').lastChild.remove();
 $('eventCount').textContent=game.events.length+' olay';$('eventTicker').textContent=`${clock(e.time)} · ${e.title}`;$('commentary').textContent=e.desc;
 if(e.type==='goal'){
  $('momentTitle').textContent='GOOOL!';$('momentDesc').textContent=`${game.score[0]} – ${game.score[1]} · ${e.player||'Takım'}`;$('bigMoment').className='moment show goal';overlayTime=2.5;$('stadiumWrap').classList.add('goal-flash');
 }
 // Chances remain visible. Crowd reacts without covering the pitch with a shot banner.
 if(['shot','header','save','goal'].includes(e.type))crowd.react(e.type);
 if(['whistle','half','foul','yellow','red','end'].includes(e.type))crowd.whistle();
}
function consume(){for(const e of game.drain())event(e);}
function metrics(){
 const m=game,total=m.possession[0]+m.possession[1],pos=total?Math.round(m.possession[0]/total*100):50;
 $('matchClock').textContent=clock(m.time);
 $('halfLabel').textContent=m.time>=m.duration/2?'2. DEVRE':'1. DEVRE';$('progressBar').style.width=m.time/m.duration*100+'%';$('realTime').textContent=clock(Math.ceil(m.duration-m.time))+' kaldı';
 $('scoreHome').textContent=m.score[0];$('scoreAway').textContent=m.score[1];$('statPoss').textContent=`%${pos} – %${100-pos}`;$('statShots').textContent=m.shots.join(' – ');$('statTarget').textContent=m.onTarget.join(' – ');$('statCards').textContent=`🟨 ${m.cards.join(' – ')} · 🟥 ${m.reds.join(' – ')}`;$('statFouls').textContent=m.fouls.join(' – ');
 if($('statPasses'))$('statPasses').textContent=`${m.completed[0]}/${m.passes[0]} – ${m.completed[1]}/${m.passes[1]}`;
 if($('statXg'))$('statXg').textContent=m.xg.map(n=>n.toFixed(2)).join(' – ');
 const r=m.restart||m.kick?.restartContext,labels={'kickoff':'SANTRA','throw':'TAÇ','corner':'KORNER','goal-kick':'AUT','free-kick':'SERBEST VURUŞ'};
 $('liveType').textContent=m.done?'TAMAMLANDI':m.goalPause?'GOL!':paused?'DURAKLATILDI':r?labels[r.kind]:m.flight?.kind==='shot'?'GOL POZİSYONU':'CANLI';
 const phaseNames={build:'Geriden oyun kurma',progress:'Pas bağlantılarıyla ilerleme',final:'Son bölge hücumu',counter:'Hızlı hücum',counterpress:'Kaybın ardından baskı',defend:'Savunma yerleşimi',press:'Baskı ve kademe'};if($('teamPhase'))$('teamPhase').textContent=m.done?'Maç tamamlandı':m.goalPause?'Gol sonrası hazırlık':r?'Duran top yerleşimi':phaseNames[m.tacticalPhase[0]]||'Takım yerleşiyor';
 if($('playState'))$('playState').textContent=m.goalPause?'Gol kutlaması · Santra hazırlanıyor':r?`${r.team===0?'Ev sahibi':'Konuk takım'} · ${labels[r.kind]}`:m.owner?`${m.owner.name} · ${m.owner.holdingBall?'Topu tuttu':m.owner.receiveClock>0?(m.owner.receiveMode==='one-touch'?'Tek pas hazırlığı':m.owner.receiveMode==='open'?'Boşluğa ilk kontrol':'İlk kontrol'):'Topla ilerliyor'}`:m.flight?.kind==='shot'?'Top kaleye gidiyor':m.flight?.kind==='cross'?'Ceza sahasına orta':m.flight?.kind==='through'?'Savunma arkasına pas':'Top oyunda · Takımlar yerleşiyor';
 let left=Number($('momentum').dataset.left||50),target=m.ball.x>0?60:40;left+=(target-left)*.12;$('momentum').dataset.left=left;$('momentum').style.setProperty('--homeWidth',left+'%');
 if(m.done&&!shownFinish){shownFinish=true;$('finishScreen').hidden=false;$('finishScore').textContent=m.score.join(' – ');$('finishText').textContent=`${m.shots.join('–')} şut · ${m.completed.join('–')} başarılı pas · ${m.fouls.join('–')} faul. Yerel gösterim maçıdır; günlük lig sonucunu değiştirmez.`;}
}
function tick(dt){
 if(paused||game.done)return;accumulator+=Math.min(.25,Math.max(0,dt))*speed;
 while(accumulator+1e-10>=1/60&&!game.done){accumulator-=1/60;game.step();for(const p of game.players){p.selected=p===game.owner;if(p.active)Rig.update(p,1/60);}if(overlayTime>0){overlayTime-=1/60;if(overlayTime<=0){$('bigMoment').classList.remove('show');$('stadiumWrap').classList.remove('goal-flash');}}}
 consume();const metric=Math.floor(game.time*5+1e-7);if(metric!==lastMetric||game.done){metrics();lastMetric=metric;}
}
function renderSubs(){
 $('subOut').innerHTML=game.field(0).map(p=>`<option value="${p.index}">${escapeHtml(p.name)} (${p.skill})</option>`).join('');
 $('subIn').innerHTML=game.bench().map(p=>`<option value="${p.id}">${escapeHtml(p.name)} (${p.rating})</option>`).join('');$('saveSubs').disabled=game.done||game.subCount>=3||!game.bench().length;
 $('subsLeft').textContent=game.bench().length?`Kalan değişiklik: ${3-game.subCount}`:'Kadro ekranından maç başlatırsan yedekleri kullanabilirsin.';
}
// Original synthesized stadium bed. Audio only starts with an explicit button press.
const crowd={ctx:null,gain:null,enabled:false,ready(){
 if(this.ctx)return;const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return;
 this.ctx=new Audio();const c=this.ctx,b=c.createBuffer(1,c.sampleRate*3,c.sampleRate),data=b.getChannelData(0);let seed=1657;for(let i=0;i<data.length;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;data[i]=(seed/4294967296*2-1)*.35;}
 const src=c.createBufferSource();src.buffer=b;src.loop=true;const filter=c.createBiquadFilter();filter.type='lowpass';filter.frequency.value=950;this.gain=c.createGain();this.gain.gain.value=0;src.connect(filter);filter.connect(this.gain);this.gain.connect(c.destination);src.start();
},toggle(){this.ready();if(!this.ctx)return false;this.enabled=!this.enabled;this.ctx.resume();this.gain.gain.setTargetAtTime(this.enabled?.12:0,this.ctx.currentTime,.2);return this.enabled;},react(type){if(!this.enabled)return;const t=this.ctx.currentTime,g=this.gain.gain;g.cancelScheduledValues(t);g.setTargetAtTime(type==='goal'?.5:type==='save'?.3:.23,t,.12);g.setTargetAtTime(.12,t+(type==='goal'?2.7:1.0),.7);},whistle(){if(!this.enabled)return;const c=this.ctx,o=c.createOscillator(),g=c.createGain(),t=c.currentTime;o.frequency.value=2350;o.connect(g);g.connect(c.destination);g.gain.setValueAtTime(.018,t);g.gain.exponentialRampToValueAtTime(.0001,t+.16);o.start(t);o.stop(t+.18);}
};
window.addEventListener('DOMContentLoaded',()=>{
 if(!scene.gl){const a=document.querySelector?.('.webgl');if(a)a.textContent='2D YEDEK';$('rigButton').disabled=true;}
 $('playButton').onclick=()=>{paused=!paused;label('playButton',paused?'Devam et':'Duraklat',paused?'play':'pause');metrics();};$('restartButton').onclick=init;$('againButton').onclick=init;
 $('camButton').onclick=()=>{scene.camera=scene.camera==='tv'?'close':scene.camera==='close'?'tactical':'tv';label('camButton',scene.camera==='tv'?'Kamera: TV':scene.camera==='close'?'Kamera: Yakın':'Kamera: Taktik','target');};
 $('rigButton').onclick=()=>{scene.debugRig=!scene.debugRig;label('rigButton',scene.debugRig?'İskelet: Açık':'İskelet: Kapalı','studio');};
 $('speedButton').onclick=()=>{const levels=[1,1.5,.75,4,8,16];speed=levels[(levels.indexOf(speed)+1)%levels.length];label('speedButton',speed+'× Hız');};
 if($('soundButton'))$('soundButton').onclick=()=>{label('soundButton',crowd.toggle()?'Tribün sesi: Açık':'Tribün sesi: Kapalı','sound');};
 $('subButton').onclick=()=>{renderSubs();$('subPanel').hidden=!$('subPanel').hidden;};$('closeSubs').onclick=()=>{$('subPanel').hidden=true;};
 $('saveSubs').onclick=()=>{const result=game.substitute(Number($('subOut').value),Number($('subIn').value));if(result.ok){$('subPanel').hidden=true;consume();renderSubs();}else alert(result.error);};
 function start(){init();let last=performance.now();function frame(now){const dt=Math.min(.25,(now-last)/1000);last=now;tick(dt);const b=game.ball;scene.render(game.players,b,[b.x+b.vx*.25,b.z+b.vz*.25],{},dt);requestAnimationFrame(frame);}requestAnimationFrame(frame);}
 if(window.TribunTransfers?.hasSession()){
  const controls=[...document.querySelectorAll('.match-controls button,#subButton,#saveSubs,#againButton,#restartButton,#playButton,#speedButton')];controls.forEach(b=>b.disabled=true);
  $('sessionTitle').textContent='GÜNCEL KADRO ALINIYOR…';
  window.TribunTransfers.sync().then(data=>{const current=window.TribunTransfers.cached();cfg.players=data.players;cfg.starters=window.TribunClubData.repairStarters(current.starters,data.players,cfg.formation);cfg.special=current.special||cfg.special;controls.forEach(b=>b.disabled=false);start();}).catch(()=>{$('sessionTitle').textContent='TRANSFER BAĞLANTISI KURULAMADI · SAYFAYI YENİLE';});
 }else start();
});
window.TRIBUN_MATCH_TEST={getState:()=>({...game,elapsed:game.time,paused,speed,players:game.players,phase:game.phase,kickTask:game.kick}),advance:(n=1)=>{for(let i=0;i<Math.round(n*60);i++)tick(1/60);},restart:init,frame:tick,substitute:(a,b)=>game.substitute(a,b),benchPlayers:()=>game.bench()};
})();
