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
  assert.equal(state.status.phase,'streaming');assert.ok(state.width>0);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({playedDuringMatch:true,mediaTime:state.time,videoWidth:state.width}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
