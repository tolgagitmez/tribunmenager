'use strict';
/* 22 on-pitch licensed footballers in the ACTUAL match.html.
 * Desktop and touch/mobile-viewport Chromium SwiftShader are reference
 * profiles, not real desktop GPU or physical phone measurements. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {createServer}=require('./serve-character-viewer.cjs');
const destination=path.resolve('dist/live-contact-pilot');
const sorted=values=>values.slice().sort((a,b)=>a-b);
function summary(values,threshold){
 const a=sorted(values),pct=p=>a[Math.min(a.length-1,Math.ceil(p*a.length)-1)]||null;
 return {frames:a.length,medianMs:pct(.5),p95Ms:pct(.95),maxMs:a.at(-1),
  withinBudget:a.filter(x=>x<=threshold).length,
  passRate:a.filter(x=>x<=threshold).length/a.length,frameBudgetMs:threshold};
}
async function run(browser,url,profile){
 const context=await browser.newContext({viewport:profile.viewport,
  deviceScaleFactor:profile.dpr,isMobile:profile.mobile,hasTouch:profile.mobile});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 try{
  await page.goto(url+'?pilot=1',{waitUntil:'load',timeout:45000});
  await page.waitForFunction(()=>window.TRIBUN_MATCH_TEST?.getState?.().players?.filter(p=>p.active&&!p.referee).length===22,null,{timeout:45000});
  await page.waitForFunction(()=>['ready','fallback'].includes(window.TRIBUN_MATCH_TEST?.pilotStats?.().status),null,{timeout:80000});
  const status=await page.evaluate(()=>window.TRIBUN_MATCH_TEST.pilotStats());
  assert.equal(status.status,'ready','Blender four-clip import did not reach match: '+status.reason);
  for(const kind of ['idle','run','shoot','dive-right'])assert(status.clips.includes(kind));
  const variants={};
  for(const mode of ['quality','balanced','performance']){
   await page.evaluate(mode=>window.TRIBUN_MATCH_TEST.setGraphicsMode(mode),mode);
   // Warm the real 22-player stadium renderer before sampling frame pacing.
   const readings=await page.evaluate(async()=>{
    const api=window.TRIBUN_MATCH_TEST,frames=[];
    await new Promise(resolve=>{
     let last=null;
     const tick=now=>{
      if(last!==null)frames.push(now-last);
      last=now;
      if(frames.length>=48)resolve();
      else requestAnimationFrame(tick);
     };
     requestAnimationFrame(tick);
    });
    const probe=api.renderProbe(),perf=api.performanceStats(),pilot=api.pilotStats();
    return {frames,probe,perf,pilot};
   });
   assert.equal(readings.probe.active,22);
   assert(readings.probe.webgl,'actual match must use WebGL');
   assert(readings.pilot.blenderSamples>0,'real Blender palettes must have been sampled');
   variants[mode]={...summary(readings.frames,profile.budget),renderProbeMs:readings.probe.cpuGpuMs,
    rendered:readings.perf.players,canvas:readings.perf.canvas,
    pilot:{clip:readings.pilot.clip,blenderSamples:readings.pilot.blenderSamples,
     contactFrames:readings.pilot.contactFrames,
     maxSupportHeightError:readings.pilot.maxSupportHeightError}};
  }
  const score=await page.evaluate(()=>[...window.TRIBUN_MATCH_TEST.getState().score]);
  await page.screenshot({path:path.join(destination,profile.name+'.png'),timeout:60000});
  assert.deepEqual(errors,[],'browser JavaScript errors');
  return {profile:profile.name,environment:'Chromium SwiftShader software GL + viewport emulation',
    actualDevice:false,dimensions:profile.viewport,deviceScaleFactor:profile.dpr,frameBudgetMs:profile.budget,
    renderer:'production custom WebGL1/DQ with licensed player mesh and single Blender upper-body pilot',
    activePlayers:22,variants,score,errors};
 }finally{await context.close();}
}
async function main(){
 fs.mkdirSync(destination,{recursive:true});
 const server=createServer();await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
 const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
 try{
  const url='http://127.0.0.1:'+server.address().port+'/match.html';
  const profiles=[{name:'desktop-reference',viewport:{width:1440,height:900},dpr:1,mobile:false,budget:16.7},
   {name:'mobile-viewport-emulation',viewport:{width:390,height:844},dpr:2,mobile:true,budget:33.3}];
  const result={method:'requestAnimationFrame intervals with real 22-player Match advancing, plus forced gl.finish render probe. 48 samples per graphics mode, not physical device measurement.',profiles:[]};
  for(const profile of profiles){
   const measured=await run(browser,url,profile);result.profiles.push(measured);
   console.log('MATCH_FRAME_PROFILE '+JSON.stringify(measured));
  }
  result.recommendation='Retain production custom renderer while comparing quality/balanced/performance at measured real-match scene sizes. SwiftShader cannot certify 95th-percentile deadlines on desktop GPU or physical phone; verify on representative hardware.';
  fs.writeFileSync(path.join(destination,'report.json'),JSON.stringify(result,null,2)+'\n');
 }finally{await browser.close();await new Promise(ok=>server.close(ok));}
}
main().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
