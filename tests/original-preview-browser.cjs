'use strict';
// Real Chromium playback + report export; capture permission is deliberately
// substituted with a deterministic canvas MediaStream. Not native window sharing.
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const {chromium}=require('playwright');

(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const context=await browser.newContext({acceptDownloads:true});
  await context.route('**/*',route=>{
   const url=new URL(route.request().url());
   return url.hostname==='127.0.0.1'?route.continue():route.abort();
  });
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   window.__testCaptureCalls=0;
   window.__testTrack=null;
   // Actual HTML video MediaStream and requestVideoFrameCallback, no native
   // picker or actual engine frame claims.
   Object.defineProperty(navigator.mediaDevices,'getDisplayMedia',{configurable:true,value:async()=>{
    window.__testCaptureCalls++;
    const canvas=document.createElement('canvas');canvas.width=640;canvas.height=360;
    const ctx=canvas.getContext('2d');
    let index=0;
    const draw=()=>{
     ctx.fillStyle='#123456';ctx.fillRect(0,0,640,360);
     ctx.fillStyle='#ffffff';ctx.fillRect((index++*11)%550,80,80,80);
    };
    draw();
    const stream=canvas.captureStream(30),track=stream.getVideoTracks()[0];
    const settings=track.getSettings.bind(track);
    Object.defineProperty(track,'getSettings',{value:()=>({...settings(),displaySurface:'window'})});
    const stop=track.stop.bind(track),timer=setInterval(draw,33);
    Object.defineProperty(track,'stop',{value:()=>{clearInterval(timer);stop();}});
    window.__testTrack=track;
    return stream;
   }});
  });
  const url=process.env.ORIGINAL_TEST_URL||'http://127.0.0.1:8765/original-engine.html';
  await page.goto(url,{waitUntil:'domcontentloaded'});
  assert.equal(await page.evaluate(()=>window.__testCaptureCalls),0);
  await page.locator('#originalPreviewStart').click();
  await page.waitForFunction(()=>document.querySelector('#originalPreviewVideo').videoWidth===640);
  await page.waitForFunction(()=>!document.querySelector('#originalPreviewReport').disabled,{},{timeout:15000});
  await page.waitForTimeout(2200);
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#originalPreviewReport').click()]);
  const report=JSON.parse(await fs.readFile(await download.path(),'utf8'));
  assert.equal(report.schema,1);
  assert.ok(report.seconds>=1);
  assert.ok(report.frames>0);
  assert.ok(report.averagePresentedFps>0);
  assert.ok(report.samples.every(s=>s.width===640&&s.height===360));
  await page.locator('#originalPreviewStop').click();
  assert.equal(await page.evaluate(()=>document.querySelector('#originalPreviewVideo').srcObject===null),true);
  assert.equal(await page.evaluate(()=>window.__testTrack.readyState),'ended');
  assert.equal(await page.locator('#originalPreviewReport').isEnabled(),true);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({browserPlaybackVerified:true,syntheticCanvasStream:true,
   nativeWindowPickerVerified:false,nativeMatchVerified:false,reportDownloadVerified:true,
   sampleSeconds:report.seconds,averagePresentedFps:report.averagePresentedFps}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
