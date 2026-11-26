'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),P=require('./replay-performance.js');
test('pixel limits preserve aspect ratio without upscaling ordinary canvases',()=>{
 assert.deepEqual(P.fitPixels(300,200,450000),[300,200]);
 const [w,h]=P.fitPixels(2400,1350,450000);
 assert.ok(w*h<=450000);assert.ok(Math.abs(w/h-16/9)<.01);
 assert.ok(P.pixelBudget('performance',true)<P.pixelBudget('quality',true));
 assert.throws(()=>P.fitPixels(100,100,0));
});
test('paused and hidden frame gates preserve active redraw and dirty events',()=>{
 const s=P.create();assert.equal(s.shouldDraw(0,false,false),true);s.drawn();
 assert.equal(s.shouldDraw(16,false,false),false);assert.equal(s.shouldDraw(32,true,false),true);
 s.invalidate(50,1400);assert.equal(s.shouldDraw(60,false,true),false);
 assert.equal(s.shouldDraw(70,false,false),true);s.drawn();
 assert.equal(s.shouldDraw(1400,false,false),true);assert.equal(s.shouldDraw(1451,false,false),false);
 assert.equal(s.stats().skipped,3);
});
test('bounded CPU submission timing window',()=>{
 const s=P.create();for(let i=0;i<300;i++)s.record(i<180?100:10);
 assert.equal(s.stats().samples,120);assert.equal(s.stats().meanMs,10);assert.equal(s.stats().p95Ms,10);
});
