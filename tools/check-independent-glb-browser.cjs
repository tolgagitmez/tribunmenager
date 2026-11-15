'use strict';
const {chromium}=require('playwright');
const {PNG}=require('pngjs');
const fs=require('node:fs'),path=require('node:path');
const assert=require('node:assert/strict');
const {createServer}=require('./serve-character-viewer.cjs');
const output=path.resolve('dist/character-glb-viewer');
function diff(a,b){
 const aa=PNG.sync.read(a),bb=PNG.sync.read(b);
 assert.equal(aa.width,bb.width);assert.equal(aa.height,bb.height);
 let n=0,sum=0,colors=new Set();
 for(let i=0;i<aa.data.length;i+=4*13){
  sum+=Math.abs(aa.data[i]-bb.data[i])+Math.abs(aa.data[i+1]-bb.data[i+1])+Math.abs(aa.data[i+2]-bb.data[i+2]);
  colors.add((aa.data[i]>>3)*1024+(aa.data[i+1]>>3)*32+(aa.data[i+2]>>3));n++;
 }
 return {difference:sum/(3*n),colors:colors.size};
}
async function main(){
 fs.mkdirSync(output,{recursive:true});
 const server=createServer();
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox']});
 const issues=[],report={};
 try{
  const page=await browser.newPage({viewport:{width:1320,height:900},deviceScaleFactor:1});
  page.on('pageerror',e=>issues.push(e.message));
  page.on('console',msg=>{if(msg.type()==='error')issues.push(msg.text());});
  await page.goto('http://127.0.0.1:'+server.address().port+'/character-viewer.html',{waitUntil:'load'});
  await page.waitForFunction(()=>window.TribunGLBViewer?.ready,null,{timeout:45000});
  const stats=await page.evaluate(()=>window.TribunGLBViewer.stats());
  assert.equal(stats.clips.length,12);assert(stats.hasBone,'pelvis joint missing');
  report.stats=stats;
  const captures={};
  for(const [name,t] of [['idle',.15],['walk',.50],['sprint',.50],['shoot',.26],['dive-left',.27],['run-pass',1.05],['run-shoot',1.13]]){
   const sample=await page.evaluate(([clip,time])=>{
    const viewer=window.TribunGLBViewer;
    return {selected:viewer.selectClip(clip),sampled:viewer.sample(time),feet:viewer.getFrame()};
   },[name,t]);
   assert(sample.selected&&sample.sampled);
   assert(sample.feet.every(point=>point.length===3&&point.every(Number.isFinite)));
   await page.waitForTimeout(120);
   const shot=await page.locator('#stage canvas').screenshot({path:path.join(output,name+'.png')});
   const png=PNG.sync.read(shot);
   assert(png.width>=450&&png.height>=400);
   captures[name]={bytes:shot.byteLength,feet:sample.feet};
  }
  const idle=fs.readFileSync(path.join(output,'idle.png'));
  for(const name of ['walk','sprint','shoot','dive-left','run-pass','run-shoot']){
   const data=fs.readFileSync(path.join(output,name+'.png'));
   const {difference,colors}=diff(idle,data);captures[name].differenceFromIdle=difference;
   assert(colors>25,'GLB viewer screenshot has no rendered scene');
   assert(difference>.4,name+' identical to idle despite time change: '+difference);
  }
  assert.deepEqual(issues,[],'independent glTF player console errors');
  report.captures=captures;report.errors=issues;
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log('independent GLB viewer: '+JSON.stringify({clips:stats.clips.length,modes:Object.keys(captures),errors:issues.length}));
 }finally{
  await browser.close();await new Promise(resolve=>server.close(resolve));
 }
}
main().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
