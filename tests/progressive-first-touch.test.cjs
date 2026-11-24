'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Match}=require('../football-sim');
for(const team of [0,1]){
 function fixture(){
  const m=new Match({seed:42,individualAI:true}),p=m.players[team*11+5],side=m.direction(team);
  Object.assign(p,{role:'MID',position:'CM',x:10*side,z:0,face:team===0?1.9:Math.PI-1.9,dribbling:85,composure:85,agility:82,energy:1});
  m.rivals=()=>[{x:10*side,z:10,vx:0,vz:0}];return {m,p,side,outgoing:team===0?Math.PI:0};
 }
 test('an equally safe forward first touch replaces a backward preference, team '+team,()=>{
  const {m,p,side,outgoing}=fixture(),ball={...m.ball},seed=m.seed;
  const result=m.controlOption(p,p,outgoing);
  assert(result.progressive);assert((result.x-p.x)*side>1.9);
  assert.deepEqual(m.ball,ball);assert.equal(m.seed,seed);
 });
 test('progressive first touch is suppressed by nearby pressure, closed forward route, fatigue, protected midfield role or disabled AI, team '+team,()=>{
  for(const change of ['pressure','path','fatigue','anchor','disabled']){
   const {m,p,side,outgoing}=fixture();
   if(change==='pressure')m.rivals=()=>[{x:p.x,z:3,vx:0,vz:0}];
   if(change==='path')m.rivals=()=>[{x:p.x+1.5*side,z:0,vx:0,vz:0}];
   if(change==='fatigue')p.energy=.3;
   if(change==='anchor')p.position='DM';
   if(change==='disabled')m.cfg.individualAI=false;
   assert.notEqual(m.controlOption(p,p,outgoing).progressive,true,change);
  }
 });
}
