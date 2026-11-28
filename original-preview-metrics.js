'use strict';
// Measures frames presented by the browser, not native render FPS or physics.
(function(root){
 // Store only bounded numeric observations, never the shared window pixels or title.
 function createReport(){
  let samples=[],dropped=0,excluded=0;
  function reset(){samples=[];dropped=excluded=0;}
  function add(s){
   if(!['playing','stalled'].includes(s.state)||!Number.isFinite(s.intervalMs)||s.intervalMs<=0||
      !Number.isSafeInteger(s.intervalFrames)||s.intervalFrames<0){excluded++;return;}
   if(samples.length>=3600){dropped++;return;}
   samples.push({intervalMs:s.intervalMs,frames:s.intervalFrames,width:s.width,height:s.height,
    longestGapMs:s.longestGapMs,state:s.state});
  }
  function snapshot(){
   const ms=samples.reduce((v,s)=>v+s.intervalMs,0),frames=samples.reduce((v,s)=>v+s.frames,0);
   return {schema:1,scope:'local browser presented frames; not native render FPS or proof of unique pixel changes',
    seconds:Math.round(ms)/1000,frames,averagePresentedFps:ms?Math.round(frames*10000/ms)/10:null,
    longestObservedGapMs:samples.reduce((v,s)=>Math.max(v,s.longestGapMs),0),
    excludedObservations:excluded,discardedAfterLimit:dropped,samples:samples.map(s=>({...s}))};
  }
  return {reset,add,snapshot};
 }
 function createMonitor({video,now,interval,clearInterval,onSample,isVisible}){
  let active=false,handle=null,timer=null,epoch=0,previous=null,lastFrame=null;
  let count=0,missed=0,longest=0,stallSince=null,stalls=0;
  let suspended=false,sampleStart=0,sampleFrames=0;
  function reset(){
   previous=null;lastFrame=null;count=missed=longest=stalls=0;stallSince=null;
   sampleStart=now();sampleFrames=0;
  }
  function start(){
   stop();active=true;reset();suspended=false;const id=epoch;
   if(typeof video.requestVideoFrameCallback!=='function'){
    active=false;onSample({state:'unsupported'});return;
   }
   function frame(t,m){
    if(!active||id!==epoch)return;
    if(!isVisible()||video.paused||video.ended){reset();suspended=true;}
    else{
     if(suspended){reset();suspended=false;}
     if(lastFrame!==null){
      const gap=Math.max(0,t-lastFrame);
      if(gap>=1000&&stallSince===null)stalls++;
      longest=Math.max(longest,gap);
     }
     lastFrame=t;stallSince=null;
     if(Number.isFinite(m.presentedFrames)){
      if(previous!==null&&m.presentedFrames>previous){
       count+=m.presentedFrames-previous;
       missed+=Math.max(0,m.presentedFrames-previous-1);
      }else if(previous!==null&&m.presentedFrames<previous){reset();}
      previous=m.presentedFrames;
     }
    }
    handle=video.requestVideoFrameCallback(frame);
   }
   handle=video.requestVideoFrameCallback(frame);
   timer=interval(()=>{
    if(!active||id!==epoch)return;
    const t=now();
    if(!isVisible()||video.paused||video.ended){
     reset();suspended=true;sampleStart=t;sampleFrames=0;
     onSample({state:'paused'});return;
    }
    if(suspended){reset();suspended=false;sampleStart=t;sampleFrames=0;}
    if(count<sampleFrames){sampleStart=t;sampleFrames=count;return;}
    const elapsed=t-sampleStart;
    if(elapsed<500)return;
    const gap=lastFrame===null?0:Math.max(0,t-lastFrame);
    if(lastFrame!==null&&gap>=1000&&stallSince===null){stalls++;stallSince=lastFrame;}
    const fps=elapsed>0?(count-sampleFrames)*1000/elapsed:0;
    onSample({state:previous===null?'waiting':gap>=1000?'stalled':'playing',
     fps:Math.round(fps*10)/10,intervalMs:elapsed,intervalFrames:count-sampleFrames,width:video.videoWidth,height:video.videoHeight,
     missedCallbacks:missed,stallEpisodes:stalls,
     longestGapMs:Math.round(Math.max(longest,gap)),frames:count});
    sampleStart=t;sampleFrames=count;
   },1000);
  }
  function stop(){
   active=false;epoch++;
   if(handle!==null&&typeof video.cancelVideoFrameCallback==='function')video.cancelVideoFrameCallback(handle);
   if(timer!==null)clearInterval(timer);
   handle=timer=null;
  }
  return {start,stop};
 }
 if(typeof module!=='undefined'&&module.exports){module.exports={createMonitor,createReport};return;}
 root.TribunOriginalMetrics={createMonitor,createReport};
})(typeof window!=='undefined'?window:globalThis);
