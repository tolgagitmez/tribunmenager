'use strict';
// CI-only browser consumer for the private native fragmented MP4 HLS relay.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {setTimeout:delay}=require('node:timers/promises');

async function viewer(browser,url,disconnect,fullDuration=0){
 const context=await browser.newContext();
 try{
  const page=await context.newPage();
  if(disconnect){
   await page.exposeFunction('interruptHlsProbeConnection',async()=>{
    await context.setOffline(true);
    try{await delay(1100);}finally{await context.setOffline(false);}
   });
  }
  await page.goto(url+'/viewer',{timeout:5000});
  return await page.evaluate(async ({disconnect,fullDuration})=>{
   const video=document.querySelector('video'),start=performance.now();
   const elapsed=()=>performance.now()-start,round=n=>Math.round(n*100)/100;
   let transportFailures=0,resumedAfterFailure=0,offline=false,lastTransportError=null;
   let interruption=null,interruptionError=null,interruptionCompleted=false,interruptionFailures=0;
   async function fetchMedia(path,read){
    const before=performance.now();
    try{
     const response=await fetch('/'+path,{cache:'no-store',signal:AbortSignal.timeout(3000)});
     if(!response.ok)throw Error('media HTTP '+response.status+' '+path);
     const data=await read(response);
     if(offline){offline=false;resumedAfterFailure++;}
     const publicationAge=response.headers.get('X-Publication-Age-Ms');
     return {data,requestMs:round(performance.now()-before),publicationAgeMs:publicationAge===null?null:Number(publicationAge)};
    }catch(error){
     transportFailures++;offline=true;lastTransportError=String(error);
     if(interruption&&!interruptionCompleted)interruptionFailures++;
     return null;
    }
   }
   const bytes=response=>response.arrayBuffer(),manifest=response=>response.text();
   const initial=await fetchMedia('init.mp4',bytes);
   if(!initial)throw Error('Unable to fetch initialization segment: '+lastTransportError);
   const init=new Uint8Array(initial.data);
   // AVCDecoderConfigurationRecord carries the exact profile/compat/level.
   let codec=null;
   for(let i=4;i<init.length-8;i++){
    if(init[i]===97&&init[i+1]===118&&init[i+2]===99&&init[i+3]===67&&init[i+4]===1){
     codec='avc1.'+Array.from(init.slice(i+5,i+8),x=>x.toString(16).padStart(2,'0')).join('');
     break;
    }
   }
   if(!codec)throw Error('No AVC configuration in init');
   const mime='video/mp4; codecs="'+codec+', mp4a.40.2"';
   if(!MediaSource.isTypeSupported(mime))throw Error('MSE codecs unavailable: '+mime);
   const media=new MediaSource(),object=URL.createObjectURL(media);
   const opened=new Promise(resolve=>media.addEventListener('sourceopen',resolve,{once:true}));
   video.src=object;
   video.muted=false;
   const deadline=performance.now()+(fullDuration===-1?480000:fullDuration?(fullDuration+60)*1000:25000);
   const watchdog=new Promise((_,reject)=>setTimeout(()=>reject(Error('Timed out waiting for MediaSource')),6000));
   await Promise.race([opened,watchdog]);
   const buffer=media.addSourceBuffer(mime);
   async function append(data){
    await new Promise((resolve,reject)=>{
     const clean=()=>{
      buffer.removeEventListener('updateend',ok);
      buffer.removeEventListener('error',fail);
      clearTimeout(timeout);
     };
     const ok=()=>{clean();resolve();};
     const fail=()=>{clean();reject(Error('SourceBuffer decode error'));};
     const timeout=setTimeout(()=>{clean();reject(Error('SourceBuffer append timed out'));},5000);
     buffer.addEventListener('updateend',ok,{once:true});
     buffer.addEventListener('error',fail,{once:true});
     try{buffer.appendBuffer(data);}catch(error){clean();reject(error);}
    });
   }
   const audio=new AudioContext();
   const analyser=audio.createAnalyser(),sink=audio.createGain();
   // Keep the media element unmuted so the analyser gets decoded samples.
   // A zero-gain output avoids requiring a host sound device or speakers.
   sink.gain.value=0;
   audio.createMediaElementSource(video).connect(analyser).connect(sink).connect(audio.destination);
   const pcm=new Float32Array(analyser.fftSize);
   let nonSilentAudioSamples=0,firstAudioSignalMs=null,peakAudioRms=0;
   const audibleMinutes=Array(5).fill(0);
   const audioTimer=setInterval(()=>{
    if(video.paused)return;
    analyser.getFloatTimeDomainData(pcm);
    const rms=Math.sqrt(pcm.reduce((sum,sample)=>sum+sample*sample,0)/pcm.length);
    peakAudioRms=Math.max(peakAudioRms,rms);
    if(rms>=0.0001){
     nonSilentAudioSamples++;
     if(fullDuration)audibleMinutes[Math.min(4,Math.max(0,Math.floor(video.currentTime/60)))]++;
     firstAudioSignalMs??=elapsed();
    }
   },80);
   const canvas=document.createElement('canvas');
   canvas.width=32;canvas.height=24;
   const pixels=canvas.getContext('2d',{willReadFrequently:true}),signatures=new Set();
   let frames=0,firstFrameMs=null,lastFrameAt=null,maxFrameGapMs=0,firstMediaTime=null,mediaTime=null;
   let lastScreenSample=-Infinity,frameId=null,maxMediaGapMs=0;
   let stallAt=null,stallCount=0,stallMs=0;
   video.addEventListener('waiting',()=>{
    if(firstFrameMs!==null&&stallAt===null){stallAt=performance.now();stallCount++;}
   });
   video.addEventListener('playing',()=>{
    if(stallAt!==null){stallMs+=performance.now()-stallAt;stallAt=null;}
   });
   function frame(now,metadata){
    frameId=video.requestVideoFrameCallback(frame);
    if(video.paused||video.seeking)return;
    frames++;
    if(firstFrameMs===null){
     firstFrameMs=elapsed();firstMediaTime=metadata.mediaTime;
     if(disconnect)interruption=window.interruptHlsProbeConnection()
      .then(()=>{interruptionCompleted=true;})
      .catch(error=>{interruptionError=String(error);});
    }
    if(lastFrameAt!==null)maxFrameGapMs=Math.max(maxFrameGapMs,now-lastFrameAt);
    lastFrameAt=now;
    if(mediaTime!==null)maxMediaGapMs=Math.max(maxMediaGapMs,(metadata.mediaTime-mediaTime)*1000);
    mediaTime=metadata.mediaTime;
    if(mediaTime-lastScreenSample>=.5){
     pixels.drawImage(video,0,0,canvas.width,canvas.height);
     const data=pixels.getImageData(0,0,canvas.width,canvas.height).data;
     let signature=2166136261;
     for(let i=0;i<data.length;i++)signature=Math.imul(signature^data[i],16777619);
     signatures.add(signature);
     lastScreenSample=mediaTime;
    }
   }
   function readPlaylist(text){
    const lines=text.split(/\r?\n/),sequence=lines.find(x=>/^#EXT-X-MEDIA-SEQUENCE:\d+$/.test(x));
    const names=lines.filter(x=>/^segment-\d{6}\.m4s$/.test(x));
    if(!sequence||!lines.includes('#EXT-X-MAP:URI="init.mp4"')||!names.length)throw Error('Invalid fMP4 playlist');
    const first=Number(sequence.split(':')[1]);
    if(names.some((name,i)=>Number(name.slice(8,14))!==first+i))throw Error('Non-contiguous playlist');
    return names.map((name,i)=>({name,sequence:first+i}));
   }
   const fragments=[];
   let started=false,appendedDuringPlayback=0,appendedAfterReconnect=0,endedManifest=false;
   try{
    await append(init);
    frameId=video.requestVideoFrameCallback(frame);
    while(performance.now()<deadline){
     if(video.error)throw Error('video error '+video.error.code);
     const playlist=await fetchMedia('stream.m3u8',manifest);
     if(playlist){
      const entries=readPlaylist(playlist.data);
      if(fullDuration&&!fragments.length&&entries[0].sequence!==0)throw Error('Missed initial fragment');
      for(const fragment of entries){
       const previous=fragments.at(-1);
       if(previous&&fragment.sequence<=previous.sequence)continue;
       if(previous&&fragment.sequence!==previous.sequence+1)throw Error('Live playlist advanced past the last appended fragment');
       const received=await fetchMedia(fragment.name,bytes);
       if(!received)break;
       const hash=await crypto.subtle.digest('SHA-256',received.data);
       await append(received.data);
       if(firstFrameMs!==null&&!video.paused)appendedDuringPlayback++;
       if(interruptionCompleted&&interruptionFailures>0&&resumedAfterFailure>0)appendedAfterReconnect++;
       fragments.push({...fragment,bytes:received.data.byteLength,requestMs:received.requestMs,
        publicationAgeMs:received.publicationAgeMs,sha256:Array.from(new Uint8Array(hash),x=>x.toString(16).padStart(2,'0')).join('')});
      }
      if(fullDuration&&playlist.data.split(/\r?\n/).includes('#EXT-X-ENDLIST')&&fragments.at(-1)?.sequence===entries.at(-1).sequence&&!endedManifest){
       media.endOfStream();endedManifest=true;
      }
     }
     if(!started&&buffer.buffered.length&&buffer.buffered.end(0)-buffer.buffered.start(0)>=(fullDuration?4:2)){
      video.currentTime=buffer.buffered.start(0)+.05;
      await audio.resume();
      await video.play();
      started=true;
     }
     const playbackSeconds=mediaTime-firstMediaTime;
     const complete=fullDuration ? endedManifest&&video.ended&&playbackSeconds>=Math.max(4,fullDuration-.3) : playbackSeconds>=4.05;
     if(started&&frames>=30&&signatures.size>=3&&complete&&nonSilentAudioSamples>=3&&appendedDuringPlayback>0&&(!disconnect||appendedAfterReconnect>0)){
      if(interruptionError)throw Error('Connection interruption failed: '+interruptionError);
      const quality=video.getVideoPlaybackQuality();
      return {presentedCallbacks:frames,distinctScreenSamples:signatures.size,totalVideoFrames:quality.totalVideoFrames,
       droppedVideoFrames:quality.droppedVideoFrames,firstFrameMs:round(firstFrameMs),playbackSeconds:round(playbackSeconds),
       width:video.videoWidth,height:video.videoHeight,codec:mime,fragments,appendedDuringPlayback,
       audioAnalysisSampleRate:audio.sampleRate,nonSilentAudioSamples,peakAudioRms,firstAudioSignalMs:round(firstAudioSignalMs),
       transportFailures,resumedAfterFailure,interruptionFailures,appendedAfterReconnect,simulatedDisconnect:disconnect,
       firstMediaTime, lastMediaTime:mediaTime, mediaDuration:video.duration, endedManifest, ended:video.ended,audibleMinutes,maxMediaGapMs:round(maxMediaGapMs),
       maxFrameGapMs:round(maxFrameGapMs),stallCount,
       stallMs:round(stallMs+(stallAt===null?0:performance.now()-stallAt)),
       appendedMediaAheadMs:buffer.buffered.length?round((buffer.buffered.end(buffer.buffered.length-1)-mediaTime)*1000):0};
     }
     await new Promise(resolve=>setTimeout(resolve,280));
    }
    throw Error('Browser playback did not meet the evidence threshold: '+JSON.stringify({frames,distinctScreenSamples:signatures.size,
     firstFrameMs,mediaTime,firstMediaTime,nonSilentAudioSamples,appendedDuringPlayback,appendedAfterReconnect,
     transportFailures,resumedAfterFailure,interruptionFailures,interruptionError,lastTransportError}));
   }finally{
    video.cancelVideoFrameCallback(frameId);
    clearInterval(audioTimer);
    video.pause();video.removeAttribute('src');video.load();URL.revokeObjectURL(object);
    await audio.close();
   }
  },{disconnect,fullDuration});
 }finally{await context.close();}
}

(async()=>{
 const url=new URL(process.argv[2]);
 const fullDuration=process.argv[3]==='--five-minute'?300:process.argv[3]==='--native-full'?-1:0;
 assert(process.argv.length===(fullDuration?4:3),'Unexpected arguments');
 assert.equal(url.protocol,'http:');
 assert.equal(url.hostname,'127.0.0.1');
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||undefined,
  args:['--autoplay-policy=no-user-gesture-required']});
 try{
  const results=await Promise.all([viewer(browser,url.origin,false,fullDuration),viewer(browser,url.origin,!fullDuration,fullDuration)]);
  for(const result of results){
   assert(result.presentedCallbacks>=30&&result.distinctScreenSamples>=3&&result.width===(fullDuration?1280:640)&&result.height===(fullDuration?720:512));
   assert(result.nonSilentAudioSamples>=3&&result.peakAudioRms>=0.0001);
   assert(result.fragments.every(f=>Number.isFinite(f.publicationAgeMs)));
  }
  if(fullDuration){
   for(const result of results){
    assert(result.ended&&result.endedManifest&&result.firstMediaTime<=.15,'Missing stream boundaries');
    if(fullDuration===300){
     assert(result.playbackSeconds>=299.7&&result.lastMediaTime>=299.7,'Incomplete playback duration');
     assert(result.fragments.length===150&&result.fragments[0].sequence===0&&result.fragments.at(-1).sequence===149,'Missing full-stream fragments');
     assert(result.audibleMinutes.every(n=>n>=100),'Missing decoded sound during a minute');
    }else{
     assert(Number.isFinite(result.mediaDuration)&&result.mediaDuration-result.lastMediaTime<=.25,'Native final frame missing');
     assert(result.fragments[0].sequence===0&&result.fragments.at(-1).sequence===result.fragments.length-1,'Missing native fragment');
    }
    assert(result.maxFrameGapMs<=500&&result.stallCount===0&&result.transportFailures===0,JSON.stringify(result));
    assert(result.maxMediaGapMs<=200,'Missing media-time frames');
    assert(result.presentedCallbacks/result.playbackSeconds>=28.5,'Insufficient delivered video callbacks');
    assert(result.droppedVideoFrames/Math.max(1,result.totalVideoFrames)<=.01,'Too many dropped video frames');
   }
  }else assert(results[1].interruptionFailures>0&&results[1].resumedAfterFailure>0&&results[1].appendedAfterReconnect>0);
  const peer=new Map(results[1].fragments.map(f=>[f.name,f.sha256]));
  const shared=results[0].fragments.filter(f=>peer.has(f.name));
  assert(shared.length>=(fullDuration===300?150:3),'The viewers must receive common ordered fragments');
  if(fullDuration)assert(results.every(r=>r.fragments.length===shared.length),'Full viewers did not receive identical fragment counts');
  for(const fragment of shared)assert.equal(fragment.sha256,peer.get(fragment.name),fragment.name);
  console.log(JSON.stringify({browserPlaybackVerified:true,browserAudioSignalVerified:true,independentBrowserContexts:2,
   sharedFragments:shared.length,shortDisconnectRecoveryVerified:!fullDuration,fiveMinuteTransportVerified:fullDuration===300,nativeFullStreamPlaybackVerified:fullDuration===-1,results,physicalAudioOutputVerified:false,
   captureToScreenLatencyVerified:false,avSyncVerified:false,fullMatchVerified:false}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
