'use strict';
// Reproducible discovery of REAL manager-kick windows on the current engine.
// No forced restarts, mocked goals, player teleports, or altered RNG.
const {Match}=require('../football-sim.js'),Rig=require('../humanoid-rig.js');
const tactics={playstyle:'wing',crossing:'early',tempo:90,mentality:'attacking',aggression:80,press:76,passing:'direct'};
const seeds=(process.env.OFFER_SEEDS||'3,5,6,9,12,18,20,24').split(',').map(Number);
for(const seed of seeds){
 const m=new Match({seed,tactics,awayTactics:tactics,
   rules:{periodSeconds:45,halftimeSeconds:0,addedTime:false}},Rig);
 m.managerKickTeams=new Set([0,1]);
 let found=null;
 for(let tick=0;tick<5500&&!m.done;tick++){
  m.step(1/60);
  if(m.pendingManagerKick){
   const q=m.pendingManagerKick;
   found={seed,tick:tick+1,time:m.time,period:m.period,team:q.team,kind:q.kind,id:q.id,
    angle:q.angle,power:q.power};
   break;
  }
 }
 console.log('LIVE_OFFER_PROBE '+JSON.stringify({seed,offer:found,done:m.done,time:m.time}));
}
