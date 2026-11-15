'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Rig=require('../humanoid-rig.js');
const Scenarios=require('../animation-scenarios.js');
const length=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
function trajectory(mode,frames=600){
 const state=Scenarios.create(mode),contacts=[0,0],plants=[0,0],slips=[0,0],lifts=[0,0];
 let before=null;
 for(let tick=0;tick<frames;tick++){
  Scenarios.sample(state,tick/60,Rig);
  const pose=Rig.update(state.p,1/60);
  for(let side=0;side<2;side++){
   const leg=pose.legs[side],prior=before?.legs[side];
   assert(Math.abs(length(leg.hip,leg.knee)-.5)<1e-5,'thigh length stable');
   assert(Math.abs(length(leg.knee,leg.ankle)-.5)<1e-5,'shin length stable');
   assert(Number.isFinite(leg.footLift));
   lifts[side]=Math.max(lifts[side],leg.footLift);
   if(leg.stance){
    contacts[side]++;
    assert(Math.abs(leg.ankle[1]-.13)<1e-4,'foot sits on ground during contact');
    if(!prior||!prior.stance)plants[side]++;
    else slips[side]=Math.max(slips[side],length(leg.ankle,prior.ankle));
   }
  }
  before=pose;
 }
 return {contacts,plants,slips,lifts};
}
test('sprinting visibly alternates support feet rather than dragging one leg',()=>{
 const result=trajectory('sprint');
 for(let i=0;i<2;i++){
  assert(result.plants[i]>=10,'each foot must land repeatedly: '+JSON.stringify(result));
  assert(result.contacts[i]>=45,'both legs must support the ground: '+JSON.stringify(result));
  assert(result.lifts[i]>.10,'each foot must also leave the ground');
  assert(result.slips[i]<.001,'locked foot slides: '+JSON.stringify(result));
 }
 assert(Math.abs(result.plants[0]-result.plants[1])<=4,'high speed gait must be balanced');
});
test('foot contact locking remains stable at walk, jog, turn and shoot',()=>{
 for(const mode of ['walk','jog','run','turn','shoot']){
  const result=trajectory(mode,300);
  assert(result.slips.every(v=>v<.001),'planted ankle slipped in '+mode);
  if(['walk','jog','run','turn'].includes(mode))assert(result.plants.every(n=>n>=4),'missing support in '+mode);
 }
});
