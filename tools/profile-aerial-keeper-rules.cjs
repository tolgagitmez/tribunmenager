#!/usr/bin/env node
'use strict';
/* Passive match-level audit: same 60 Hz physical engine and normal rules. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {Match}=require('../football-sim.js');
const seeds=[11,21,42,77];
const scenarios=[];
const sum={seeds:seeds.length,shots:0,onTarget:0,headers:0,chestControls:0,aerialLongBalls:0,
 aerialDuels:0,aerialSecondBalls:0,secondBallContests:0,keeperReachableShots:0,
 keeperReachableCatches:0,keeperReachableParries:0,penaltyRetakes:0};
for(const seed of seeds){
 const m=new Match({seed,matchMinutes:5,
  tactics:{playstyle:'wing',tempo:82,press:65,mentality:'attacking',crossing:'early'},
  awayTactics:{playstyle:'direct',tempo:75,press:58,mentality:'attacking',passing:'direct'}});
 m.managerKickTeams=new Set();let ticks=0;
 while(!m.done&&ticks<50000){m.step(1/60);ticks++;}
 assert(m.done,'Natural fixture did not terminate: '+seed);
 const keeper=m.keeperSummary(),t=m.telemetry;
 const item={seed,ticks,score:m.score,shots:m.shots,onTarget:m.onTarget,
  aerial:{headers:t.aerialHeaders||0,longBalls:t.aerialLongBalls||0,chests:t.chestControls||0,
   duels:t.aerialDuels||0,secondBalls:t.aerialSecondBalls||0,contests:t.secondBallContests||0},
  goalkeeper:keeper,penalty:{retakes:t.penaltyRetakes||0,earlyEntrants:t.penaltyEarlyEntrants||0,
   keeperLineOffences:t.penaltyKeeperLineOffences||0}};
 scenarios.push(item);sum.shots+=m.shots[0]+m.shots[1];sum.onTarget+=m.onTarget[0]+m.onTarget[1];
 for(const [key,value]of [['headers',item.aerial.headers],['chestControls',item.aerial.chests],
  ['aerialLongBalls',item.aerial.longBalls],['aerialDuels',item.aerial.duels],
  ['aerialSecondBalls',item.aerial.secondBalls],['secondBallContests',item.aerial.contests],
  ['keeperReachableShots',keeper.reachableShots],['keeperReachableCatches',keeper.catches],
  ['keeperReachableParries',keeper.parries],['penaltyRetakes',item.penalty.retakes]])sum[key]+=value;
 process.stderr.write('NATURAL_MATCH '+JSON.stringify(item)+'\n');
}
sum.keeperReachableCatchRate=sum.keeperReachableShots?sum.keeperReachableCatches/sum.keeperReachableShots:null;
sum.keeperReachableParryRate=sum.keeperReachableShots?sum.keeperReachableParries/sum.keeperReachableShots:null;
const source=fs.readFileSync(path.join(__dirname,'../football-sim.js'));
const report={engineSHA256:crypto.createHash('sha256').update(source).digest('hex'),
 method:'Four ordinary full 5-minute matches with no injected balls or score changes. Only actual keeper-reachable attempts enter catch/parry denominator. No conclusions on season-wide balance.',summary:sum,scenarios};
const filename=path.join(__dirname,'../docs/validation/aerial-keeper-rules-current.json');
fs.mkdirSync(path.dirname(filename),{recursive:true});fs.writeFileSync(filename,JSON.stringify(report,null,2)+'\n');
console.log('AERIAL_KEEPER_AUDIT '+JSON.stringify(sum));
