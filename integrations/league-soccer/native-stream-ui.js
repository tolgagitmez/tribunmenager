'use strict';
(function(){
 const $=id=>document.getElementById(id),scene=new Stadium3D($('pitch')),view=window.TribunNativeStreamView.create(window.TribunHumanoidRig);
 scene.setPerformanceMode('balanced');scene.setStadiumStyle($('stadiumStyle').value);scene.enhancedPlayerAppearance=$('playerAppearance').value==='enhanced';$('mode').textContent=scene.gl?'WebGL 3D':'2D yedek görünüm';
 const advisor=window.TribunNativeAdvisor.create(),tv=window.TribunBroadcastDesign.create(document);
 const fields=['press','counter','support','width','tempo'];
 const labels=['Baskı','Kontra','Pas desteği','Genişlik','Tempo'];
 for(let i=0;i<fields.length;i++){const label=document.createElement('label');label.textContent=labels[i]+' ';const input=document.createElement('input');input.type='number';input.min=0;input.max=100;input.required=true;input.value=50;input.id='tactic-'+fields[i];label.append(input);$('controlFields').append(label,document.createElement('br'));}
 const select=document.createElement('select');select.id='tactic-formation';for(const [v,l] of [[0,'Dizilişi koru'],[433,'4-3-3'],[442,'4-4-2'],[4231,'4-2-3-1']])select.add(new Option(l,String(v)));$('controlFields').append(select);
 let requestRound=null,requestToken=null,submitting=false;
 let generation=0,timer=null,controller=null,active=false,current=null;
 const renderBudget=window.TribunNativeStreamView.createRenderBudget();
 const performanceApi=window.TribunReplayPerformance;
 function graphics(){
  const enabled=$('advancedPresentation').checked,mode=$('quality').value;
  view.setPresentation(enabled);scene.setPerformanceMode(mode);
  scene.replayCameraSmooth=enabled;scene.replayCameraSnap=enabled;
  scene.replayRenderBudget=enabled?performanceApi.pixelBudget(mode,matchMedia('(max-width: 760px)').matches):null;
  scene.instancingEnabled=enabled&&mode==='performance';renderBudget.reset();
 }
 $('advancedPresentation').onchange=graphics;
 window.addEventListener('resize',graphics);
 for(let i=0;i<10;i++)$('round').add(new Option(String(i+1),String(i)));
 const round=new URLSearchParams(location.search).get('round');if(round!==null&&/^[0-9]$/.test(round))$('round').value=round;
 function stop(){$('sendTactics').disabled=true;active=false;generation++;clearTimeout(timer);controller?.abort();controller=null;}
 function start(){
  stop();renderBudget.reset();$('controlPanel').hidden=true;$('commandState').textContent='';view.reset();advisor.reset();scene.resetAnimation();current=null;$('adviceText').textContent='Maç verisi bekleniyor.';
  tv.update(null);$('score').textContent='Bağlantı kuruluyor';$('clock').textContent='';$('stats').textContent='';
  let token;try{token=localStorage.getItem('tribun-league-token');}catch{}
  if(!token){$('status').textContent='Lig oturumu gerekli.';return;}
  active=true;const g=generation,selected=$('round').value;requestRound=Number(selected);requestToken=token;
  async function poll(){
   if(!active||g!==generation)return;
   if(document.hidden){timer=setTimeout(poll,1000);return;}
   const request=new AbortController();controller=request;
   const timeout=setTimeout(()=>request.abort(),6500);
   let delay=180;
   try{
    const response=await fetch('/api/league/native-pilot/broadcast?round='+selected,{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:request.signal});
    const data=await response.json();
    if(g!==generation)return;
    if(!response.ok){if([401,403,404].includes(response.status)){stop();$('status').textContent=data.error||'Erişim yok.';return;}throw Error(data.error||'Sunucu bağlantısı yok.');}
    if(data.engine!=='league-soccer'||data.authoritative!==false)throw Error('Geçersiz pilot yanıtı.');
    if(data.frame&&!view.ingest(data,performance.now())){ $('sendTactics').disabled=true;throw Error('Eski veya çelişkili yayın karesi'); }
    $('controlPanel').hidden=data.source!=='interactive-native';
    $('sendTactics').disabled=!data.frame||data.source!=='interactive-native'||!data.canControl||submitting||data.phase==='finished'||data.finalizing===true||data.commandState==='waiting-for-engine'||view.isStale(performance.now());
    if(data.source==='interactive-native'){
     const states={'waiting-for-engine':' · Motor onayı bekleniyor','not-applied-at-end':' · Komut maç sonuna kadar uygulanmadı','applied':' · Motor uyguladı'};
     $('commandState').textContent='Gönderilen #'+(data.submittedRevision||0)+' · Motor onayı #'+(data.appliedRevision||0)+(states[data.commandState]||'')+(data.finalizing?' · Sonuç doğrulanıyor':'');
    }
    if(data.frame){
     const changed=!current||current.sequence!==data.sequence;
     current=data;if(changed){advisor.ingest(data);renderAdvice();}
     tv.update(data.frame,{home:data.homeName,away:data.awayName,phase:data.finalizing?'DOĞRULANIYOR':data.phase==='finished'?'MAÇ SONU':data.source==='interactive-native'?'PİLOT CANLI':'KAYIT YAYINI'});
     const seconds=Math.ceil(data.remainingMs/1000);
     $('clock').textContent=data.source==='interactive-native'?'Çalışan C++ motoru · '+Math.floor(data.frame.matchMs/60000)+'′'+(Number.isFinite(data.observedWallMs)?' · Gerçek süre '+Math.floor(data.observedWallMs/1000)+' sn':''):String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')+' kaldı';
     $('score').textContent=(data.homeName||'Ev sahibi')+' '+data.frame.score.join(' – ')+' '+(data.awayName||'Deplasman')+' · '+Math.floor(data.frame.matchMs/60000)+'′';
     if(changed){
     const s=data.frame.stats; $('stats').textContent=s?['Şut: '+s.shots.join(' – '),'İsabetli: '+s.onTarget.join(' – '),'Başarılı pas: '+s.completed.join(' – '),'Faul: '+s.fouls.join(' – ')].join('\n'):'';
     $('status').textContent=data.phase==='finished'?'Pilot yayın tamamlandı.':'Ortak sunucu yayını · resmî sonuç değildir.';
     if(Array.isArray(data.frame.participation)){
      const ys=[0,0],rs=[0,0];for(const p of data.frame.participation){ys[p.team]+=p.cardCode>=3?p.cardCode-3:p.cardCode;rs[p.team]+=Number(p.cardCode>=2);}
      $('stats').textContent+='\nSarı kart: '+ys.join(' – ')+'\nKırmızı kart: '+rs.join(' – ');
     }
     if(Array.isArray(data.frame.managerTactics)){
      for(const t of data.frame.managerTactics)if(t.revision>0)$('stats').textContent+='\n'+(t.team===0?'Ev sahibi':'Deplasman')+' · '+Math.floor(t.appliedMatchMs/60000)+'′ taktik komutu #'+t.revision+' · Baskı '+t.press+' / Kontra '+t.counter+' / Destek '+t.support+' / Genişlik '+t.width+(Number.isInteger(t.tempo)?' / Tempo '+t.tempo:'')+(t.formation?' / Diziliş '+({433:'4-3-3',442:'4-4-2',4231:'4-2-3-1'}[t.formation]||t.formation):'');
     }
     }
     if(data.phase==='finished'){stop();return;}
    }else if(!data.frame){
     delay=1000;
     $('status').textContent=({queued:'Motor kuyruğunda',running:'League-Soccer maçı hesaplanıyor',failed:'Motor testi başarısız', 'not-enabled':'Bu fikstür için pilot etkin değil',unindexed:'Eski kayıt henüz yayın indeksine sahip değil'})[data.state]||'Yayın bekleniyor';
    }
   }catch(e){if(g===generation){tv.phase('BAĞLANTI KESİLDİ');$('sendTactics').disabled=true;$('status').textContent='Bağlantı kesildi; tekrar bağlanılıyor.';delay=1500;}}
   finally{clearTimeout(timeout);if(controller===request)controller=null;if(active&&g===generation)timer=setTimeout(poll,delay);}
  }
  poll();
 }
 function renderAdvice(){
  const a=advisor.advice(Number($('adviceTeam').value));
  if(!a){$('adviceText').textContent='Aktif maç önerisi yok.';return;}
  const text=[a.minute+'′ · '+a.reasons.join(' ')];
  if(a.rivalShape)text.push('Rakibin gözlenen hat dağılımı: '+a.rivalShape);
  if(a.window)text.push('Son '+Math.round(a.window.minutes)+' maç dakikasında şut: '+a.window.shots.join(' – '));
  if(a.mode!=='balanced'){
   const v=a.values;text.push('Deneysel öneri: Baskı '+v.press+' / Kontra '+v.counter+' / Destek '+v.support+' / Genişlik '+v.width+' / Tempo '+v.tempo+(v.formation?' / Diziliş '+({433:'4-3-3',442:'4-4-2',4231:'4-2-3-1'}[v.formation]):''));
   if(!a.baselineKnown)text.push('Mevcut uygulanan ayarlar bilinmiyor; değerler öneridir.');
  }
  for(const c of a.changes)text.push('Değişiklik önerisi: '+c.out+' → '+c.in+' ('+c.reason+')');
  $('adviceText').textContent=text.join('\n');
 }
 $('controlForm').onsubmit=async e=>{
  e.preventDefault();if(!active||submitting||!current?.canControl||current.source!=='interactive-native'||current.phase!=='playing'||current.finalizing||view.isStale(performance.now())||$('sendTactics').disabled)return;
  const g=generation;submitting=true;$('sendTactics').disabled=true;
  const tactics=Object.fromEntries([...fields,'formation'].map(k=>[k,Number($('tactic-'+k).value)]));
  try{
   const requestId=Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join('');
   const r=await fetch('/api/league/native-pilot/tactics',{method:'POST',headers:{Authorization:'Bearer '+requestToken,'Content-Type':'application/json'},body:JSON.stringify({round:requestRound,requestId,tactics})});
   const data=await r.json();if(g!==generation)return;
   if(!r.ok)throw Error(data.error||'Komut reddedildi');
   if(!Number.isSafeInteger(data.revision)||data.revision<1||data.state!=='submitted-not-applied')throw Error('Komut yanıtı doğrulanamadı; motor durumunu bekle.');
   $('commandState').textContent='Komut #'+data.revision+' gönderildi, motor onayı bekleniyor.';
  }catch(err){if(g===generation)$('commandState').textContent=err.message;}
  finally{submitting=false;}
 };
 $('adviceTeam').onchange=renderAdvice;
 $('connect').onclick=start;
 $('camera').onclick=()=>{scene.camera=scene.camera==='tv'?'close':scene.camera==='close'?'tactical':'tv';$('camera').textContent='Kamera: '+({tv:'TV',close:'Yakın',tactical:'Taktik'}[scene.camera]);};
 $('quality').onchange=graphics;
 $('playerAppearance').onchange=()=>{scene.enhancedPlayerAppearance=$('playerAppearance').value==='enhanced';renderBudget.reset();};
 $('stadiumStyle').onchange=()=>{scene.setStadiumStyle($('stadiumStyle').value);renderBudget.reset();};
 document.addEventListener('visibilitychange',()=>renderBudget.reset());
 function loop(now){
  requestAnimationFrame(loop);
  const stale=view.isStale(now);
  if(stale){$('sendTactics').disabled=true;tv.phase('VERİ BEKLENİYOR');}
  const playing=!!current&&current.phase!=='finished'&&!current.finalizing&&!stale;
  const tick=renderBudget.next(now,{hidden:document.hidden,playing,mode:$('quality').value});
  if(!tick)return;
  const dt=tick.dt;
  const frame=view.sample(now,current?.phase==='finished'?0:dt);
  scene.observeFrame(tick.measuredDt,!playing);
  if(frame)scene.render(frame.players,frame.ball,[frame.ball.x,frame.ball.z],{},dt);
  else scene.render([],{x:0,y:.11,z:0,vx:0,vy:0,vz:0},[0,0],{},dt);
 }
 window.TRIBUN_NATIVE_STREAM_TEST={state:()=>current&&({sequence:current.sequence,score:current.frame.score,phase:current.phase}),webgl:()=>!!scene.gl,presentation:()=>({enabled:$('advancedPresentation').checked,graphics:scene.performanceMode(),stale:view.isStale(performance.now()),modelReady:!!scene.playerRenderer})};
 requestAnimationFrame(loop);start();
})();
