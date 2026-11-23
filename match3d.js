'use strict';
/* Presentation adapter: football-sim owns rules/positions, this file owns controls and HUD. */
(function(){
const $=id=>document.getElementById(id),Rig=window.TribunHumanoidRig;
const escapeHtml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function config(){if(window.MATCH_CFG)return window.MATCH_CFG;let explicit=null,stored=null;try{if(location.hash)explicit=decodeURIComponent(location.hash.slice(1));}catch{}try{stored=sessionStorage.getItem('tribun-match-config');}catch{}for(const raw of [explicit,stored]){try{if(raw){const value=JSON.parse(raw);if(value&&typeof value==='object'&&!Array.isArray(value))return value;}}catch{}}return {};}

function label(id,text,name){const el=$(id);if(window.TribunUI){el.innerHTML=(name?window.TribunUI.icon(name):'')+'<span>'+text+'</span>';el.setAttribute('aria-label',text);}else el.textContent=text;}
const cfg=config(),scene=new Stadium3D($('stadiumCanvas'));
const query=new URLSearchParams(location.search),liveRound=query.get('live');
const pilotRequested=query.get('pilot')==='1';
const pilotId=query.get('pilotPlayer')||'0';
const pilotPlayer=/^(?:[0-9]|1[0-9]|2[01])$/.test(pilotId)?Number(pilotId):0;
let pilotError=null;
let localContacts;
let game,attackObserver,attackView,paused=false,speed=1,accumulator=0,lastMetric=-1,lastMetricWall=0,simOverloadFrames=0,shownFinish=false,overlayTime=0,lastFrameCost=null;
let kickPanel,kickAim,visibleKick=null,kickStage=0,kickFollow=null;
let live,liveSide=0,liveKickSending=false;
const radians=Math.PI/180;
const portrait=p=>`assets/face${(p?.portraitId??4)%17}.png`;
const clock=seconds=>{seconds=Math.max(0,Math.floor(seconds+1e-7));return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');};
const matchClock=()=>typeof game.clockState==='function'?game.clockState():{period:game.time>=game.duration/2?2:1,phase:game.done?'finished':'playing',display:clock(game.time),nominalElapsed:game.time,remaining:Math.max(0,game.duration-game.time),addedSeconds:0,addedAnnounced:false,halftimeRemaining:0};
function substitutionState(){
 if(typeof game.canSubstitute==='function')return game.canSubstitute();
 const maximum=game.rules?.maxSubstitutions??5,remaining=Math.max(0,maximum-game.subCount);
 return {ok:!game.done&&remaining>0,reason:game.done?'Maç tamamlandı.':remaining===0?'Değişiklik hakkı kalmadı.':'',remaining,windowsRemaining:Math.max(0,(game.rules?.substitutionWindows??3)-(game.subWindowsUsed||0))};
}
function closeKickControls(){
 if(!visibleKick)return;
 visibleKick=null;kickStage=0;
 kickAim.hide();kickPanel.hide();
 $('managerKickPanel').hidden=true;
 $('stadiumWrap').removeAttribute('data-kick-active');
 for(const id of ['playButton','subButton'])$(id).disabled=!!live;
 $('camButton').disabled=false;
}
const ownKick=()=>game.pendingManagerKick?.team===liveSide?game.pendingManagerKick:null;
function syncKickControls(){
 const opportunity=ownKick();
 if(opportunity?.id===visibleKick?.id)return;
 closeKickControls();
 if(!opportunity){scene.managerKickView=null;return;}
 visibleKick=opportunity;kickFollow=null;accumulator=0;
 $('stadiumWrap').setAttribute('data-kick-active','');
 $('subPanel').hidden=true;
 for(const id of ['playButton','subButton','camButton'])$(id).disabled=true;
 $('managerKickPanel').hidden=false;
 kickPanel.show({...opportunity,direction:0,angleRangeDeg:Math.round(opportunity.angleRange/radians),power:Math.round(opportunity.power*100)});
}
async function finishKick(id,input){
 const opportunity=visibleKick;
 if(!opportunity||opportunity.id!==id||liveKickSending)return;
 const restartId=game.restart?.id,releaseSerial=game.releaseSerial;
 const command=input?{
  angle:opportunity.angle+input.direction*radians,
  power:input.power/100,contactX:input.contactX,contactY:input.contactY
 }:undefined;
 let accepted;
 if(live){
  liveKickSending=true;
  $('managerKickPanel').setAttribute('aria-busy','true');
  try{accepted=await live.strike(id,command);}
  finally{$('managerKickPanel').removeAttribute('aria-busy');liveKickSending=false;}
 }else accepted=game.resolveManagerKick(id,command);
 if(!accepted){syncKickControls();return;}
 closeKickControls();
 // Retain the view for the approach and the first part of the ball flight.
 kickFollow=input?{restartId,releaseSerial,playerId:opportunity.playerId,duration:opportunity.kind==='penalty'?1.3:2,until:null}:null;
 scene.managerKickView=command?{...opportunity,angle:command.angle}:null;
 consume();metrics();
 $('stadiumWrap').scrollIntoView?.({block:'start'});
 (live?$('camButton'):$('playButton')).focus({preventScroll:true});
}
function updateKickCamera(){
 if(!kickFollow)return;
 if(game.releaseSerial!==kickFollow.releaseSerial&&kickFollow.until===null)kickFollow.until=game.time+kickFollow.duration;
 const newRestart=game.restart&&game.restart.id!==kickFollow.restartId;
 const aborted=kickFollow.until===null&&!game.restart&&(game.kick?.p?.id??game.kick?.playerId)!==kickFollow.playerId;
 if(game.done||game.goalPause||newRestart||aborted||kickFollow.until!==null&&game.time>=kickFollow.until){
  scene.managerKickView=null;kickFollow=null;
 }
}
function init(){
 if(attackObserver)attackObserver.detach();
 closeKickControls();scene.managerKickView=null;kickFollow=null;
 game=new window.TribunFootball.Match({...cfg,managerKicks:cfg.managerKicks!==false},Rig);scene.resetAnimation();attackObserver=window.TribunAttackDiagnostics.attach(game);
 if(pilotRequested&&scene.gl){
  localContacts=window.TribunContactEvents.create();
  localContacts.observe(game);
 }
 if(!attackView)attackView=window.TribunAttackAnalysisUI.mount($('attackAnalysis'),{summary:()=>attackObserver.summary(),report:()=>attackObserver.report()});
 resetPresentation();
}
function resetPresentation(){
 paused=false;speed=1;accumulator=0;lastMetric=-1;lastMetricWall=0;simOverloadFrames=0;shownFinish=false;overlayTime=0;
 $('eventList').innerHTML='';$('finishScreen').hidden=true;$('subPanel').hidden=true;if($('halftimePanel'))$('halftimePanel').hidden=true;$('bigMoment').classList.remove('show');$('stadiumWrap').classList.remove('goal-flash');
 label('playButton','Duraklat','pause');label('speedButton','1× Hız');label('camButton','Kamera: '+(scene.camera==='close'?'Yakın':scene.camera==='tactical'?'Taktik':'TV'),'target');label('rigButton','İskelet: '+(scene.debugRig?'Açık':'Kapalı'),'studio');label('soundButton','Tribün sesi: '+(crowd.enabled?'Açık':'Kapalı'),'sound');label('restartButton','Baştan oynat','refresh');$('momentum').dataset.left=50;$('momentum').style.setProperty('--homeWidth','50%');
 if($('sessionTitle'))$('sessionTitle').textContent=live?'GÜNLÜK LİG · CANLI MAÇ':(game.duration===5400?'90 DAKİKA · DENEYSEL MAÇ':`${game.duration/60} DAKİKALIK ${game.duration===300?'DENEME':'KISA MAÇ'}`)+(cfg.opponentSource==='demo'?' · DENEME KADROSU':cfg.opponentSource==='linked-roster'?' · FİKSTÜR KADROSU':'');
 const t=game.t[0];$('homeFormation').textContent=`${cfg.formation||'4-3-3'} · ${window.TribunTactics.labels.playstyle[t.playstyle]}`;
 $('tacticHome').textContent=t.mentality==='attacking'?'Hücum':t.mentality==='defensive'?'Savunma':'Dengeli';$('tacticHomeText').textContent=window.TribunTactics.describe(t).attack;
 const own=document.querySelector('.scoreboard .club:not(.away)'),away=document.querySelector('.scoreboard .club.away');
 if(own){own.querySelector('strong').textContent=cfg.homeName||'Moreirense SK';own.querySelector('small').textContent=live?'EV SAHİBİ'+(liveSide===0?' · SENİN TAKIMIN':''):cfg.fixture?.isHome===false?'DEPLASMAN · SENİN TAKIMIN':'EV SAHİBİ · SENİN TAKIMIN';}
 if(away){away.querySelector('strong').textContent=cfg.awayName||'Rakip';away.querySelector('small').textContent=live?'DEPLASMAN'+(liveSide===1?' · SENİN TAKIMIN':''):cfg.fixture?.isHome===false?'EV SAHİBİ · RAKİP':'DEPLASMAN · RAKİP';away.querySelector('span').textContent=`${cfg.awayFormation||'4-2-3-1'} · ${window.TribunTactics.labels.playstyle[game.t[1].playstyle]}`;}
 const legend=document.querySelectorAll('.legend span');if(legend[0])legend[0].textContent='● '+(cfg.homeName||'Takımın');if(legend[1])legend[1].textContent=(cfg.awayName||'Rakip')+' ●';
 const awayEffect=document.querySelectorAll('.effects>div')[1];if(awayEffect){awayEffect.querySelector('b').textContent=game.t[1].mentality==='attacking'?'Hücum':game.t[1].mentality==='defensive'?'Savunma':'Dengeli';awayEffect.querySelector('p').textContent=window.TribunTactics.describe(game.t[1]).attack;}
 const note=document.querySelector('.bottom-note');if(note)note.textContent=live?'Maç sonucu lig tablosuna işlenir.':cfg.rosterNotice||'Seçilen kadrolarla yerel maç; günlük lig sonucu değişmez.';
 for(const p of game.players)Rig.update(p,0);consume(!live);metrics();if(!live)renderSubs();
}
function liveNotice(message){
 const notice=$('liveMatchNotice');
 notice.hidden=!message;
 if(notice.textContent!==message)notice.textContent=message;
}
function updateLiveNotice(update){
 const active=game.pendingManagerKick,seconds=Math.ceil(update.decisionSeconds);
 if(game.done)return liveNotice('Maç tamamlandı.');
 if(update.catchingUp)return liveNotice('Maçın güncel anına geçiliyor…');
 if(active){
  const timer=seconds>0?` · ${seconds} sn`:'';
  return liveNotice((active.team===liveSide?'Vuruşu sen kullanıyorsun.':'Rakip menajer vuruşunu seçiyor.')+timer);
 }
 liveNotice(update.opponentPresent?'Rakip menajer maçı izliyor.':'Rakip takımın vuruşlarını oyuncuları kullanacak.');
}
function event(e,animate){
 const p=game.players.find(p=>p.id===e.playerId),el=document.createElement('div');el.className='incident '+e.type;
 const icons={goal:'⚽',shot:'◎',save:'✋',tackle:'◆',pass:'↗',throw:'↔',corner:'⚑','goal-kick':'↗',penalty:'◎',advantage:'↗','advantage-recall':'!',yellow:'■',red:'■',half:'Ⅱ','second-half':'▶','added-time':'+',end:'▣',whistle:'◉',foul:'!',sub:'↕',through:'↗',cross:'⌁',cutback:'↙',header:'◎',clearance:'↗',offside:'⚑','post':'◉','crossbar':'◉'};
 // Text is inserted through textContent so squad names cannot inject markup.
 const eventClock=e.clockDisplay||e.clock?.display||clock(e.time);
 const minute=document.createElement('div');minute.className='event-min';minute.textContent=eventClock;
 const img=document.createElement(p?'img':'div');if(p){img.src=portrait(p);img.alt='';}else{img.className='event-no-face';img.textContent=icons[e.type]||'●';}
 const text=document.createElement('div'),title=document.createElement('b'),desc=document.createElement('p');title.textContent=e.title;desc.textContent=e.desc;text.append(title,desc);
 const symbol=document.createElement('span');symbol.className='event-symbol';symbol.textContent=icons[e.type]||'●';el.append(minute,img,text,symbol);$('eventList').prepend(el);
 while($('eventList').children.length>26)$('eventList').lastChild.remove();
 $('eventCount').textContent=(game.eventSerial??game.events.length)+' olay';$('eventTicker').textContent=`${eventClock} · ${e.title}`;$('commentary').textContent=e.desc;
 if(!animate)return;
 if(e.type==='goal'){
  $('momentTitle').textContent='GOOOL!';$('momentDesc').textContent=`${game.score[0]} – ${game.score[1]} · ${e.player||'Takım'}`;$('bigMoment').className='moment show goal';overlayTime=2.5;$('stadiumWrap').classList.add('goal-flash');
 }
 // Chances remain visible. Crowd reacts without covering the pitch with a shot banner.
 if(['shot','header','save','goal'].includes(e.type))crowd.react(e.type);
 if(['whistle','half','second-half','foul','penalty','advantage-recall','yellow','red','end'].includes(e.type))crowd.whistle();
}
function consume(animate=true){for(const e of game.drain())event(e,animate);}
function metrics(){
 if(attackView)attackView.render();
 const m=game,total=m.possession[0]+m.possession[1],pos=total?Math.round(m.possession[0]/total*100):50,c=matchClock(),halftime=c.phase==='halftime';
 $('matchClock').textContent=c.display;
 $('halfLabel').textContent=m.done?(m.finishReason==='minimum-players'?'TATİL EDİLDİ':'MAÇ SONU'):halftime?'DEVRE ARASI':`${c.period}. DEVRE${c.addedAnnounced?' · +'+clock(c.addedSeconds):''}`;
 $('progressBar').style.width=Math.min(100,Math.max(0,c.nominalElapsed/m.duration*100))+'%';
 $('realTime').textContent=halftime?'İkinci devreye '+Math.max(0,Math.ceil(c.halftimeRemaining))+' sn':m.done?'Maç tamamlandı':c.addedAnnounced?'Hakemin ek süresi · '+clock(Math.ceil(c.remaining))+' kaldı':clock(Math.ceil(c.remaining))+' kaldı';
 if($('halftimePanel')){$('halftimePanel').hidden=!halftime;$('halftimeCountdown').textContent=`İkinci devre ${Math.max(0,Math.ceil(c.halftimeRemaining))} sn sonra başlayacak.`;}
 $('scoreHome').textContent=m.score[0];$('scoreAway').textContent=m.score[1];$('statPoss').textContent=`%${pos} – %${100-pos}`;$('statShots').textContent=m.shots.join(' – ');$('statTarget').textContent=m.onTarget.join(' – ');$('statCards').textContent=`🟨 ${m.cards.join(' – ')} · 🟥 ${m.reds.join(' – ')}`;$('statFouls').textContent=m.fouls.join(' – ');
 if($('statPasses'))$('statPasses').textContent=`${m.completed[0]}/${m.passes[0]} – ${m.completed[1]}/${m.passes[1]}`;
 if($('statXg'))$('statXg').textContent=m.xg.map(n=>n.toFixed(2)).join(' – ');
 const r=m.restart||m.kick?.restartContext,labels={'kickoff':'SANTRA','throw':'TAÇ','corner':'KORNER','goal-kick':'AUT','free-kick':'SERBEST VURUŞ',penalty:'PENALTI'};
 $('liveType').textContent=m.pendingManagerKick?(visibleKick?'VURUŞ SEÇİMİ':'RAKİP VURUŞ SEÇİYOR'):m.done?(m.finishReason==='minimum-players'?'TATİL EDİLDİ':'TAMAMLANDI'):halftime?'DEVRE ARASI':m.goalPause?'GOL!':paused?'DURAKLATILDI':r?labels[r.kind]||'DURAN TOP':m.referee?.pendingAdvantage?'AVANTAJ':m.flight?.kind==='shot'?'GOL POZİSYONU':'CANLI';
 const phaseNames={build:'Geriden oyun kurma',progress:'Pas bağlantılarıyla ilerleme',final:'Son bölge hücumu',counter:'Hızlı hücum',counterpress:'Kaybın ardından baskı',defend:'Savunma yerleşimi',press:'Baskı ve kademe'};if($('teamPhase'))$('teamPhase').textContent=m.done?'Maç tamamlandı':halftime?'Devre arası':m.goalPause?'Gol sonrası hazırlık':r?'Duran top yerleşimi':phaseNames[m.tacticalPhase[liveSide]]||'Takım yerleşiyor';
 if($('playState'))$('playState').textContent=halftime?'Maç saati durdu · İkinci devrede kaleler değişecek':m.goalPause?'Gol kutlaması · Santra hazırlanıyor':r?`${r.team===0?(cfg.homeName||'Takımın'):(cfg.awayName||'Rakip')} · ${labels[r.kind]||'Duran top'}`:m.referee?.pendingAdvantage?'Hakem avantajı izliyor · Oyun sürüyor':m.owner?`${m.owner.name} · ${m.owner.holdingBall?'Topu tuttu':m.owner.receiveClock>0?(m.owner.receiveMode==='one-touch'?'Tek pas hazırlığı':m.owner.receiveMode==='open'?'Boşluğa ilk kontrol':'İlk kontrol'):'Topla ilerliyor'}`:m.flight?.kind==='shot'?'Top kaleye gidiyor':m.flight?.kind==='cross'?'Ceza sahasına orta':m.flight?.kind==='through'?'Savunma arkasına pas':'Top oyunda · Takımlar yerleşiyor';
 let left=Number($('momentum').dataset.left||50),target=m.ball.x*(typeof m.direction==='function'?m.direction(0):1)>0?60:40;left+=(target-left)*.12;$('momentum').dataset.left=left;$('momentum').style.setProperty('--homeWidth',left+'%');
 if(!$('subPanel').hidden)renderSubs();
 if(!$('subPanel').hidden)renderSubs();
 if(m.done&&!shownFinish){shownFinish=true;$('finishScreen').hidden=false;$('finishScore').textContent=m.score.join(' – ');document.querySelector('#finishScreen .result-top').textContent=m.finishReason==='minimum-players'?'MAÇ TATİL EDİLDİ':'MAÇ SONA ERDİ';$('finishText').textContent=(m.finishReason==='minimum-players'?'Asgari oyuncu sayısının altına düşüldü. ':'')+`${m.shots.join('–')} şut · ${m.completed.join('–')} başarılı pas · ${m.fouls.join('–')} faul. `+(live?'Sonuç lig tablosuna işlendi.':'Yerel gösterim maçıdır; günlük lig sonucunu değiştirmez.');}
}
function tick(dt){
 if(live||paused||game.done||game.pendingManagerKick)return;accumulator+=Math.min(.25,Math.max(0,dt))*speed;
 // Never execute an unbounded backlog on the render thread. Under severe
 // load the match slows gracefully instead of freezing the whole browser.
 const budget=speed>=8?14:speed>=4?10:6;
 let steps=0;
 while(accumulator+1e-10>=1/60&&!game.done&&steps<budget&&!game.pendingManagerKick){
  steps++;accumulator-=1/60;attackObserver.step();
  for(const p of game.players){p.selected=p===game.owner;if(p.active)Rig.update(p,1/60);}
  let releaseFrame=false;
  if(localContacts){
   localContacts.observe(game);
   const observed=scene.matchPilot?.observe({
    time:game.time,players:game.players,ball:game.ball,flight:game.flight,
    releaseSerial:game.releaseSerial,contacts:localContacts.recent()
   },1/60);
   releaseFrame=observed?.releaseCue?.time===game.time;
  }
  if(overlayTime>0){
   overlayTime-=1/60;
   if(overlayTime<=0){$('bigMoment').classList.remove('show');$('stadiumWrap').classList.remove('goal-flash');}
  }
  // Keep any remaining fixed steps for the next draw so a busy frame does
  // not consume both the pilot's strike and the start of its follow-through.
  if(releaseFrame)break;
 }
 if(steps===budget&&accumulator>=1/60){accumulator=Math.min(accumulator,2/60);simOverloadFrames++;}
 consume();const metric=Math.floor(game.time*5+1e-7),wall=performance.now();
 if(game.pendingManagerKick){syncKickControls();metrics();}
 else if(game.done||(metric!==lastMetric&&(speed<4||wall-lastMetricWall>=120))){
  metrics();lastMetric=metric;lastMetricWall=wall;
 }
}
function renderSubs(){
 const oldOut=$('subOut').value,oldIn=$('subIn').value,state=substitutionState(),pool=typeof game.team==='function'?game.team(0):game.field(0);
 $('subOut').innerHTML=pool.filter(p=>!p.referee&&p.active).map(p=>`<option value="${p.index}">${escapeHtml(p.name)} (${p.skill})${p.role==='GK'?' · Kaleci':''}</option>`).join('');
 $('subIn').innerHTML=game.bench().map(p=>`<option value="${p.id}">${escapeHtml(p.name)} (${p.rating})${p.pos==='GK'?' · Kaleci':''}</option>`).join('');
 if([...$('subOut').options].some(o=>o.value===oldOut))$('subOut').value=oldOut;if([...$('subIn').options].some(o=>o.value===oldIn))$('subIn').value=oldIn;
 $('saveSubs').disabled=!state.ok||!game.bench().length;
 if($('subRules'))$('subRules').textContent=`Bu müsabakada en fazla ${game.rules?.maxSubstitutions??5} oyuncu, ${game.rules?.substitutionWindows??3} değişiklik penceresinde değiştirilebilir. Devre arası değişiklikleri pencere kullanmaz.`;
 $('subsLeft').textContent=game.bench().length?`Kalan oyuncu: ${state.remaining} · Kalan pencere: ${state.windowsRemaining}${state.ok?'':` · ${state.reason||'Değişiklik için oyun durmalı.'}`}`:'Kadro ekranından maç başlatırsan yedekleri kullanabilirsin.';
}
// Original synthesized stadium bed. Audio only starts with an explicit button press.
const crowd={ctx:null,gain:null,enabled:false,ready(){
 if(this.ctx)return;const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return;
 this.ctx=new Audio();const c=this.ctx,b=c.createBuffer(1,c.sampleRate*3,c.sampleRate),data=b.getChannelData(0);let seed=1657;for(let i=0;i<data.length;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;data[i]=(seed/4294967296*2-1)*.35;}
 const src=c.createBufferSource();src.buffer=b;src.loop=true;const filter=c.createBiquadFilter();filter.type='lowpass';filter.frequency.value=950;this.gain=c.createGain();this.gain.gain.value=0;src.connect(filter);filter.connect(this.gain);this.gain.connect(c.destination);src.start();
},toggle(){this.ready();if(!this.ctx)return false;this.enabled=!this.enabled;this.ctx.resume();this.gain.gain.setTargetAtTime(this.enabled?.12:0,this.ctx.currentTime,.2);return this.enabled;},react(type){if(!this.enabled)return;const t=this.ctx.currentTime,g=this.gain.gain;g.cancelScheduledValues(t);g.setTargetAtTime(type==='goal'?.5:type==='save'?.3:.23,t,.12);g.setTargetAtTime(.12,t+(type==='goal'?2.7:1.0),.7);},whistle(){if(!this.enabled)return;const c=this.ctx,o=c.createOscillator(),g=c.createGain(),t=c.currentTime;o.frequency.value=2350;o.connect(g);g.connect(c.destination);g.gain.setValueAtTime(.018,t);g.gain.exponentialRampToValueAtTime(.0001,t+.16);o.start(t);o.stop(t+.18);}
};
window.addEventListener('DOMContentLoaded',()=>{
 if(pilotRequested){
  if(scene.gl){
   import('./match-clip-pilot.mjs')
    .then(()=>{scene.matchPilot=window.TribunLiveClipPilot.create({playerId:pilotPlayer});})
    .catch(error=>{pilotError=String(error.message||error);});
  }else pilotError='WebGL kullanılamıyor.';
 }
 kickPanel=new window.TribunManagerKickPanel($('managerKickPanel'),{
  onChange(opportunity,input,stage){
   if(opportunity.id!==visibleKick?.id)return;
   kickAim.show(visibleKick,input,stage);
   if(kickStage!==stage){
    kickStage=stage;
    (stage===1?$('stadiumWrap'):$('managerKickPanel')).scrollIntoView?.({block:'start'});
   }
  },
  onStrike:(opportunity,input)=>finishKick(opportunity.id,input),
  onAuto:opportunity=>finishKick(opportunity.id)
 });
 kickAim=new window.TribunManagerKickAim($('managerKickAim'),scene,(direction,power)=>kickPanel.setAim(direction,power));
 if(!scene.gl){const a=document.querySelector?.('.webgl');if(a)a.textContent='2D YEDEK';$('rigButton').disabled=true;}
 $('playButton').onclick=()=>{paused=!paused;label('playButton',paused?'Devam et':'Duraklat',paused?'play':'pause');metrics();};$('restartButton').onclick=init;$('againButton').onclick=init;
 $('camButton').onclick=()=>{scene.camera=scene.camera==='tv'?'close':scene.camera==='close'?'tactical':'tv';label('camButton',scene.camera==='tv'?'Kamera: TV':scene.camera==='close'?'Kamera: Yakın':'Kamera: Taktik','target');};
 $('rigButton').onclick=()=>{scene.debugRig=!scene.debugRig;label('rigButton',scene.debugRig?'İskelet: Açık':'İskelet: Kapalı','studio');};
 $('qualityButton').onclick=()=>{
  const modes=['balanced','performance','quality'],index=modes.indexOf(scene.performance.mode);
  scene.setPerformanceMode(modes[(index+1)%modes.length]);updateQualityLabel();
 };
 $('speedButton').onclick=()=>{const levels=[1,1.5,.75,4,8,16];speed=levels[(levels.indexOf(speed)+1)%levels.length];label('speedButton',speed+'× Hız');};
 if($('soundButton'))$('soundButton').onclick=()=>{label('soundButton',crowd.toggle()?'Tribün sesi: Açık':'Tribün sesi: Kapalı','sound');};
 $('subButton').onclick=()=>{renderSubs();$('subPanel').hidden=!$('subPanel').hidden;};$('closeSubs').onclick=()=>{$('subPanel').hidden=true;};
 if($('resumeHalf'))$('resumeHalf').onclick=()=>{if(typeof game.resumeHalf==='function')game.resumeHalf();consume();metrics();renderSubs();};
 if($('halftimeSubs'))$('halftimeSubs').onclick=()=>{renderSubs();$('subPanel').hidden=false;};
 $('saveSubs').onclick=()=>{const result=game.substitute(Number($('subOut').value),Number($('subIn').value));if(result.ok){$('subPanel').hidden=true;consume();renderSubs();}else alert(result.error);};
 let lastGraphicsLabel=0;
 function updateQualityLabel(){const p=scene.performanceMode(),name={balanced:'Dengeli',performance:'Performans',quality:'Kalite'}[p.mode];
  label('qualityButton','Grafik: '+name+' · '+Math.round(p.fps)+' FPS');
 }
 updateQualityLabel();
 function animate(){let last=performance.now(),lastPauseDraw=0;
  function frame(now){
   const started=performance.now();
   const dt=Math.max(0,Math.min(.25,(now-last)/1000));last=now;
   if(!game.pendingManagerKick)scene.observeFrame(dt,paused);
   const simStart=performance.now();
   if(!live)tick(dt);
   const physicsMs=performance.now()-simStart;
   if(ownKick()?.id!==visibleKick?.id)syncKickControls();
   updateKickCamera();
   // A paused pitch does not need full-rate GPU submissions.
   const stopped=paused||!!game.pendingManagerKick||!!live&&game.done;
   if(live){
    game.sample(now,stopped?0:dt);
    consume();
    scene.matchPilot?.observe(game.presentation??game,stopped?0:dt);
    if(overlayTime>0&&(overlayTime-=dt)<=0){$('bigMoment').classList.remove('show');$('stadiumWrap').classList.remove('goal-flash');}
   }
   let drawMs=0;
   if(!stopped||now-lastPauseDraw>=120){
    const renderStart=performance.now();
    const b=game.visualBall??game.ball;scene.render(game.players,b,[b.x+b.vx*.25,b.z+b.vz*.25],{},stopped?0:dt);
    kickAim.draw();lastPauseDraw=now;drawMs=performance.now()-renderStart;
   }
   lastFrameCost={physicsMs,drawSubmitMs:drawMs,mainThreadMs:performance.now()-started,
    gameSeconds:game.time,simOverloadFrames,activePlayers:game.players?.filter(p=>p.active&&!p.referee).length||0};
   if(now-lastGraphicsLabel>=1000){updateQualityLabel();lastGraphicsLabel=now;}
   requestAnimationFrame(frame);
  }requestAnimationFrame(frame);
 }
 function start(){init();animate();}
 if(liveRound!==null){
  for(const id of ['playButton','speedButton','subButton','restartButton','againButton','resumeHalf','attackAnalysis']){
   $(id).hidden=true;$(id).disabled=true;
  }
  document.querySelector('.analysis-link').hidden=true;
  document.querySelector('.stage-head>span:nth-child(2)').textContent='TRİBÜN ARENA / GÜNLÜK LİG';
  const exit=document.querySelector('#finishScreen .dialog-actions a');
  exit.href='league.html';exit.textContent='Lige dön';
  $('sessionTitle').textContent='GÜNLÜK LİG · CANLI MAÇ';
  liveNotice('Canlı maça bağlanılıyor…');
  live=new window.TribunLiveMatchClient(liveRound,{
   onState(update){
    const first=!game;
    if(first){
     liveSide=update.side;
     Object.assign(cfg,{homeName:update.homeName,awayName:update.awayName,formation:update.homeFormation,awayFormation:update.awayFormation});
     game=new window.TribunLiveMatchView();
    }
    game.ingest(update.state,performance.now());
    if(first){scene.resetAnimation();resetPresentation();animate();}
    else consume();
    syncKickControls();metrics();updateLiveNotice(update);
   },
   onError(error){liveNotice(error.message);}
  });
  live.start();
  return;
 }
 if(!window.TribunMatchConfig.prepared(cfg)){
  const controls=[...document.querySelectorAll('.match-controls button,#subButton,#saveSubs,#againButton,#restartButton,#playButton,#speedButton')];controls.forEach(b=>b.disabled=true);
  $('sessionTitle').textContent='GÜNCEL KADRO ALINIYOR…';
  window.TribunMatchConfig.prepare(cfg).then(value=>{Object.assign(cfg,value);controls.forEach(b=>b.disabled=false);if(!scene.gl)$('rigButton').disabled=true;start();}).catch(()=>{$('sessionTitle').textContent='KADRO BAĞLANTISI KURULAMADI · SAYFAYI YENİLE';});
 }else start();
});
window.TRIBUN_MATCH_TEST={attackReport:()=>attackObserver.report(),attackSummary:()=>attackObserver.summary(),getState:()=>({...game,elapsed:game.time,paused,speed,players:game.players,phase:game.phase,kickTask:game.kick}),animationStats:()=>scene.animationStats(),pilotStats:()=>scene.matchPilot?.info()||(pilotError?{status:'fallback',reason:pilotError}:{status:pilotRequested?'loading':'not-loaded'}),ballSeams:()=>scene.ballVisual?.orientation()||null,frameCost:()=>lastFrameCost,performanceStats:()=>({...scene.performanceMode(),simOverloadFrames}),setGraphicsMode:mode=>scene.setPerformanceMode(mode),setAnimationBlending:enabled=>scene.matchAnimation?.setEnabled(enabled),
 renderProbe:()=>{const b=game.ball,start=performance.now();scene.render(game.players,b,[b.x+b.vx*.25,b.z+b.vz*.25],{},0);if(scene.gl)scene.gl.finish();return {cpuGpuMs:performance.now()-start,active:game.players.filter(p=>p.active&&!p.referee).length,bridge:scene.animationStats(),webgl:!!scene.gl};},
 advance:(n=1)=>{for(let i=0;i<Math.round(n*60);i++)tick(1/60);},restart:init,frame:tick,substitute:(a,b)=>game.substitute(a,b),benchPlayers:()=>game.bench()};
})();
