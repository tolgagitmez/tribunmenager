'use strict';
// CI ONLY: real native window capture on the isolated Xvfb display.
// No mock MediaStream or fake capture devices. The title selection switch
// is Chromium's test facility, never part of production launch.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');

(async()=>{
 if(process.env.TRIBUN_PRIVATE_NATIVE_TEST!=='1'||!/^:\d+(\.\d+)?$/.test(process.env.DISPLAY||''))
  throw Error('Only run in the disposable native capture test display');
 const browser=await chromium.launch({headless:false,args:[
  '--auto-select-window-capture-source-by-title=League Soccer',
  '--disable-background-timer-throttling','--disable-renderer-backgrounding'
 ]});
 try{
  const context=await browser.newContext({viewport:{width:1000,height:760}});
  await context.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/original-engine.html',{waitUntil:'domcontentloaded'});
  assert.equal(await page.evaluate(()=>document.querySelector('#originalPreviewVideo').srcObject),null);
  await page.locator('#originalPreviewStart').click();
  await page.waitForFunction(()=>{
   const v=document.querySelector('#originalPreviewVideo');
   return v.videoWidth>0&&v.videoHeight>0&&v.srcObject?.getVideoTracks()[0]?.getSettings().displaySurface==='window';
  },{},{timeout:20000});
  const result=await page.evaluate(async()=>{
   const video=document.querySelector('#originalPreviewVideo');
   const track=video.srcObject.getVideoTracks()[0];
   const canvas=document.createElement('canvas');canvas.width=160;canvas.height=90;
   const ctx=canvas.getContext('2d',{willReadFrequently:true});
   let previous=null,changes=0,samples=0;
   const start=Date.now();
   for(let i=0;i<24;i++){
    await new Promise(r=>setTimeout(r,250));
    if(track.readyState!=='live')throw Error('Native stream ended during observation');
    ctx.drawImage(video,0,0,160,90);
    const data=ctx.getImageData(0,0,160,90).data;
    // Exact downsampled pixel comparison; no images retained or exported.
    if(previous&&data.some((v,j)=>v!==previous[j]))changes++;
    previous=data.slice();samples++;
   }
   const settings=track.getSettings();
   return {startMs:start,endMs:Date.now(),surface:settings.displaySurface,
    width:video.videoWidth,height:video.videoHeight,samples,changedSamples:changes};
  });
  assert.equal(result.surface,'window');
  assert.ok(result.changedSamples>0,'Real shared image did not change');
  await page.waitForFunction(()=>!document.querySelector('#originalPreviewReport').disabled,{},{timeout:5000});
  await page.locator('#originalPreviewStop').click();
  assert.equal(await page.evaluate(()=>document.querySelector('#originalPreviewVideo').srcObject===null),true);
  assert.deepEqual(errors,[]);
  console.log('NATIVE_BROWSER_RESULT '+JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
