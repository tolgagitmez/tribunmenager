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
 function codec(bytes,audio=false){
  const a=new Uint8Array(bytes);
  for(let i=4;i+8<a.length;i++)if(a[i]===97&&a[i+1]===118&&a[i+2]===99&&a[i+3]===67&&a[i+4]===1){
   const size=new DataView(a.buffer,a.byteOffset+i-4,4).getUint32(0);
   if(size<15||i-4+size>a.length)continue;
   return 'video/mp4; codecs="avc1.'+[a[i+5],a[i+6],a[i+7]].map(n=>n.toString(16).padStart(2,'0')).join('')+(audio?',mp4a.40.2':'')+'"';
  }
  throw Error('AVC configuration missing');
 }
 // Never block segment ingestion on play() resolving. Initial buffering is explicit.
 function bufferDecision(ranges,time,started,done){
  if(!ranges.length)return {start:false,seek:null};
  const [start,end]=ranges[ranges.length-1];
  if(!started)return {start:end-start>=3.5||(done&&end>start),seek:start+.03};
  // At the live edge, wait for a new segment instead of jumping backwards.
  if(time>=end-.15)return {start:false,seek:null};
  const inside=ranges.some(([a,b])=>time>=a-.15&&time<b+.15);
  if(!inside){
   const next=ranges.find(([a,b])=>a>time&&b>a);
   if(!next)return {start:false,seek:null};
   return {start:false,seek:Math.max(next[0]+.03,Math.min(next[1]-.03,end-3))};
  }
  if(!done&&end-time>10)return {start:false,seek:Math.max(start+.03,end-3)};
  return {start:false,seek:null};
 }
 function retryStartup(error){return ['HTTP 404','HTTP 409','HTTP 503','Failed to fetch','The operation was aborted.'].includes(error?.message)||error?.name==='AbortError';}
 if(typeof module!=='undefined'&&module.exports){module.exports={playlist,codec,bufferDecision,retryStartup};return;}
 const leagueTransport=root.TRIBUN_LEAGUE_AV;
 const request=(name,options)=>leagueTransport?leagueTransport.request(name,options):fetch(name,options);
 const v=document.querySelector('#video'),button=document.querySelector('#start'),status=document.querySelector('#status'),sound=document.querySelector('#sound');
 let audioRequested=false;
 sound.addEventListener('click',()=>{if(audioRequested){v.muted=!v.muted;sound.textContent=v.muted?'Sesi aç':'Sesi kapat';}});
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));let running=false,objectUrl=null,playGeneration=0;
 const diagnostic={phase:'idle',mime:null,appended:0,playError:null,firstSegment:null,initialSeekSeconds:null,automaticSeeks:0,automaticSkippedSeconds:0,waitingEvents:0,stallEvents:0,playlistComplete:false,finalMediaEnd:null};
 function phase(name){diagnostic.phase=name;}
 const rangeArray=range=>Array.from({length:range.length},(_,i)=>[range.start(i),range.end(i)]);
 root.TRIBUN_VIDEO_DIAGNOSTIC=()=>{
  const quality=typeof v.getVideoPlaybackQuality==='function'?v.getVideoPlaybackQuality():null;
  return {...diagnostic,readyState:v.readyState,networkState:v.networkState,currentTime:v.currentTime,paused:v.paused,ended:v.ended,videoWidth:v.videoWidth,videoHeight:v.videoHeight,mediaError:v.error?.code||null,buffered:rangeArray(v.buffered),played:rangeArray(v.played),decodedFrames:quality?.totalVideoFrames??null,droppedFrames:quality?.droppedVideoFrames??null,message:status.textContent};
 };
 v.addEventListener('waiting',()=>{if(running)diagnostic.waitingEvents++;});
 v.addEventListener('stalled',()=>{if(running)diagnostic.stallEvents++;});
 v.addEventListener('ended',()=>{if(running){phase('ended');status.textContent='Maç yayını tamamlandı.';}});
 v.addEventListener('error',()=>{if(running&&v.error){phase('error');diagnostic.playError='Media decode error '+v.error.code;}});
 async function get(name,binary=false){
  const ac=new AbortController(),timer=setTimeout(()=>ac.abort(),8000);
  try{const r=await request(name,{cache:'no-store',signal:ac.signal});if(!r.ok)throw Error('HTTP '+r.status);return await (binary?r.arrayBuffer():r.text());}finally{clearTimeout(timer);}
 }
 async function waitPlaylist(){
  for(let i=0;i<240;i++){
   try{const p=playlist(await get('live.m3u8'));if(p.files.length)return p;}catch(e){if(leagueTransport?!retryStartup(e):e.message!=='HTTP 404')throw e;}
   await sleep(500);
  }throw Error('Yayın zaman aşımına uğradı.');
 }
 function event(el,name){return new Promise((resolve,reject)=>{
  const cleanup=()=>{clearTimeout(timer);el.removeEventListener(name,ok);el.removeEventListener('error',bad);el.removeEventListener('abort',bad);};
  const ok=()=>{cleanup();resolve();},bad=()=>{cleanup();reject(Error('Media event failed: '+name));};
  const timer=setTimeout(()=>{cleanup();reject(Error('Media event timeout: '+name));},10000);
  el.addEventListener(name,ok,{once:true});el.addEventListener('error',bad,{once:true});el.addEventListener('abort',bad,{once:true});
 });}
 async function play(){
  if(running)return;running=true;button.disabled=true;
  const generation=++playGeneration;Object.assign(diagnostic,{phase:'waiting-playlist',mime:null,appended:0,playError:null,firstSegment:null,initialSeekSeconds:null,automaticSeeks:0,automaticSkippedSeconds:0,waitingEvents:0,stallEvents:0,playlistComplete:false,finalMediaEnd:null});status.textContent='İlk video parçaları bekleniyor…';
  try{
   let p=await waitPlaylist();
   const state=JSON.parse(await get('status.json'));audioRequested=state.audioRequested===true;sound.disabled=!audioRequested;
   v.muted=true;sound.textContent=audioRequested?'Sesi aç':'Ses bu pilotta kapalı';
   const init=await get('init.mp4',true),mime=codec(init,audioRequested);diagnostic.mime=mime;
   const mse=!!root.MediaSource&&MediaSource.isTypeSupported(mime);
   if(!mse&&!leagueTransport&&v.canPlayType('application/vnd.apple.mpegurl')){
    phase('native-hls');v.src='live.m3u8';await v.play();status.textContent='Native HLS oynatılıyor.';return;
   }
   if(!mse)throw Error(leagueTransport?'Bu özel yayın için MSE destekli tarayıcı gerekli.':'Tarayıcı kodlayıcıyı desteklemiyor: '+mime);
   phase('opening-mse');const ms=new MediaSource();objectUrl=URL.createObjectURL(ms);
   const opened=event(ms,'sourceopen');v.src=objectUrl;await opened;
   const sb=ms.addSourceBuffer(mime);
   const append=async bytes=>{const finished=event(sb,'updateend');sb.appendBuffer(bytes);await finished;};
   await append(init);phase('buffering');
   let next=Math.max(0,p.files.length-3),started=false,emptyPolls=0,playError=null;
   diagnostic.firstSegment=next;
   const ranges=()=>Array.from({length:v.buffered.length},(_,i)=>[v.buffered.start(i),v.buffered.end(i)]);
   const begin=()=>{
    const decision=bufferDecision(ranges(),v.currentTime,started,p.done);
    if(!started&&decision.start){
     started=true;diagnostic.initialSeekSeconds=decision.seek;v.currentTime=decision.seek;phase('starting-playback');
     // Promise resolves asynchronously; continue feeding source buffer meanwhile.
     v.play().then(()=>{if(generation===playGeneration&&!diagnostic.playlistComplete){phase('playing');status.textContent='Orijinal motor görüntüsü oynatılıyor.';}}).catch(e=>{playError=e;diagnostic.playError=e.message;});
    }else if(started&&decision.seek!==null&&!v.seeking&&decision.seek>v.currentTime+.05){
     diagnostic.automaticSeeks++;diagnostic.automaticSkippedSeconds+=decision.seek-v.currentTime;v.currentTime=decision.seek;
    }
   };
   while(generation===playGeneration){
    if(playError)throw playError;
    if(v.error)throw Error('Media decode error '+v.error.code);
    const before=next;
    for(;next<p.files.length;next++){
     await append(await get(p.files[next],true));diagnostic.appended++;begin();
     if(started&&v.buffered.length&&v.currentTime-v.buffered.start(0)>35){const finished=event(sb,'updateend');sb.remove(v.buffered.start(0),v.currentTime-15);await finished;}
    }
    begin();
    if(p.done){
     if(!started)throw Error('Tamamlanan yayında oynatılabilir video yok.');
     diagnostic.playlistComplete=true;
     diagnostic.finalMediaEnd=v.buffered.length?v.buffered.end(v.buffered.length-1):null;
     if(ms.readyState==='open')ms.endOfStream();
     if(!v.ended){phase('draining');status.textContent='Son video parçaları oynatılıyor.';}
     break;
    }
    emptyPolls=next===before?emptyPolls+1:0;
    if(emptyPolls>60)throw Error('Yeni video parçası alınamadı.');
    await sleep(500);p=playlist(await get('live.m3u8'));
    if(p.files.length<next)throw Error('Playlist regressed');
   }
  }catch(e){phase('error');diagnostic.playError=e.message;status.textContent='Yayın açılamadı: '+e.message;running=false;button.disabled=false;sound.disabled=true;v.pause();v.removeAttribute('src');v.load();if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;}
 }
 // Current engine state is separate from buffered video time.
 const panel=document.querySelector('#manager'),send=document.querySelector('#sendTactics'),form=document.querySelector('#tacticsForm'),commandStatus=document.querySelector('#commandStatus');
 let controlState=null,submitting=false,pollGeneration=0,polling=false,managerSide=null,pendingRequest=null,rosterKey='',controlStopped=false;
 function renderRoster(roster){
  const key=JSON.stringify(roster);if(key===rosterKey)return;rosterKey=key;
  const rows=document.querySelector('#rosterRows'),plans=document.querySelector('#plannedChanges'),status=document.querySelector('#rosterStatus');
  rows.replaceChildren();plans.replaceChildren();
  if(!roster?.available){status.textContent='Doğrulanmış kadro verisi bekleniyor.';return;}
  status.textContent='Motor saati: '+Math.floor(roster.matchMs/60000)+'′ · '+roster.players.filter(p=>p.active).length+' aktif oyuncu';
  const percent=v=>Number.isFinite(v)?Math.round(v*100)+'%':'—';
  for(const p of roster.players){
   const row=document.createElement('tr');
   for(const val of [p.name,p.status==='active'?'Sahada':p.status==='dismissed'?'İhraç':p.status==='used'?'Çıktı':'Yedek',percent(p.fatigueFactor),percent(p.injuryLevel),p.red?'Kırmızı':p.yellow?'Sarı ×'+p.yellow:'—',Math.floor(p.nominalMs/60000)]){
    const cell=document.createElement('td');cell.textContent=String(val);cell.style.padding='5px 3px';row.append(cell);
   }
   rows.append(row);
  }
  for(const p of roster.changes){const li=document.createElement('li');li.textContent=p.outName+' → '+p.inName+' · '+(p.state==='observed'?'Sahada gözlendi':p.state==='not-observed'?'Henüz gözlenmedi':'Devre arası planı');plans.append(li);}
 }
 async function controlPoll(){
  const generation=++pollGeneration;
  try{
   const state=JSON.parse(await get('tactics.json'));
   if(generation!==pollGeneration)return;
   if(state.side!==managerSide)throw Error('Takım uyuşmuyor.');
   controlState=state;renderRoster(state.roster);
   if(!submitting){
    if(state.commandState==='waiting-for-engine')commandStatus.textContent='Komut '+state.submittedRevision+' · motor onayı bekleniyor.';
    else if(state.commandState==='applied')commandStatus.textContent='Motor onayladı · komut '+state.appliedRevision+(state.lastAcknowledgement?' · '+Math.floor(state.lastAcknowledgement.appliedMatchMs/60000)+'′':'');
    else if(state.commandState==='not-applied-at-end')commandStatus.textContent='Maç bitti; son komut uygulanmadı.';
    else commandStatus.textContent=state.canControl?'Motor hazır.':'Motor komut beklemiyor.';
   }
   if(state.appliedRevision>0&&pendingRequest&&state.appliedRevision>=pendingRequest.revision)pendingRequest=null;
   send.disabled=submitting||!state.canControl;
  }catch(e){if(generation===pollGeneration){controlState=null;renderRoster(null);send.disabled=true;commandStatus.textContent='Motor bağlantısı yok.';}}
 }
 async function startControl(){
  try{
   let state;
   const deadline=Date.now()+120000;
   while(!controlStopped){
    try{state=JSON.parse(await get('status.json'));break;}
    catch(e){if(!leagueTransport||!retryStartup(e)||Date.now()>=deadline)throw e;await sleep(500);}
   }
   if(controlStopped||!state||![0,1].includes(state.managerSide))return;
   managerSide=state.managerSide;panel.hidden=false;document.querySelector('#teamSide').textContent=managerSide===0?'Ev sahibi takım':'Deplasman takımı';
   if(polling)return;polling=true;
   while(polling){await controlPoll();await sleep(500);}
  }catch(e){send.disabled=true;}
 }
 form.addEventListener('submit',async e=>{
  e.preventDefault();if(submitting||!controlState?.canControl)return;
  const tactics=Object.fromEntries(['press','counter','support','width','tempo','formation'].map(k=>[k,Number(document.querySelector('#'+k).value)]));
  // Reuse identical request after a lost HTTP response; never assume acknowledgement.
  const key=JSON.stringify(tactics);
  if(!pendingRequest||pendingRequest.key!==key)pendingRequest={key,id:crypto.randomUUID(),revision:controlState.submittedRevision+1};
  submitting=true;send.disabled=true;commandStatus.textContent='Motora gönderiliyor…';
  try{
   const response=await request('tactics.json',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({round:leagueTransport?leagueTransport.round:0,requestId:pendingRequest.id,tactics})});
   const result=await response.json();
   if(!response.ok){if(response.status===400||response.status===403)pendingRequest=null;throw Error(result.error||'Komut reddedildi.');}
   if((!leagueTransport&&result.team!==managerSide)||result.state!=='submitted-not-applied')throw Error('Geçersiz motor cevabı.');
   pendingRequest.revision=result.revision;commandStatus.textContent='Gönderildi · motor onayı bekleniyor.';
  }catch(e){commandStatus.textContent=e.message;}
  finally{submitting=false;await controlPoll();}
 });
 startControl();
 button.addEventListener('click',play);
 root.addEventListener('pagehide',()=>{controlStopped=true;polling=false;pollGeneration++;playGeneration++;if(objectUrl)URL.revokeObjectURL(objectUrl);});
})(typeof window!=='undefined'?window:globalThis);
