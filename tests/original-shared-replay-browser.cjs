'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {setTimeout:delay}=require('node:timers/promises');
(async()=>{
 const url=new URL(process.argv[2]);
 assert.equal(url.hostname,'127.0.0.1');
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||undefined,
  args:['--autoplay-policy=no-user-gesture-required']});
 try{
  const c1=await browser.newContext(),c2=await browser.newContext();
  const p1=await c1.newPage(),p2=await c2.newPage();
  await p1.goto(url.origin+'/viewer');
  const ready=async(page,min)=>page.waitForFunction(min=>{
   const v=document.querySelector('video'),d=window.replayDiagnostics;
   return d&&!d.error&&d.expected>=min&&!v.paused&&!v.seeking&&Math.abs(v.currentTime-d.expected)<.65;
  },min,{timeout:20000});
  await ready(p1,2);
  await delay(2500);
  await p2.goto(url.origin+'/viewer');
  await ready(p2,4);
  async function sample(){
   const rows=await Promise.all([p1,p2].map(page=>page.evaluate(()=>{
    const video=document.querySelector('video'),d=window.replayDiagnostics;
    return {current:video.currentTime,identity:d.identity,expected:d.expected,rtt:d.rtt,
     failures:d.failures,paused:video.paused};
   })));
   assert.equal(rows[0].identity,rows[1].identity);
   return {rows,skewMs:Math.abs(rows[0].current-rows[1].current)*1000};
  }
  const late=await sample();
  assert(late.rows[1].current>=4,'Late join started at zero');
  assert(late.skewMs<800,JSON.stringify(late));
  await c2.setOffline(true);
  await p2.waitForFunction(()=>window.replayDiagnostics?.error&&document.querySelector('video').paused,
   null,{timeout:6000});
  await delay(1500);
  await c2.setOffline(false);
  await ready(p2,6);
  const recovered=await sample();
  assert(recovered.rows[1].failures>0);
  assert(recovered.skewMs<800,JSON.stringify(recovered));
  await delay(1000);
  const steady=await sample();
  assert(steady.skewMs<800,JSON.stringify(steady));
  console.log(JSON.stringify({sharedClockBrowserVerified:true,lateJoin:late,reconnected:recovered,
   steady,independentBrowserContexts:2,sameHostOnly:true,publicPlaybackVerified:false,
   physicalDisplaySyncVerified:false,liveSimulation:false}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
