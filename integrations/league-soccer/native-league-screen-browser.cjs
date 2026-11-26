'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const {coverage}=require('./native-playback-evidence.cjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const cfg=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),reportPath=process.argv[3];
 assert.match(cfg.base,/^http:\/\/127\.0\.0\.1:\d+$/);assert.equal(cfg.round,0);
 const browser=await chromium.launch({headless:true,channel:process.env.TRIBUN_BROWSER_CHANNEL||'chrome',args:['--autoplay-policy=no-user-gesture-required']});
 let stage='league-screen',page;
 try{
  page=await browser.newPage({viewport:{width:390,height:844}});
  await page.addInitScript(token=>localStorage.setItem('tribun-league-token',token),cfg.homeToken);
  const errors=[];page.on('pageerror',()=>errors.push('page-error'));
  await page.goto(cfg.base+'/league.html');
  const watch=page.locator('#watchLive');
  await watch.waitFor({state:'visible',timeout:30000});
  assert.equal(await watch.getAttribute('href'),'native-league-live.html?round=0');
  assert.equal(await page.locator('#watchNative').isVisible(),false);
  await watch.click();await page.waitForURL('**/native-league-live.html?round=0');
  stage='media-authorization';
  const denied=await page.request.get(cfg.base+'/api/league/native-av/media?round=0&file=status.json',{headers:{Authorization:'Bearer '+cfg.foreignToken}});
  assert.equal(denied.status(),403);
  const noAuth=await page.request.get(cfg.base+'/api/league/native-av/media?round=0&file=status.json');assert.equal(noAuth.status(),403);
  await page.locator('#start').click();
  stage='native-playback';
  await page.waitForFunction(()=>{const d=window.TRIBUN_VIDEO_DIAGNOSTIC?.();return d?.phase==='error'||(d?.currentTime>2&&!d?.paused&&d.videoWidth>0);},{},{timeout:120000});
  const d=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());assert.notEqual(d.phase,'error');assert.equal(d.videoWidth,1280);
  await page.locator('#sound').click();assert.equal(await page.locator('video').evaluate(v=>v.muted),false);
  await page.waitForFunction(()=>document.querySelector('video').currentTime>4,{},{timeout:30000});
  const audioBytes=await page.locator('video').evaluate(v=>typeof v.webkitAudioDecodedByteCount==='number'?v.webkitAudioDecodedByteCount:null);
  if(audioBytes!==null)assert.ok(audioBytes>0);
  stage='home-ui-command';
  const command=page.locator('#sendTactics');
  await page.waitForFunction(()=>!document.querySelector('#sendTactics').disabled,{},{timeout:60000});
  await page.locator('#press').fill('75');await page.locator('#tempo').fill('80');await page.locator('#formation').selectOption('442');
  await command.click();
  await page.waitForFunction(()=>document.querySelector('#commandStatus').textContent.includes('Motor onayladı'),{},{timeout:60000});
  const home=await page.evaluate(async()=>await(await TRIBUN_LEAGUE_AV.request('tactics.json')).json());
  assert.equal(home.side,0);assert.equal(home.appliedRevision,1);assert.equal(home.lastAcknowledgement.formation,442);assert.equal(home.lastAcknowledgement.press,75);
  stage='away-command';
  const url=cfg.base+'/api/league/native-av/tactics?round=0',headers={Authorization:'Bearer '+cfg.awayToken};
  let away;
  const readyDeadline=Date.now()+60000;
  while(Date.now()<readyDeadline){
   const r=await page.request.get(url,{headers});if(r.ok()){away=await r.json();if(away.canControl)break;}
   await sleep(500);
  }
  assert.ok(away?.canControl);assert.equal(away.side,1);
  const body={round:0,requestId:'stage150-away',tactics:{press:35,counter:50,support:50,width:50,tempo:40,formation:4231}};
  const posted=await page.request.post(url,{headers,data:body});assert.equal(posted.status(),202);
  const accepted=await posted.json();assert.equal(accepted.revision,1);
  const ackDeadline=Date.now()+60000;
  while(Date.now()<ackDeadline){const r=await page.request.get(url,{headers});if(r.ok()){away=await r.json();if(away.appliedRevision===1)break;}await sleep(500);}
  assert.equal(away.appliedRevision,1);assert.equal(away.lastAcknowledgement.formation,4231);assert.equal(away.lastAcknowledgement.press,35);
  stage='full-playback';
  const deadline=Date.now()+390000;let samples=0,last=null,stagnantSince=Date.now(),longest=0;
  while(Date.now()<deadline){
   const state=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC());samples++;
   assert.notEqual(state.phase,'error');assert.equal(state.mediaError,null);
   if(last===null||state.currentTime>last+.05){longest=Math.max(longest,Date.now()-stagnantSince);stagnantSince=Date.now();last=state.currentTime;}
   else if(Date.now()-stagnantSince>15000&&!state.ended)throw Error('Playback stalled');
   if(state.ended){
    const result={...coverage(state,300),samples,longestObservedProgressIntervalMs:longest,leagueScreenVerified:true,homeUICommandVerified:true,awayCommandVerified:true,foreignMediaRejected:true,unauthenticatedMediaRejected:true,audioDecodedBytes:audioBytes};
    assert.deepEqual(errors,[]);assert.equal(result.passed,true);
    fs.writeFileSync(reportPath,JSON.stringify(result,null,2)+'\n');return;
   }
   await sleep(500);
  }
  throw Error('Playback completion deadline');
 }catch(e){
  let diagnostic=null;try{diagnostic=await page.evaluate(()=>window.TRIBUN_VIDEO_DIAGNOSTIC?.()||null);}catch{}
  fs.mkdirSync(require('node:path').dirname(reportPath),{recursive:true});
  fs.writeFileSync(reportPath,JSON.stringify({passed:false,stage,failureType:e.name,diagnostic},null,2)+'\n');
  console.error('Native league screen failure at '+stage);process.exitCode=1;
 }finally{await browser.close();}
})().catch(()=>{console.error('Native league screen setup failed');process.exitCode=1;});
