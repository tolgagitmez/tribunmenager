'use strict';
/* Actual match.html / Stadium3D / PlayerRenderer / 22 footballers.
   CPU+GPU sync timings are SwiftShader reference measurements only, NOT
   mobile-device FPS guarantees. No match physics mutations in this test. */
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const {PNG}=require('pngjs');
const assert=require('node:assert/strict');
const {createServer}=require('./serve-character-viewer.cjs');
const destination=path.resolve('dist/match-animation-benchmark');
function summary(values){
 const a=values.slice().sort((x,y)=>x-y),pct=p=>a[Math.min(a.length-1,Math.floor(p*(a.length-1)))];
 return {samples:a.length,minMs:a[0],medianMs:pct(.5),p95Ms:pct(.95),maxMs:a[a.length-1],
  meanMs:a.reduce((sum,n)=>sum+n,0)/a.length};
}
async function main(){
 fs.mkdirSync(destination,{recursive:true});
 const server=createServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
 const errors=[],report={};
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1024},deviceScaleFactor:1});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port+'/match.html',{waitUntil:'load'});
  await page.waitForFunction(()=>{
   try{const state=window.TRIBUN_MATCH_TEST?.getState();
    return state?.players?.filter(p=>p.active&&!p.referee).length===22;}catch{return false;}
  },null,{timeout:45000});
  // Let the real match presentation sample players while the match runs.
  await page.waitForTimeout(700);
  const before=await page.evaluate(()=>({
   clock:window.TRIBUN_MATCH_TEST.getState().time,
   score:[...window.TRIBUN_MATCH_TEST.getState().score],
   stats:window.TRIBUN_MATCH_TEST.animationStats(),
   quality:document.querySelector('[data-player-quality]')?.textContent
  }));
  assert(before.stats.players>=22,'match animation bridge did not see 22 player models');
  assert(before.quality?.includes('YENİ OYUNCU MODELİ'),'match should use skinned GPU footballers');
  await page.click('#playButton'); // Freeze game state for A/B 22-player rendering.
  const results=await page.evaluate(()=>{
   const api=window.TRIBUN_MATCH_TEST;
   const run=(enabled,count)=>{
    api.setAnimationBlending(enabled);
    const out=[];
    for(let i=0;i<count;i++){
     const p=api.renderProbe();
     if(!p.webgl||p.active!==22)throw Error('Expected true 22-player WebGL scene');
     out.push(p.cpuGpuMs);
    }
    return out;
   };
   run(true,3); // shader and WebGL warmup
   const baseline=run(false,12),blended=run(true,12);
   return {baseline,blended,state:api.getState().time,score:[...api.getState().score],
    bridge:api.animationStats()};
  });
  assert.equal(results.baseline.length,12);assert.equal(results.blended.length,12);
  assert(results.bridge.players>=22);
  const screenshot=await page.locator('#stadiumCanvas').screenshot({path:path.join(destination,'match-22-players.png')});
  const png=PNG.sync.read(screenshot);
  const colors=new Set();for(let i=0;i<png.data.length;i+=4*29){
   colors.add(((png.data[i]>>3)<<10)|((png.data[i+1]>>3)<<5)|(png.data[i+2]>>3));
  }
  assert(colors.size>30,'WebGL screenshot lacks visual detail');
  assert.equal(results.state,before.clock,'repeated rendering must not advance match clock while paused');
  assert.deepEqual(results.score,before.score,'rendering must not change the score');
  assert.deepEqual(errors,[],'browser console JavaScript errors');
  report.browser='Chromium SwiftShader (software WebGL)',report.kind='synchronous render+gl.finish; not a mobile FPS measurement';
  report.activeFootballers=22;report.animatedPlayers=results.bridge.players;report.bridge=results.bridge;
  report.withoutBlending=summary(results.baseline);report.withBlending=summary(results.blended);
  report.gameClockUnchanged=true;report.scoreUnchanged=true;report.pixelColors=colors.size;report.errors=errors;
  fs.writeFileSync(path.join(destination,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log('22-player real match render benchmark: '+JSON.stringify(report));
 }finally{
  await browser.close();await new Promise(resolve=>server.close(resolve));
 }
}
main().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
