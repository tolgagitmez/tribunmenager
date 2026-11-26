'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const file=process.argv[2],deadline=Date.now()+120000;
 while(!fs.existsSync(file)){if(Date.now()>deadline)throw Error('Local server did not start');await new Promise(r=>setTimeout(r,250));}
 const url=fs.readFileSync(file,'utf8').trim();
 assert.match(url,/^http:\/\/127\.0\.0\.1:\d+\/[\w-]+\/$/);
 const browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.locator('#start').click();
  await page.waitForFunction(()=>document.querySelector('video').currentTime>2&&!document.querySelector('video').paused,{},{timeout:120000});
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
    await m.close();
   }
   console.log('Both manager commands acknowledged by the actual native engine while video plays.');
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({playedDuringMatch:true,mediaTime:state.time,videoWidth:state.width}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
