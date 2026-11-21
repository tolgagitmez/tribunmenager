'use strict';
const {Match}=require('../football-sim');
const tactics={playstyle:'wing',crossing:'early',tempo:90,mentality:'attacking',aggression:80,press:76,passing:'direct'};
const max=Number(process.env.SEED_MAX||60);
let firstHome=0,firstAway=0;
for(let seed=1;seed<=max;seed++){
 const match=new Match({seed,tactics,awayTactics:tactics,rules:{periodSeconds:45,halftimeSeconds:0,addedTime:false}});
 match.managerKickTeams=new Set([0,1]);
 const offers=[];
 for(let tick=1;tick<=6000&&!match.done;tick++){
  match.step(1/60);
  if(match.pendingManagerKick){
   const offer=match.pendingManagerKick;
   offers.push({tick,team:offer.team,kind:offer.kind,period:match.period,id:offer.id});
   if(!match.resolveManagerKick(offer.id,null))throw Error('Failed to delegate AI kick at '+seed+'/'+tick);
   // A different first or second offer cannot satisfy the original worker test.
   if(offers.length>=2||offers.length===1&&
      !(offer.team===0&&offer.kind==='free-kick'&&offer.period===1&&offer.tick<=2400))break;
  }
  if(!offers.length&&tick>2400)break;
  if(offers.length===1&&tick-offers[0].tick>2700)break;
 }
 if(offers[0]?.team===0&&offers[0]?.kind==='free-kick'&&offers[0]?.period===1&&offers[0]?.tick<=2400)firstHome++;
 if(offers[1]?.team===1&&offers[1]?.kind==='free-kick'&&offers[1]?.period===2)firstAway++;
 const strict=offers[0]?.team===0&&offers[0]?.kind==='free-kick'&&offers[0]?.period===1&&offers[0]?.tick<=2400&&
  offers[1]?.team===1&&offers[1]?.kind==='free-kick'&&offers[1]?.period===2&&offers[1]?.tick-offers[0].tick<=2700;
 console.log('SEED_SCAN '+JSON.stringify({seed,offers:offers.slice(0,6),strict,done:match.done,seconds:Number(match.time.toFixed(3))}));
 if(strict){console.log('FOUND_LIVE_MATCH_SEED '+seed);process.exit(0);}
}
console.log('NO_STRICT_SEED',{max,firstHome,firstAway});
process.exitCode=1;
