'use strict';
const assert=require('node:assert/strict'),{once}=require('node:events'),{chromium}=require('playwright');
const {createServer}=require('../../tools/serve-character-viewer.cjs');
function packet(seq,score=[0,0],done=false){
 const players=Array.from({length:22},(_,i)=>({id:i,databaseId:i+1,team:i<11?0:1,position:[i<11?-20:20,(i%11-5)*4,0],velocity:[1,0,0],direction:[1,0,0],goalkeeper:i%11===0,heightMetres:i%2===0?1.72:1.95}));
 return {engine:'league-soccer',authoritative:false,sequence:seq,phase:done?'finished':'playing',state:'ready',source:'interactive-native',canControl:!done,remainingMs:done?0:200000,homeName:'Ev',awayName:'Dep',players:players.map(p=>({nativeId:p.databaseId,name:'Oyuncu '+p.id,slot:p.id%11,number:p.id%11+1})),frame:{schema:1,engine:'league-soccer',elapsedMs:seq*100,matchMs:done?5400000:seq*1800,done,inPlay:!done,setPiece:false,score,ball:[0,0,.11],ballVelocity:[0,0,0],players}};
}
(async()=>{
 const server=createServer();server.listen(0,'127.0.0.1');await once(server,'listening');
 let browser;
 try{
  browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('tribun-league-token','synthetic-test-token'));
  let response=packet(20,[1,0]),requests=0,commands=0;
  await page.route('**/api/league/native-pilot/broadcast?*',async route=>{
   requests++;assert.equal(route.request().headers().authorization,'Bearer synthetic-test-token');
   await route.fulfill({json:response});
  });
  await page.route('**/api/league/native-pilot/tactics',async route=>{commands++;await route.fulfill({json:{revision:1}});});
  await page.goto('http://127.0.0.1:'+server.address().port+'/native-match.html');
  await page.waitForFunction(()=>window.TRIBUN_NATIVE_STREAM_TEST?.state()?.sequence===20);
  assert.equal(await page.evaluate(()=>window.TRIBUN_NATIVE_STREAM_TEST.webgl()),true);
  await page.waitForFunction(()=>window.TRIBUN_NATIVE_STREAM_TEST.presentation().modelReady,{},{timeout:30000});
  await page.locator('#advancedPresentation').check();
  await page.locator('#quality').selectOption('performance');
  await page.waitForFunction(()=>{const p=window.TRIBUN_NATIVE_STREAM_TEST.presentation();return p.enabled&&p.graphics.canvas[0]*p.graphics.canvas[1]<=450000;});
  response=packet(21,[1,0]);
  await page.waitForFunction(()=>window.TRIBUN_NATIVE_STREAM_TEST.state()?.sequence===21);
  response=packet(21,[9,0]);
  await page.waitForFunction(()=>document.querySelector('#sendTactics').disabled);
  assert.deepEqual(await page.evaluate(()=>window.TRIBUN_NATIVE_STREAM_TEST.state().score),[1,0]);
  await page.waitForFunction(()=>window.TRIBUN_NATIVE_STREAM_TEST.presentation().stale);
  response=packet(22,[1,0]);
  await page.waitForFunction(()=>window.TRIBUN_NATIVE_STREAM_TEST.state()?.sequence===22);
  await page.waitForFunction(()=>!document.querySelector('#sendTactics').disabled);
  response=packet(23,[2,0],true);
  await page.waitForFunction(()=>window.TRIBUN_NATIVE_STREAM_TEST.state()?.phase==='finished');
  assert.deepEqual(await page.evaluate(()=>window.TRIBUN_NATIVE_STREAM_TEST.state().score),[2,0]);
  assert.equal(await page.locator('#sendTactics').isDisabled(),true);
  assert.equal(commands,0);assert.ok(requests>=4);assert.deepEqual(errors,[]);
  console.log('League pilot WebGL synthetic HTTP contract passed; no live backend or official result mutation.');
 }finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
