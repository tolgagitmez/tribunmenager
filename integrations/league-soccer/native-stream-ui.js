'use strict';
(function(){
 const $=id=>document.getElementById(id),scene=new Stadium3D($('pitch')),view=window.TribunNativeStreamView.create(window.TribunHumanoidRig);
 scene.setPerformanceMode('balanced');$('mode').textContent=scene.gl?'WebGL 3D':'2D yedek görünüm';
 const advisor=window.TribunNativeAdvisor.create();
 let generation=0,timer=null,controller=null,active=false,current=null,last=0;
 for(let i=0;i<10;i++)$('round').add(new Option(String(i+1),String(i)));
 const round=new URLSearchParams(location.search).get('round');if(round!==null&&/^[0-9]$/.test(round))$('round').value=round;
 function stop(){active=false;generation++;clearTimeout(timer);controller?.abort();controller=null;}
 function start(){
  stop();view.reset();advisor.reset();scene.resetAnimation();current=null;$('adviceText').textContent='Maç verisi bekleniyor.';
  $('score').textContent='Bağlantı kuruluyor';$('clock').textContent='';$('stats').textContent='';
  let token;try{token=localStorage.getItem('tribun-league-token');}catch{}
  if(!token){$('status').textContent='Lig oturumu gerekli.';return;}
  active=true;const g=generation,selected=$('round').value;
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
    if(data.frame&&view.ingest(data,performance.now())){
     current=data;advisor.ingest(data);renderAdvice();
     const seconds=Math.ceil(data.remainingMs/1000);
     $('clock').textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')+' kaldı';
     $('score').textContent=(data.homeName||'Ev sahibi')+' '+data.frame.score.join(' – ')+' '+(data.awayName||'Deplasman')+' · '+Math.floor(data.frame.matchMs/60000)+'′';
     const s=data.frame.stats; $('stats').textContent=s?['Şut: '+s.shots.join(' – '),'İsabetli: '+s.onTarget.join(' – '),'Başarılı pas: '+s.completed.join(' – '),'Faul: '+s.fouls.join(' – ')].join('\n'):'';
     $('status').textContent=data.phase==='finished'?'Pilot yayın tamamlandı.':'Ortak sunucu yayını · resmî sonuç değildir.';
     if(Array.isArray(data.frame.participation)){
      const ys=[0,0],rs=[0,0];for(const p of data.frame.participation){ys[p.team]+=p.cardCode>=3?p.cardCode-3:p.cardCode;rs[p.team]+=Number(p.cardCode>=2);}
      $('stats').textContent+='\nSarı kart: '+ys.join(' – ')+'\nKırmızı kart: '+rs.join(' – ');
     }
     if(Array.isArray(data.frame.managerTactics)){
      for(const t of data.frame.managerTactics)if(t.revision>0)$('stats').textContent+='\n'+(t.team===0?'Ev sahibi':'Deplasman')+' · '+Math.floor(t.appliedMatchMs/60000)+'′ taktik komutu #'+t.revision+' · Baskı '+t.press+' / Kontra '+t.counter+' / Destek '+t.support+' / Genişlik '+t.width+(Number.isInteger(t.tempo)?' / Tempo '+t.tempo:'')+(t.formation?' / Diziliş '+({433:'4-3-3',442:'4-4-2',4231:'4-2-3-1'}[t.formation]||t.formation):'');
     }
     if(data.phase==='finished'){stop();return;}
    }else if(!data.frame){
     delay=1000;
     $('status').textContent=({queued:'Motor kuyruğunda',running:'League-Soccer maçı hesaplanıyor',failed:'Motor testi başarısız', 'not-enabled':'Bu fikstür için pilot etkin değil',unindexed:'Eski kayıt henüz yayın indeksine sahip değil'})[data.state]||'Yayın bekleniyor';
    }
   }catch(e){if(g===generation){$('status').textContent='Bağlantı kesildi; tekrar bağlanılıyor.';delay=1500;}}
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
 $('adviceTeam').onchange=renderAdvice;
 $('connect').onclick=start;
 $('camera').onclick=()=>{scene.camera=scene.camera==='tv'?'close':scene.camera==='close'?'tactical':'tv';$('camera').textContent='Kamera: '+({tv:'TV',close:'Yakın',tactical:'Taktik'}[scene.camera]);};
 $('quality').onchange=()=>scene.setPerformanceMode($('quality').value);
 function loop(now){
  const dt=last?Math.min(.1,(now-last)/1000):0;last=now;
  const frame=view.sample(now,current?.phase==='finished'?0:dt);
  scene.observeFrame(dt,!current||current.phase==='finished');
  if(frame)scene.render(frame.players,frame.ball,[frame.ball.x,frame.ball.z],{},dt);
  else scene.render([],{x:0,y:.11,z:0,vx:0,vy:0,vz:0},[0,0],{},dt);
  requestAnimationFrame(loop);
 }
 window.TRIBUN_NATIVE_STREAM_TEST={state:()=>current&&({sequence:current.sequence,score:current.frame.score,phase:current.phase}),webgl:()=>!!scene.gl};
 requestAnimationFrame(loop);start();
})();
