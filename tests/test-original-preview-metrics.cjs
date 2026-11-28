'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createMonitor,createReport}=require('../original-preview-metrics.js');

function setup(){
 let time=0,visible=true,tick,callback;
 let cancelCount=0,clearCount=0;
 const samples=[];
 const video={paused:false,ended:false,videoWidth:1280,videoHeight:720,
  requestVideoFrameCallback(fn){callback=fn;return 1;},
  cancelVideoFrameCallback(){cancelCount++;}};
 const monitor=createMonitor({video,now:()=>time,interval:fn=>{tick=fn;return 1;},
  clearInterval:()=>{clearCount++;},onSample:s=>samples.push(s),isVisible:()=>visible});
 return {monitor,video,samples,frame(t,n){time=t;callback(t,{presentedFrames:n});},
  tick(t){time=t;tick();},setVisible(v){visible=v;},
  cleanup:()=>[cancelCount,clearCount]};
}

test('30 presented fps and actual dimensions',()=>{
 const s=setup();s.monitor.start();s.frame(0,1);
 for(let i=1;i<=30;i++)s.frame(i*1000/30,i+1);
 s.tick(1000);
 assert.equal(s.samples.at(-1).fps,30);
 assert.equal(s.samples.at(-1).width,1280);
 assert.equal(s.samples.at(-1).stallEpisodes,0);
});

test('startup delay is waiting, not a stall',()=>{
 const s=setup();s.monitor.start();s.tick(2000);
 assert.equal(s.samples.at(-1).state,'waiting');
 assert.equal(s.samples.at(-1).stallEpisodes,0);
});

test('one continuous frame gap counts once, then recovery',()=>{
 const s=setup();s.monitor.start();s.frame(100,1);s.tick(1200);s.tick(2200);
 assert.equal(s.samples.at(-1).state,'stalled');
 assert.equal(s.samples.at(-1).stallEpisodes,1);
 s.frame(2300,2);s.tick(3200);
 assert.equal(s.samples.at(-1).state,'playing');
 assert.equal(s.samples.at(-1).stallEpisodes,1);
 assert.equal(s.samples.at(-1).longestGapMs,2200);
});

test('missed observer callbacks are not counted as dropped frames',()=>{
 const s=setup();s.monitor.start();s.frame(0,1);s.frame(1000,31);s.tick(1000);
 assert.equal(s.samples.at(-1).fps,30);
 assert.equal(s.samples.at(-1).missedCallbacks,29);
});

test('hidden tab interval is excluded',()=>{
 const s=setup();s.monitor.start();s.frame(0,1);s.setVisible(false);s.tick(2000);
 assert.equal(s.samples.at(-1).state,'paused');
 s.setVisible(true);s.frame(5000,10);s.frame(5100,11);s.frame(5500,12);s.tick(5600);
 assert.equal(s.samples.at(-1).stallEpisodes,0);
 assert.equal(s.samples.at(-1).longestGapMs,400);
 assert.equal(s.samples.at(-1).fps,3.3);
});

test('stop cancels callbacks and prevents late samples',()=>{
 const s=setup();s.monitor.start();s.monitor.stop();s.frame(1000,10);s.tick(2000);
 assert.deepEqual(s.cleanup(),[1,1]);
 assert.equal(s.samples.length,0);
});

test('report weights FPS by measured duration and excludes waiting/paused',()=>{
 const report=createReport();
 const base={state:'playing',width:1280,height:720,longestGapMs:33};
 report.add({...base,intervalMs:1000,intervalFrames:30});
 report.add({...base,intervalMs:2000,intervalFrames:40,longestGapMs:1200,state:'stalled'});
 report.add({state:'paused'});report.add({state:'waiting'});
 const data=report.snapshot();
 assert.equal(data.seconds,3);
 assert.equal(data.frames,70);
 assert.equal(data.averagePresentedFps,23.3);
 assert.equal(data.longestObservedGapMs,1200);
 assert.equal(data.excludedObservations,2);
 assert.equal(data.samples.length,2);
 report.reset();
 assert.equal(report.snapshot().averagePresentedFps,null);
});

test('report is bounded and contains only numeric sample fields and state',()=>{
 const report=createReport();
 for(let i=0;i<3602;i++)report.add({state:'playing',intervalMs:1000,intervalFrames:30,
    width:1280,height:720,longestGapMs:34,windowTitle:'private',pixels:'private'});
 const data=report.snapshot();
 assert.equal(data.samples.length,3600);
 assert.equal(data.discardedAfterLimit,2);
 assert.equal(data.samples[0].windowTitle,undefined);
 assert.equal(data.samples[0].pixels,undefined);
 data.samples[0].frames=0;
 assert.equal(report.snapshot().frames,108000);
});
