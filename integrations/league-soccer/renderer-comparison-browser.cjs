'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),{once}=require('node:events'),{chromium}=require('playwright');
const {createServer}=require('../../tools/serve-character-viewer.cjs');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
(async()=>{
 const out=path.resolve(process.argv[2]),file=path.join(out,'comparison.json'),report=JSON.parse(fs.readFileSync(file,'utf8')),trace=path.join(out,'match.ndjson'),manifest=trace+'.fixture.json';
 assert.equal(report.status,'native-captured');assert.equal(report.pairs.length,3);
 assert.equal(hash(trace),report.traceSha256);assert.equal(hash(manifest),report.manifestSha256);
 const server=createServer();server.listen(0,'127.0.0.1');await once(server,'listening');
 let browser;
 try{
  browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port+'/integrations/league-soccer/replay.html');
  await page.locator('#file').setInputFiles(trace);
  await page.waitForFunction(()=>window.TRIBUN_NATIVE_REPLAY_TEST.state()?.players===22);
  await page.locator('#manifest').setInputFiles(manifest);
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Kadro eşleştirildi'));
  await page.waitForFunction(()=>window.TRIBUN_NATIVE_REPLAY_TEST.modelReady(),{},{timeout:30000});
  assert.equal(await page.evaluate(()=>window.TRIBUN_NATIVE_REPLAY_TEST.webgl()),true);
  await page.locator('#betaPresentation').click();
  await page.waitForFunction(()=>window.TRIBUN_NATIVE_REPLAY_TEST.clipStatus()==='ready',{},{timeout:30000});
  await page.locator('#quality').selectOption('quality');
  for(const [i,p] of report.pairs.entries()){
   assert.equal(hash(path.join(out,p.nativeImage)),p.sha256);
   await page.locator('#seek').evaluate((el,t)=>{el.value=String(t);el.dispatchEvent(new Event('input'));},p.elapsedMs);
   await page.waitForFunction(t=>Math.abs(window.TRIBUN_NATIVE_REPLAY_TEST.state()?.elapsedMs-t)<=1,p.elapsedMs);
   const state=await page.evaluate(()=>window.TRIBUN_NATIVE_REPLAY_TEST.state());
   assert.deepEqual(state.score,p.score);assert.equal(state.players,22);
   await page.waitForTimeout(450);
   const name='browser-'+(i+1)+'.png';await page.locator('#pitch').screenshot({path:path.join(out,name)});
   p.browserImage=name;p.browserSha256=hash(path.join(out,name));p.browserCanvas=await page.evaluate(()=>window.TRIBUN_NATIVE_REPLAY_TEST.performance().scene.canvas);
  }
  assert.deepEqual(errors,[]);report.status='manual-visual-review-required';
  fs.writeFileSync(file,JSON.stringify(report,null,2)+'\n');
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  fs.writeFileSync(path.join(out,'compare.html'),'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>League-Soccer renderer comparison</title><style>body{font:16px system-ui;background:#101827;color:#eff4fa;margin:24px}section{margin:24px 0} .pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}img{width:100%;height:auto}figure{margin:0}figcaption{padding:8px 0}@media(max-width:700px){.pair{grid-template-columns:1fr}}</style><h1>League-Soccer: OpenGL / WebGL</h1><p>Same recorded match; approximate time pairing, different camera/HUD/resolution. Not a performance benchmark. No visual winner asserted.</p>'+report.pairs.map(p=>'<section><h2>'+Math.floor(p.matchMs/60000)+'′ · '+esc(p.score.join(' : '))+'</h2><p>Observation gap: '+p.observationGapMs+' ms (not render synchronization).</p><div class="pair"><figure><img src="'+esc(p.nativeImage)+'"><figcaption>Original OpenGL</figcaption></figure><figure><img src="'+esc(p.browserImage)+'"><figcaption>Tribün Manager WebGL</figcaption></figure></div></section>').join(''));
  console.log('Comparison screenshots and local gallery ready for manual review.');
 }finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
