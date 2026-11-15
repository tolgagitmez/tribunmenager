'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Blender=require('../character-blend-controller.js');
const Assets=require('../assets/player/player-model-data.js');
const {bakeClip,CLIPS}=require('../tools/character-animation-baker.cjs');
const {buildGLB,PARENT}=require('../tools/export-character-glb.cjs');
const distance=(a,b)=>Math.hypot(...a.map((x,i)=>x-b[i]));

function action(){
 return {weight:0,enabled:false,stopped:false,
  reset(){this.stopped=false;return this;},
  play(){this.stopped=false;return this;},
  stop(){this.stopped=true;this.weight=0;return this;},
  setEffectiveTimeScale(){return this;},
  setEffectiveWeight(w){this.weight=w;return this;},
  getEffectiveWeight(){return this.weight;}
 };
}
test('crossfader eases both animation weights and prevents character-root teleportation',()=>{
 const clips=['run','shoot','pass'].map((name,i)=>({
  name,duration:2,tracks:[{name:'pelvis.position',values:[i===0?1:0,1,0]}]
 }));
 const actions=new Map(),mixer={t:0,clipAction:clip=>{
  if(!actions.has(clip.name))actions.set(clip.name,action());
  return actions.get(clip.name);
 },update:dt=>{mixer.t+=dt;},setTime:t=>{mixer.t=t;}};
 const model={position:{x:0,y:0,z:0}},pelvis={position:{x:3,y:1,z:.4}};
 const ctl=Blender.create({mixer,clips,model,pelvis,fadeSeconds:.28});
 assert(ctl.select('run',{immediate:true}));
 assert(ctl.select('shoot'));
 let info=ctl.info();assert(info.transition);assert.equal(info.from,'run');assert.equal(info.to,'shoot');
 ctl.update(.14);info=ctl.info();
 assert(Math.abs(info.fromWeight-.5)<1e-6);
 assert(Math.abs(info.toWeight-.5)<1e-6);
 assert(Math.abs(model.position.x-1.5)<1e-5);
 ctl.update(.14);info=ctl.info();
 assert.equal(info.transition,false);assert.equal(info.toWeight,1);
 assert(Math.abs(model.position.x-3)<1e-5);
 assert(actions.get('run').stopped);
 assert(ctl.select('pass'));ctl.update(.10);
 assert(ctl.info().transition);
 assert(ctl.seek(.25));
 assert.equal(ctl.info().transition,false);
 assert.equal(actions.get('pass').weight,1);
 assert(Math.abs(model.position.x-6)<1e-4);
 assert.equal(mixer.t,.25);
 assert.equal(ctl.select('nonexistent'),false);
 ctl.reset();assert.equal(ctl.info().active,null);
});
test('walk, run and sprint loop clips wrap at the same pose with matched end velocity',()=>{
 const loops=CLIPS.filter(c=>c.loop);
 assert.deepEqual(loops.map(c=>c.name),['walk-loop','run-loop','sprint-loop']);
 const output=buildGLB({animations:true,fps:30,lod:2});
 const specs=output.json.animations.filter(c=>c.extras?.loopReady);
 assert.equal(specs.length,3);
 for(const definition of loops){
  const baked=bakeClip({...definition,parents:PARENT,fps:30});
  assert.equal(baked.loopReady,true);
  const n=baked.times.length;
  assert.equal(Math.round(baked.duration*30)+1,n);
  let maxSeamVelocityDiff=0,nonFlat=0;
  for(const ch of baked.channels){
   for(const [key,dim] of [['translation',3],['rotation',4]]){
    const values=ch[key];
    const first=Array.from(values.slice(0,dim)),second=Array.from(values.slice(dim,2*dim));
    const last=Array.from(values.slice((n-1)*dim,n*dim));
    const before=Array.from(values.slice((n-2)*dim,(n-1)*dim));
    assert(distance(first,last)<2e-6,definition.name+' pose seam not closed');
    const firstStep=second.map((v,i)=>v-first[i]),lastStep=last.map((v,i)=>v-before[i]);
    maxSeamVelocityDiff=Math.max(maxSeamVelocityDiff,distance(firstStep,lastStep));
    for(const v of values)assert(Number.isFinite(v));
    if(key==='rotation')for(let k=0;k<n;k++){
     const q=Array.from(values.slice(k*4,k*4+4));
     assert(Math.abs(Math.hypot(...q)-1)<2e-5,'not a unit quaternion');
     if(k){
      const prev=Array.from(values.slice((k-1)*4,k*4));
      assert(q.reduce((s,x,i)=>s+x*prev[i],0)>0,'loop quaternion must remain in same hemisphere');
     }
    }
   }
   const t=ch.translation,q=ch.rotation;
   nonFlat=Math.max(nonFlat,...Array.from(t,(v,i)=>Math.abs(v-t[i%3])),...Array.from(q,(v,i)=>Math.abs(v-q[i%4])));
  }
  assert(maxSeamVelocityDiff<.05,definition.name+' discontinuous gait seam: '+maxSeamVelocityDiff);
  assert(nonFlat>.015,definition.name+' cannot be a frozen pose');
  const pelvis=baked.channels[0].translation;
  let xMin=Infinity,xMax=-Infinity,zMin=Infinity,zMax=-Infinity;
  for(let i=0;i<n;i++){
   xMin=Math.min(xMin,pelvis[i*3]);xMax=Math.max(xMax,pelvis[i*3]);
   zMin=Math.min(zMin,pelvis[i*3+2]);zMax=Math.max(zMax,pelvis[i*3+2]);
  }
  assert(xMax-xMin<.004&&zMax-zMin<.004,'loop must be in place, not run in circles');
 }
});
