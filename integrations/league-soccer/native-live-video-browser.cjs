'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const {coverage}=require('./native-playback-evidence.cjs');
(async()=>{
 const file=process.argv[2],deadline=Date.now()+120000;
 while(!fs.existsSync(file)){if(Date.now()>deadline)throw Error('Local server did not start');await new Promise(r=>setTimeout(r,250));}
 const url=fs.readFileSync(file,'utf8').trim();
 assert.match(url,/^http:\/\/127\.0\.0\.1:\d+\/[\w-]+\/$/);
 const browser=await chromium.launch({headless:true,channel:process.env.TRIBUN_BROWSER_CHANNEL||'chrome',args:['--autoplay-policy=no-user-gesture-required']});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.locator('#start').click();
  try{
   await page.waitForFunction(()=>{const d=window.TRIBUN_VIDEO_DIAGNOSTIC?.();return d?.phase==='error'||(d?.currentTime>2&&!d?.paused&&d.videoWidth>0);},{},{timeout:90000});
   const d=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());assert.notEqual(d.phase,'error',JSON.stringify(d));
  }catch(e){
   const d=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC?.()||{message:document.querySelector('#status')?.textContent});
   console.error('Playback diagnostic:',JSON.stringify(d));throw e;
  }
  const state=await page.evaluate(async()=>({status:await(await fetch('status.json')).json(),time:document.querySelector('video').currentTime,width:document.querySelector('video').videoWidth}));
  assert.equal(state.status.phase,'streaming');assert.ok(state.width>0);
  if(process.env.TRIBUN_EXPECT_AUDIO==='1'){
   assert.equal(state.status.audioRequested,true);
   await page.locator('#sound').click();assert.equal(await page.locator('video').evaluate(v=>v.muted),false);
   await page.waitForFunction(()=>document.querySelector('video').currentTime>4,{},{timeout:30000});
   const bytes=await page.locator('video').evaluate(v=>typeof v.webkitAudioDecodedByteCount==='number'?v.webkitAudioDecodedByteCount:null);
   if(bytes!==null)assert.ok(bytes>0,'No decoded audio bytes');
   console.log(JSON.stringify({audioRequested:true,unmuted:true,decodedAudioBytes:bytes}));
  }
  if(process.env.TRIBUN_EXPECT_SUSTAINED==='1'){
   const start=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());
   await page.waitForFunction(t=>{const d=window.TRIBUN_VIDEO_DIAGNOSTIC();return d.phase==='error'||d.currentTime>=t+8;},start.currentTime,{timeout:25000});
   const end=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());
   assert.notEqual(end.phase,'error',JSON.stringify(end));assert.ok(end.currentTime>=start.currentTime+8);
   const late=await browser.newPage({viewport:{width:390,height:844}});
   try{
    await late.goto(url);await late.locator('#start').click();
    await late.waitForFunction(()=>{const d=window.TRIBUN_VIDEO_DIAGNOSTIC?.();return d?.phase==='error'||(d?.videoWidth>0&&!d.paused&&d.currentTime>4);},{},{timeout:30000});
    const a=await late.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());
    assert.notEqual(a.phase,'error',JSON.stringify(a));
    await late.waitForFunction(t=>{const d=window.TRIBUN_VIDEO_DIAGNOSTIC();return d.phase==='error'||d.currentTime>=t+3;},a.currentTime,{timeout:15000});
    const b=await late.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());assert.notEqual(b.phase,'error',JSON.stringify(b));assert.ok(b.currentTime>=a.currentTime+3);
    const original=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());
    assert.notEqual(original.phase,'error',JSON.stringify(original));assert.ok(original.currentTime>end.currentTime);
    console.log(JSON.stringify({sustainedPlayback:true,lateViewer:true,originalMediaTime:original.currentTime,lateMediaTime:b.currentTime,mediaTimeDifference:Math.abs(original.currentTime-b.currentTime)}));
   }finally{await late.close();}
  }
  if(process.env.TRIBUN_EXPECT_CONTROL==='1'){
   const dir=require('node:path').dirname(file);
   const urls=[0,1].map(side=>fs.readFileSync(require('node:path').join(dir,'local-manager-'+side+'.txt'),'utf8').trim());
   assert.equal(await page.locator('#manager').isVisible(),false);
   const managers=await Promise.all(urls.map(()=>browser.newPage({viewport:{width:390,height:844}})));
   for(let side=0;side<2;side++){
    const m=managers[side];await m.goto(urls[side]);
    await m.waitForFunction(()=>!document.querySelector('#sendTactics').disabled,{},{timeout:60000});
    await m.locator('#press').fill(side===0?'75':'35');
    await m.locator('#tempo').fill(side===0?'80':'40');
    await m.locator('#formation').selectOption(side===0?'442':'4231');
    await m.locator('#sendTactics').click();
    await m.waitForFunction(()=>document.querySelector('#commandStatus').textContent.includes('Motor onayladı'),{},{timeout:60000});
    const ack=await m.evaluate(async()=>await(await fetch('tactics.json')).json());
    assert.equal(ack.side,side);assert.equal(ack.appliedRevision,1);
    assert.equal(ack.lastAcknowledgement.revision,1);
    assert.equal(ack.lastAcknowledgement.formation,side===0?442:4231);
    assert.equal(ack.lastAcknowledgement.press,side===0?75:35);
    assert.ok(ack.lastAcknowledgement.appliedMatchMs<=ack.engineMatchMs);
    const spectator=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());
    assert.notEqual(spectator.phase,'error',JSON.stringify(spectator));
    assert.ok(spectator.videoWidth>0);
    await m.close();
   }
   console.log('Both manager commands acknowledged by the actual native engine while video plays.');
  }
  if(process.env.TRIBUN_EXPECT_FULL_PLAYBACK==='1'){
   const minSeconds=Number(process.env.TRIBUN_PLAYBACK_MIN_SECONDS||'300');
   assert.ok(Number.isFinite(minSeconds)&&minSeconds>0&&minSeconds<=900);
   const path=require('node:path').join(require('node:path').dirname(file),'browser-playback-report.json');
   const deadline=Date.now()+Math.round((minSeconds+90)*1000);
   let last=null,stagnantSince=Date.now(),samples=0,longestStallMs=0;
   try{
    while(Date.now()<deadline){
     const d=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());
     assert.notEqual(d.phase,'error',JSON.stringify(d));assert.equal(d.mediaError,null);
     samples++;
     if(last===null||d.currentTime>last+.05){longestStallMs=Math.max(longestStallMs,Date.now()-stagnantSince);stagnantSince=Date.now();last=d.currentTime;}
     else if(Date.now()-stagnantSince>15000&&!d.ended)throw Error('Playback stopped progressing for 15 seconds');
     if(d.ended){
      const result=coverage(d,minSeconds);
      const report={...result,samples,longestObservedProgressIntervalMs:longestStallMs,syntheticOnly:minSeconds<300};
      fs.writeFileSync(path,JSON.stringify(report,null,2)+'\n');
      console.log(JSON.stringify(report));assert.ok(result.passed,JSON.stringify(result));break;
     }
     await new Promise(resolve=>setTimeout(resolve,500));
    }
    assert.ok(fs.existsSync(path),'Playback did not reach actual ended event');
   }catch(error){
    if(!fs.existsSync(path)){
     const d=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());
     fs.writeFileSync(path,JSON.stringify({passed:false,error:String(error.message).slice(0,500),diagnostic:d,samples},null,2)+'\n');
    }
    throw error;
   }
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({playedDuringMatch:true,mediaTime:state.time,videoWidth:state.width}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
