'use strict';
// CI-only browser consumer for the private fragmented MP4 HLS relay.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');

async function viewer(browser,url){
 const context=await browser.newContext();
 try{
  const page=await context.newPage();
  await page.goto(url+'/viewer');
  return await page.evaluate(async()=>{
   const video=document.querySelector('video');
   const start=performance.now();
   const fetchBytes=async path=>{
    const r=await fetch('/'+path,{cache:'no-store'});
    if(!r.ok)throw Error('media HTTP '+r.status);
    return new Uint8Array(await r.arrayBuffer());
   };
   const init=await fetchBytes('init.mp4');
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
   const media=new MediaSource();
   const object=URL.createObjectURL(media);
   const opened=new Promise(resolve=>media.addEventListener('sourceopen',resolve,{once:true}));
   video.src=object;video.muted=true;
   await opened;
   const buffer=media.addSourceBuffer(mime);
   function append(data){
    return new Promise((resolve,reject)=>{
     const clean=()=>{buffer.removeEventListener('updateend',ok);buffer.removeEventListener('error',fail);};
     const ok=()=>{clean();resolve();};
     const fail=()=>{clean();reject(Error('SourceBuffer decode error'));};
     buffer.addEventListener('updateend',ok,{once:true});
     buffer.addEventListener('error',fail,{once:true});
     buffer.appendBuffer(data);
    });
   }
   await append(init);
   const seen=new Set();
   let frames=0,firstFrameMs=null;
   function frame(){
    frames++;
    if(firstFrameMs===null)firstFrameMs=performance.now()-start;
    video.requestVideoFrameCallback(frame);
   }
   video.requestVideoFrameCallback(frame);
   let started=false;
   try{
    const deadline=performance.now()+18000;
    while(performance.now()<deadline){
     const response=await fetch('/stream.m3u8',{cache:'no-store'});
     if(!response.ok)throw Error('playlist HTTP '+response.status);
     const names=(await response.text()).split(/\r?\n/).filter(x=>/^segment-\d{6}\.m4s$/.test(x));
     for(const name of names){
      if(seen.has(name))continue;
      await append(await fetchBytes(name));seen.add(name);
     }
     if(!started&&buffer.buffered.length&&buffer.buffered.end(0)-buffer.buffered.start(0)>=2){
      video.currentTime=buffer.buffered.start(0)+.05;
      await video.play();started=true;
     }
     if(started&&frames>=15&&video.currentTime-buffer.buffered.start(0)>=1.0&&seen.size>=3){
      return {decodedFrames:frames,firstFrameMs:Math.round(firstFrameMs),segments:seen.size,
       playbackSeconds:video.currentTime-buffer.buffered.start(0),width:video.videoWidth,height:video.videoHeight,
       mutedForAutoplay:true,codec:mime};
     }
     if(video.error)throw Error('video error '+video.error.code);
     await new Promise(r=>setTimeout(r,350));
    }
    throw Error('Browser playback did not advance');
   }finally{video.pause();video.removeAttribute('src');video.load();URL.revokeObjectURL(object);}
  });
 }finally{await context.close();}
}

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});
 try{
  const results=await Promise.all([viewer(browser,process.argv[2]),viewer(browser,process.argv[2])]);
  for(const result of results){assert(result.decodedFrames>=15);assert(result.width>0&&result.height>0);}
  console.log(JSON.stringify({browserPlaybackVerified:true,independentBrowserContexts:2,results,
   physicalAudioOutputVerified:false,captureToScreenLatencyVerified:false}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
