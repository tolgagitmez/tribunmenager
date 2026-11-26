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
 if(typeof module!=='undefined'&&module.exports){module.exports={playlist,codec};return;}
 const v=document.querySelector('#video'),button=document.querySelector('#start'),status=document.querySelector('#status'),sound=document.querySelector('#sound');
 let audioRequested=false;
 sound.addEventListener('click',()=>{if(audioRequested){v.muted=!v.muted;sound.textContent=v.muted?'Sesi aç':'Sesi kapat';}});
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));let running=false,objectUrl=null;
 async function get(name,binary=false){const r=await fetch(name,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return binary?r.arrayBuffer():r.text();}
 async function waitPlaylist(){
  for(let i=0;i<240;i++){
   try{const p=playlist(await get('live.m3u8'));if(p.files.length)return p;}catch(e){if(e.message!=='HTTP 404')throw e;}
   await sleep(500);
  }throw Error('Yayın zaman aşımına uğradı.');
 }
 function event(el,name){return new Promise((resolve,reject)=>{const ok=()=>{el.removeEventListener('error',bad);resolve();},bad=()=>{el.removeEventListener(name,ok);reject(Error('Video buffer error'));};el.addEventListener(name,ok,{once:true});el.addEventListener('error',bad,{once:true});});}
 async function play(){
  if(running)return;running=true;button.disabled=true;status.textContent='İlk video parçası bekleniyor…';
  try{
   let p=await waitPlaylist();
   const state=JSON.parse(await get('status.json'));audioRequested=state.audioRequested===true;sound.disabled=!audioRequested;
   v.muted=true;sound.textContent=audioRequested?'Sesi aç':'Ses bu pilotta kapalı';
   if(v.canPlayType('application/vnd.apple.mpegurl')){
    v.src='live.m3u8';await v.play();status.textContent='Native HLS oynatılıyor.';return;
   }
   if(!root.MediaSource)throw Error('Bu tarayıcı HLS veya MediaSource desteklemiyor.');
   const init=await get('init.mp4',true),mime=codec(init,audioRequested);
   if(!MediaSource.isTypeSupported(mime))throw Error('H.264 desteği bulunamadı.');
   const ms=new MediaSource();objectUrl=URL.createObjectURL(ms);
   const opened=event(ms,'sourceopen');v.src=objectUrl;await opened;
   const sb=ms.addSourceBuffer(mime);
   const append=async bytes=>{const finished=event(sb,'updateend');sb.appendBuffer(bytes);await finished;};
   await append(init);
   let next=Math.max(0,p.files.length-3),started=false,emptyPolls=0;
   while(true){
    const before=next;
    for(;next<p.files.length;next++){
     await append(await get(p.files[next],true));
     if(v.buffered.length){
      const start=v.buffered.start(0),end=v.buffered.end(v.buffered.length-1);
      if(!started){v.currentTime=start;await v.play();started=true;status.textContent='Orijinal motor görüntüsü oynatılıyor.';}
      else if(end-v.currentTime>8)v.currentTime=Math.max(start,end-2);
      if(v.currentTime-start>35){const finished=event(sb,'updateend');sb.remove(start,v.currentTime-15);await finished;}
     }
    }
    if(p.done){ms.endOfStream();status.textContent='Motor kaydı tamamlandı.';break;}
    emptyPolls=next===before?emptyPolls+1:0;
    if(emptyPolls>60)throw Error('Yeni video parçası alınamadı.');
    await sleep(500);p=playlist(await get('live.m3u8'));
   }
  }catch(e){status.textContent='Yayın açılamadı: '+e.message;running=false;button.disabled=false;sound.disabled=true;v.pause();v.removeAttribute('src');v.load();if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;}
 }
 // Current engine state is separate from buffered video time.
 const panel=document.querySelector('#manager'),send=document.querySelector('#sendTactics'),form=document.querySelector('#tacticsForm'),commandStatus=document.querySelector('#commandStatus');
 let controlState=null,submitting=false,pollGeneration=0,polling=false,managerSide=null,pendingRequest=null,rosterKey='';
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
    else if(state.commandState==='applied')commandStatus.textContent='Motor onayladı · komut '+state.appliedRevision;
    else if(state.commandState==='not-applied-at-end')commandStatus.textContent='Maç bitti; son komut uygulanmadı.';
    else commandStatus.textContent=state.canControl?'Motor hazır.':'Motor komut beklemiyor.';
   }
   if(state.appliedRevision>0&&pendingRequest&&state.appliedRevision>=pendingRequest.revision)pendingRequest=null;
   send.disabled=submitting||!state.canControl;
  }catch(e){if(generation===pollGeneration){controlState=null;renderRoster(null);send.disabled=true;commandStatus.textContent='Motor bağlantısı yok.';}}
 }
 async function startControl(){
  try{
   const state=JSON.parse(await get('status.json'));
   if(![0,1].includes(state.managerSide))return;
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
   const response=await fetch('tactics.json',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({round:0,requestId:pendingRequest.id,tactics})});
   const result=await response.json();
   if(!response.ok){if(response.status===400||response.status===403)pendingRequest=null;throw Error(result.error||'Komut reddedildi.');}
   if(result.team!==managerSide||result.state!=='submitted-not-applied')throw Error('Geçersiz motor cevabı.');
   pendingRequest.revision=result.revision;commandStatus.textContent='Gönderildi · motor onayı bekleniyor.';
  }catch(e){commandStatus.textContent=e.message;}
  finally{submitting=false;await controlPoll();}
 });
 startControl();
 button.addEventListener('click',play);
 root.addEventListener('pagehide',()=>{polling=false;pollGeneration++;if(objectUrl)URL.revokeObjectURL(objectUrl);});
})(typeof window!=='undefined'?window:globalThis);
