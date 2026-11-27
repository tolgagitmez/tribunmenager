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
  // Test only UI presentation of explicit read-only inventory responses.
  // Native launch, save manipulation and file contents are never mocked as verified.
  let inventory={available:true,hasSnapshot:true,recoveryCount:2,
   interruptedSessionCount:0,inventoryTruncated:false,valid:true};
  await context.route('**/api/original/status',route=>route.fulfill({
   json:{supported:true,installed:true,running:false,lastExitCode:0,
    nativeDesktop:true,managerBridge:false,saveStore:inventory}
  }));
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
  // Use the actual manager tactics page to save a plan in this isolated browser.
  await page.goto(new URL('tactics.html',url).href,{waitUntil:'domcontentloaded'});
  await page.locator('[data-preset="press"]').click();
  const saved=await page.evaluate(()=>localStorage.getItem('tribun-manager-pro09'));
  assert.ok(saved,'Web tactics page must persist the chosen plan');
  const manager=JSON.parse(saved);
  assert.equal(manager.tactics.press,86);
  assert.equal(manager.starters.length,11);
  const writes=[];
  page.on('request',req=>{
   if(!['GET','HEAD','OPTIONS'].includes(req.method()))writes.push(req.method()+' '+req.url());
  });
  await page.goto(url,{waitUntil:'domcontentloaded'});
  const managerStatus=page.locator('#managerPlanStatus');
  const managerDetails=page.locator('#managerPlanDetails');
  await managerStatus.filter({hasText:'Orijinal motora uygulanmadı.'}).waitFor();
  const managerText=await managerDetails.textContent();
  assert.ok(managerText.includes(manager.formation));
  assert.ok(managerText.includes('Baskı : 86'));
  for(const index of manager.starters)assert.ok(managerText.includes(manager.players[index].name));
  assert.equal(await page.evaluate(()=>localStorage.getItem('tribun-manager-pro09')),saved);
  // An absent plan must not recreate defaults or send a native command.
  await page.evaluate(()=>localStorage.removeItem('tribun-manager-pro09'));
  await page.locator('#originalRefresh').click();
  await managerStatus.filter({hasText:'kaydedilmiş menajer planı bulunamadı'}).waitFor();
  assert.equal(await managerDetails.locator('li').count(),0);
  assert.equal(await page.evaluate(()=>localStorage.getItem('tribun-manager-pro09')),null);
  const saveNote=page.locator('#nativeSaveStoreStatus');
  await saveNote.filter({hasText:'Saklanmış lig kayıtları mevcut.'}).waitFor();
  assert.match(await saveNote.textContent(),/2 kurtarma klasörü/);
  inventory={...inventory,valid:false};
  await page.locator('#originalRefresh').click();
  await saveNote.filter({hasText:'Lig kayıt deposu incelenemedi'}).waitFor();
  inventory={...inventory,valid:true,hasSnapshot:false,recoveryCount:0,interruptedSessionCount:1};
  await page.locator('#originalRefresh').click();
  await saveNote.filter({hasText:'Henüz saklanmış lig kaydı yok.'}).waitFor();
  assert.match(await saveNote.textContent(),/başka oturum açık olabilir/);
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
  assert.deepEqual(writes,[],'Original engine page must not send a write request during read-only preview');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({browserPlaybackVerified:true,managerPlanBrowserVerified:true,managerPlanStorageUnchanged:true,syntheticCanvasStream:true,
   nativeWindowPickerVerified:false,nativeMatchVerified:false,reportDownloadVerified:true,
   sampleSeconds:report.seconds,averagePresentedFps:report.averagePresentedFps}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
