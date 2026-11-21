'use strict';
// Discover an ordinary live match fixture with two independent, manager-controlled
// decisions under the current motor. The original seed 6 was invalidated by the
// isolated safe-forward-before-hold change; do not fake an event.
const {Match}=require('../football-sim');
const Rig=require('../humanoid-rig');
const tactics={playstyle:'wing',crossing:'early',tempo:90,mentality:'attacking',aggression:80,press:76,passing:'direct'};
const maxSeed=Number(process.env.PROBE_MAX_SEED)||36;
const candidate=[];
for(let seed=1;seed<=maxSeed;seed++){
 const match=new Match({seed,tactics,awayTactics:tactics,rules:{periodSeconds:45,halftimeSeconds:0,addedTime:false}},Rig);
 match.managerKickTeams=new Set([0,1]);match.drain();
 const offers=[];
 for(let i=0;i<9300&&!match.done;i++){
  match.step(1/60);
  if(match.pendingManagerKick){
   const offer=match.pendingManagerKick;
   offers.push({team:offer.team,kind:offer.kind,period:match.period,at:Number(match.time.toFixed(2)),id:offer.id});
   if(!match.resolveManagerKick(offer.id,null))throw Error('Cannot delegate offered kick');
  }
  if(i%120===0)match.drain();
 }
 const home=offers.find(o=>o.team===0&&o.kind==='free-kick'&&o.period===1);
 const away=home&&offers.find(o=>o.team===1&&o.kind==='free-kick'&&o.period===2&&o.at>home.at);
 const anyHome=offers.find(o=>o.team===0),anyAway=anyHome&&offers.find(o=>o.team===1&&o.at>anyHome.at);
 const result={seed,done:match.done,time:match.time,score:match.score,offers,strict:!!away&&!!home,loose:!!anyAway};
 candidate.push(result);
 process.stdout.write('FIXTURE '+JSON.stringify(result)+'\n');
 if(result.strict){process.stdout.write('FOUND_STRICT '+JSON.stringify(result)+'\n');process.exit(0);}
}
const loose=candidate.find(x=>x.loose);
if(loose){console.log('FOUND_LOOSE '+JSON.stringify(loose));process.exit(0);}
console.log('NO_FIXTURE_IN_RANGE '+maxSeed);
process.exitCode=1;
