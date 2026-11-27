'use strict';
// Measures frames presented by the browser, not native render FPS or physics.
(function(root){
 function createMonitor({video,now,interval,clearInterval,onSample,isVisible}){
  let active=false,handle=null,timer=null,epoch=0,previous=null,lastFrame=null;
  let count=0,missed=0,longest=0,stallSince=null,stalls=0;
  let suspended=false;
  function reset(){
   previous=null;lastFrame=null;count=missed=longest=stalls=0;stallSince=null;
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
   let sampleStart=now(),sampleFrames=0;
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
     fps:Math.round(fps*10)/10,width:video.videoWidth,height:video.videoHeight,
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
 if(typeof module!=='undefined'&&module.exports){module.exports={createMonitor};return;}
 root.TribunOriginalMetrics={createMonitor};
})(typeof window!=='undefined'?window:globalThis);
