'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Brain=require('../player-brain.js'),{Match}=require('../football-sim.js');
const attacker=(changes={})=>({
 role:'ATT',position:'LW',x:0,z:-15,face:0,energy:1,
 passing:80,vision:80,composure:80,dribbling:90,agility:90,
 acceleration:92,pace:91,strength:66,balance:78,footPreference:'right',...changes
});
const option=(point={x:8,z:0},changes={})=>({
 kind:'pass',point,risk:.42,arrivalRisk:.55,space:5,score:8,...changes
});
test('vision and passing skill favor a safe progressive/through read, not a bad lane',()=>{
 const player=attacker({role:'MID',position:'AM',passing:94,vision:96,composure:90});
 const low=attacker({role:'MID',position:'AM',passing:64,vision:63,composure:62});
 const input={kind:'through',forwardGain:17,pressure:5,risk:.12,arrivalRisk:.15,space:8};
 assert(Brain.passBias(player,input)>Brain.passBias(low,input)+3);
 assert(Brain.passBias(player,{...input,risk:.9,arrivalRisk:.9})<Brain.passBias(player,input));
 assert.equal(Brain.canThread(player,{aligned:true,forwardGain:17,pressure:6}),true);
 assert.equal(Brain.canThread(player,{aligned:false,forwardGain:17,pressure:6}),false);
 assert.equal(Brain.canThread(low,{aligned:true,forwardGain:17,pressure:6}),false);
});
test('skilled inverted winger prefers an open inside-carry lane',()=>{
 const p=attacker();
 const cut={x:5,z:-11},outside={x:5,z:-19};
 assert(Brain.carryBias(p,{forwardGain:5,clearance:3.5,point:cut})>
  Brain.carryBias(p,{forwardGain:5,clearance:3.5,point:outside}));
 assert(Brain.carryBias(p,{forwardGain:5,clearance:3.5,point:cut})>
  Brain.carryBias(attacker({dribbling:61,agility:62,acceleration:61}),{forwardGain:5,clearance:3.5,point:cut})+2);
 assert(Brain.carryBias(p,{forwardGain:5,clearance:.1,point:cut})<
  Brain.carryBias(p,{forwardGain:5,clearance:3.5,point:cut}));
});
test('direct carry requires space and does not displace a good forward pass',()=>{
 const p=attacker(),carry={kind:'carry',point:{x:5,z:-13},clearance:3.2};
 const context={forward:1,pressure:3.5,carryTime:.4,goalDistance:40};
 assert.equal(Brain.shouldDrive(p,carry,option({x:3,z:0},{risk:.65}),context),true);
 assert.equal(Brain.shouldDrive(p,carry,option({x:16,z:0},{risk:.14,arrivalRisk:.2,score:16}),context),false);
 assert.equal(Brain.shouldDrive(p,{...carry,clearance:.4},null,context),false);
 assert.equal(Brain.shouldDrive({...p,energy:.2},carry,null,context),false);
 assert.equal(Brain.shouldDrive(attacker({role:'GK',position:'GK'}),carry,null,context),false);
});
test('feints depend on dribbling, agility and defender reading',()=>{
 const defender={tackling:80,composure:84},p=attacker();
 assert.equal(Brain.canFeint(p,defender,{pressure:2.2}),true);
 assert.equal(Brain.canFeint(attacker({agility:57}),defender,{pressure:2.2}),false);
 assert.equal(Brain.canFeint({...p,energy:.2},defender,{pressure:2.2}),false);
 assert.equal(Brain.canFeint(p,defender,{pressure:6}),false);
});
test('target forward shields with back to goal, but plays a clear pass first',()=>{
 const target=attacker({position:'ST',archetype:'targetForward',z:0,face:Math.PI,
  strength:96,balance:92,composure:88,dribbling:68,agility:59});
 const defender={x:2,z:0};
 assert.equal(Brain.canHoldUp(target,defender,option({x:1,z:0},{risk:.6}),{pressure:2,forward:1}),true);
 assert.equal(Brain.canHoldUp({...target,face:0},defender,null,{pressure:2,forward:1}),false);
 assert.equal(Brain.canHoldUp({...target,strength:65},defender,null,{pressure:2,forward:1}),false);
 assert.equal(Brain.canHoldUp(target,defender,option({x:14,z:0},{risk:.12,arrivalRisk:.12,score:19}),{pressure:2,forward:1}),false);
 assert.equal(Brain.canHoldUp({...target,x:0,face:0},defender,null,{pressure:2,forward:-1}),false);
});
function preparedMatch(){
 const m=new Match({seed:21,individualAI:true}),p=m.players[1];
 m.restart=null;m.goalPause=null;m.kick=null;m.owner=p;m.time=12;
 m.targets=new Map();m.passOptions=()=>[];m.crossingOption=()=>null;
 m.shotWindow=()=>({distance:50,quality:0,open:0,execution:0,pressure:0,point:{x:52,z:0}});
 m.clearFinish=()=>false;m.giveGoLink=()=>null;
 Object.assign(p,{role:'ATT',position:'ST',x:0,z:0,vx:0,vz:0,face:0,energy:1,
  dribbling:95,agility:95,acceleration:95,pace:94,carryTime:.45,escapeUntil:0,feintCooldown:0});
 return {m,p};
}
test('match choose actually produces a skill-driven vertical drive',()=>{
 const {m,p}=preparedMatch();
 m.rivals=()=>[{id:77,team:1,x:3.6,z:0,vx:0,vz:0,tackling:80,composure:80}];
 m.carryOption=()=>({kind:'carry',point:{x:5,z:1},clearance:3.5,score:9});
 const first=m.choose(p);assert.equal(first.kind,'carry');assert.equal(first.signatureDrive,true);
 const seed=m.seed;assert.deepEqual(m.choose(p),first);assert.equal(m.seed,seed);
});
test('match choose actually protects the ball with a strong back-to-goal striker',()=>{
 const {m,p}=preparedMatch();
 Object.assign(p,{archetype:'targetForward',face:Math.PI,
  strength:96,balance:92,composure:90,dribbling:68,agility:59});
 m.rivals=()=>[{id:77,team:1,x:1.9,z:0,vx:0,vz:0,tackling:83,composure:80}];
 m.carryOption=()=>({kind:'carry',point:{x:3,z:0},clearance:.6,score:2});
 const choice=m.choose(p);assert.equal(choice.kind,'carry');assert.equal(choice.holdUp,true);
 assert.equal(choice.shield,true);
});
test('short-passing playmaker may see a real aligned through run, not an unaligned one',()=>{
 const {m,p}=preparedMatch(),q=m.players[2];
 Object.assign(p,{role:'MID',position:'AM',x:0,z:0,face:0,vision:96,passing:95,composure:89});
 Object.assign(q,{role:'ATT',position:'ST',x:11,z:0,vx:1,vz:0,pace:87});
 m.t[0].passing='short';m.ball={x:0,y:.11,z:0,vx:0,vy:0,vz:0};
 m.team=()=>[p,q];m.observedLine=()=>13;
 m.receiverPoint=()=>({x:q.x,z:q.z});m.receptionSafety=()=>({pressure:10,risk:.1});
 m.laneRisk=()=>.1;m.passTime=()=>.85;m.threat=()=>0;m.matchContext=()=>({urgency:0,protect:false});
 m.plannedRun=()=>({x:17,z:0});m.rivals=()=>[{x:14,z:17,vx:0,vz:0}];
 // Restore the real pass-option algorithm, which preparedMatch replaced for other scenarios.
 m.passOptions=Match.prototype.passOptions;
 assert(m.passOptions(p).some(o=>o.kind==='through'&&o.q===q&&o.plannedRun));
 m.plannedRun=()=>null;
 assert(!m.passOptions(p).some(o=>o.kind==='through'),'short passing requires an aligned observed run');
 p.vision=68;p.passing=70;m.plannedRun=()=>({x:17,z:0});
 assert(!m.passOptions(p).some(o=>o.kind==='through'),'a low-vision player cannot receive the creative exception');
});

test('legacy generated-roster fixtures retain deterministic behavior until individually enabled',()=>{
 const original=new Match({seed:9}),explicitOff=new Match({seed:9,individualAI:false});
 assert.equal(original.playerBrainEnabled(original.players[0]),false);
 assert.equal(explicitOff.playerBrainEnabled(explicitOff.players[0]),false);
 for(let frame=0;frame<180;frame++){
  original.step(1/60);explicitOff.step(1/60);
 }
 assert.deepEqual(original.ball,explicitOff.ball);
 assert.deepEqual(original.events,explicitOff.events);
 assert.deepEqual(original.score,explicitOff.score);
 const opted=new Match({seed:9,individualAI:true});
 assert.equal(opted.playerBrainEnabled(opted.players[0]),true);
 const supplied=require('../player-model.js').demoTeam(0,'4-3-3'),custom=new Match({seed:9,players:supplied});
 assert.equal(custom.playerBrainEnabled(custom.players[0]),true);
 assert.equal(custom.playerBrainEnabled(custom.players[11]),false);
});
