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
  const page=await browser.newPage({viewport:{width:1600,height:1024},deviceScaleFactor:1.25});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port+'/match.html?renderStress=1',{waitUntil:'load'});
  await page.waitForFunction(()=>{
   try{const state=window.TRIBUN_MATCH_TEST?.getState();
    return state?.players?.filter(p=>p.active&&!p.referee).length===22;}catch{return false;}
  },null,{timeout:45000});
  // Wait for the WebGL model draw, not just match data initialization.
  // SwiftShader may need longer to compile shader programs in CI.
  await page.waitForTimeout(700);
  // Main uses asynchronous licensed textures; wait for the real renderer to load.
  await page.waitForFunction(()=>{window.TRIBUN_MATCH_TEST?.renderProbe?.();return window.TRIBUN_MATCH_TEST?.animationStats()?.players>=22;},null,{polling:250,timeout:45000});
  // Exercise the *real* match renderer synchronously. On software GL a single
  // scene frame can arrive well after its game object was initialized.
  const initialProbe=await page.evaluate(()=>window.TRIBUN_MATCH_TEST.renderProbe());
  console.log('Match initial forced WebGL render: '+JSON.stringify(initialProbe));
  const before=await page.evaluate(()=>({
   clock:window.TRIBUN_MATCH_TEST.getState().time,
   score:[...window.TRIBUN_MATCH_TEST.getState().score],
   stats:window.TRIBUN_MATCH_TEST.animationStats(),
   quality:document.querySelector('[data-player-quality]')?.textContent
  }));
  console.log('Match benchmark startup: '+JSON.stringify(before));
  assert(before.stats.players>=22,'match animation bridge did not see 22 player models: '+JSON.stringify(before));
  assert(before.quality&&!before.quality.includes('YEDEK'),'match should use the licensed GPU footballer renderer');
  await page.click('#playButton'); // Freeze game state for A/B 22-player rendering.
  const frozen=await page.evaluate(()=>{
   const state=window.TRIBUN_MATCH_TEST.getState();
   return {clock:state.time,score:[...state.score],paused:state.paused};
  });
  assert.equal(frozen.paused,true,'match must be paused for comparison');
  const results=await page.evaluate(()=>{
   const api=window.TRIBUN_MATCH_TEST;
   function run(mode,enabled,count){
    api.setGraphicsMode(mode);api.setAnimationBlending(enabled);
    const out=[];let last=null;
    for(let i=0;i<count;i++){
     const p=api.renderProbe();
     if(!p.webgl||p.active!==22)throw Error('Expected true 22-player WebGL scene');
     out.push(p.cpuGpuMs);last=api.performanceStats();
    }
    return {samples:out,profile:last};
   }
   // Compare the real licensed mesh and the same 22 players in all modes.
   const quality=run('quality',true,3);
   const performance=run('performance',true,8);
   const withoutBlending=run('balanced',false,8);
   const balanced=run('balanced',true,8);
   return {quality,performance,withoutBlending,balanced,
     state:api.getState().time,score:[...api.getState().score],bridge:api.animationStats()};
  });
  for(const name of ['quality','performance','withoutBlending','balanced'])assert(results[name].samples.length>=3);
  assert(results.bridge.players>=22);
  assert(results.performance.profile.players.fast>=22,'fast broadcast shader must render all footballers');
  assert(results.quality.profile.players.detailed>=22,'quality shader must preserve full original material');
  const pixels=mode=>results[mode].profile.canvas.reduce((a,b)=>a*b,1);
  assert(pixels('performance')<pixels('quality')*.55,'performance mode must reduce GPU fragment count');

  const close=await page.evaluate(()=>{const api=window.TRIBUN_MATCH_TEST;api.setGraphicsMode('performance');return Array.from({length:5},()=>api.closeViewProbe());});
  assert(close.every(x=>x.profile.players.active>=22&&x.profile.players.players+x.profile.players.culled===x.profile.players.active));
  assert(close.some(x=>x.profile.players.culled>0),'close view must avoid offscreen draw calls');
  assert(close.every(x=>x.clock===frozen.clock&&JSON.stringify(x.score)===JSON.stringify(frozen.score)));
  report.closeCamera={method:'same paused match, close view, synchronous render+finish',...summary(close.map(x=>x.cpuGpuMs)),profile:close.at(-1).profile};
  await page.evaluate(()=>window.TRIBUN_MATCH_TEST.setGraphicsMode('balanced'));
  // No synthetic simulation mutations: sample an isolated set of visual clones
  // in the production stadium renderer while the real match is paused.
  const skill=await page.evaluate(()=>window.TRIBUN_MATCH_TEST.skillRenderProbe());
  assert.equal(skill.active,22);
  assert(skill.frames.length===24&&skill.frames.every(x=>x.webgl&&x.active===22));
  assert(skill.cues.feint>0&&skill.cues.shield>0&&skill.cues.misread>0&&skill.cues.wallPass>0);
  assert(skill.frames.every(x=>x.profile.players.lodBinds<=x.profile.players.players));
  assert(skill.clockUnchanged&&skill.scoreUnchanged&&skill.positionsUnchanged);
  assert(skill.frozen.profile.players.paletteHits>=22&&skill.frozen.profile.players.dualHits>=22,
   'unchanged skill actors must reuse exact palettes and DQ');
  const screenshot=await page.screenshot({path:path.join(destination,'match-22-players.png'),animations:'disabled',timeout:90000});
  const png=PNG.sync.read(screenshot);
  const colors=new Set();for(let i=0;i<png.data.length;i+=4*29){
   colors.add(((png.data[i]>>3)<<10)|((png.data[i+1]>>3)<<5)|(png.data[i+2]>>3));
  }
  assert(colors.size>30,'WebGL screenshot lacks visual detail');
  assert.equal(results.state,frozen.clock,'repeated rendering must not advance match clock while paused');
  assert.deepEqual(results.score,frozen.score,'rendering must not change the score');
  assert.deepEqual(errors,[],'browser console JavaScript errors');
  report.browser='Chromium SwiftShader (software WebGL)',report.kind='synchronous render+gl.finish; not a mobile FPS measurement';
  report.activeFootballers=22;report.animatedPlayers=results.bridge.players;report.bridge=results.bridge;
  report.withoutBlending=summary(results.withoutBlending.samples);report.withBlending=summary(results.balanced.samples);
  report.graphics={
   quality:{...summary(results.quality.samples),profile:results.quality.profile},
   performance:{...summary(results.performance.samples),profile:results.performance.profile},
   balanced:{...summary(results.balanced.samples),profile:results.balanced.profile}
  };
  report.skillStress={method:'24 production-WebGL frames; isolated visual clones with staged skill cues, not organically generated match events',cues:skill.cues,
   frames:summary(skill.frames.map(x=>x.cpuGpuMs)),finalProfile:skill.frames.at(-1).profile,
   repeatedFrozen:skill.frozen,clockUnchanged:skill.clockUnchanged,scoreUnchanged:skill.scoreUnchanged,positionsUnchanged:skill.positionsUnchanged};
  console.log('SKILL_RENDER_STRESS '+JSON.stringify(report.skillStress));
  report.gameClockUnchanged=true;report.scoreUnchanged=true;report.pixelColors=colors.size;report.errors=errors;
  fs.writeFileSync(path.join(destination,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log('22-player real match render benchmark: '+JSON.stringify(report));
 }finally{
  await browser.close();await new Promise(resolve=>server.close(resolve));
 }
}
main().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
