'use strict';
/* Visual smoke test for the *existing WebGL renderer*, not a judgment of
   anatomical realism. Run with Playwright Chromium + pngjs installed.
   Captures reproducible evidence in dist/character-visual/. */
const {chromium}=require('playwright');
const {PNG}=require('pngjs');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');

const output=path.resolve('dist/character-visual'),script=path.resolve('player-studio.html');
function metrics(buffer){
 const data=PNG.sync.read(buffer);
 let count=0,reds=0,greens=0,blues=0,nontransparent=0;
 const unique=new Set();
 for(let i=0;i<data.data.length;i+=4*13){
  const r=data.data[i],g=data.data[i+1],b=data.data[i+2],a=data.data[i+3];
  if(a>0)nontransparent++;
  reds+=r;greens+=g;blues+=b;count++;
  unique.add((r>>3)*1024+(g>>3)*32+(b>>3));
 }
 return {width:data.width,height:data.height,colors:unique.size,opaqueRatio:nontransparent/count,avgRGB:[reds/count,greens/count,blues/count]};
}
function imageDifference(a,b){
 const aa=PNG.sync.read(a),bb=PNG.sync.read(b);
 assert.equal(aa.width,bb.width);assert.equal(aa.height,bb.height);
 let n=0,delta=0;
 for(let i=0;i<aa.data.length;i+=4*11){
  delta+=Math.abs(aa.data[i]-bb.data[i])+Math.abs(aa.data[i+1]-bb.data[i+1])+Math.abs(aa.data[i+2]-bb.data[i+2]);n++;
 }
 return delta/n/3;
}
async function main(){
 fs.mkdirSync(output,{recursive:true});
 const errors=[],browser=await chromium.launch({
  headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox']
 });
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1024},deviceScaleFactor:1});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file://'+script,{waitUntil:'load'});
  await page.waitForFunction(()=>{
   const canvas=document.getElementById('playerCanvas');
   return Boolean(window.TribunPlayerStudio&&window.TribunPlayerAssets&&canvas&&canvas.width>=200&&canvas.height>=200);
  },null,{timeout:30000});
  const screen=await page.evaluate(()=>{
   const e=document.getElementById('errorMessage');
   return {hidden:e.hidden,message:e.textContent,assets:window.TribunPlayerAssets.version,
     webgl:Boolean(document.getElementById('playerCanvas').getContext('webgl'))};
  });
  assert(screen.hidden,'Player studio reported an error: '+screen.message);
  assert(screen.webgl,'Player studio has no WebGL context');
  const captures={};
  for(const mode of ['idle','walk','run','sprint','turn','pass','shoot','dive-left']){
   await page.selectOption('#pose',mode);
   // Contact actions expire after ~0.6 s; capture them before recovery to idle.
   const previewDelay={pass:220,shoot:275,'dive-left':300};
   await page.waitForTimeout(previewDelay[mode]??(mode==='idle'?300:700));
   const state=await page.evaluate(()=>window.TribunPlayerStudio.getState());
   assert.equal(state.mode,mode);
   const png=await page.locator('#playerCanvas').screenshot({path:path.join(output,mode+'.png')});
   const stats=metrics(png);
   assert(stats.width>200&&stats.height>200);
   assert(stats.colors>30,mode+' canvas image is nearly blank');
   captures[mode]={...stats,image:mode+'.png'};
  }
  const idle=fs.readFileSync(path.join(output,'idle.png'));
  for(const mode of ['sprint','shoot','dive-left']){
   const buffer=fs.readFileSync(path.join(output,mode+'.png'));
   const change=imageDifference(idle,buffer);
   captures[mode].differenceFromIdle=change;
   assert(change>2,mode+' does not visibly change the canvas from idle');
  }
  assert.equal(errors.length,0,'Browser script errors: '+errors.join('; '));
  const report={browser:'Playwright Chromium (SwiftShader)',screen,captures,errors};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log('character visual smoke: '+JSON.stringify({webgl:screen.webgl,modes:Object.keys(captures),errors:errors.length}));
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
