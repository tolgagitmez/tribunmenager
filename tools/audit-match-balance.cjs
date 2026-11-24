'use strict';
// Offline, fixed-step natural games. No injected events, extra AI calls, or
// goal targets. Reports are evidence, not a knob that changes match physics.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {Match}=require('../football-sim'),P=require('../player-model'),T=require('../tactics');
const root=path.resolve(__dirname,'..'),DT=1/60;
const scenarios=[
 {id:'equal-balanced',a:[80,'4-3-3','balanced'],b:[80,'4-3-3','balanced']},
 {id:'press-possession',a:[80,'4-3-3','press'],b:[80,'4-2-3-1','possession']},
 {id:'wide-counter',a:[80,'4-3-3','wide'],b:[80,'5-3-2','counter']},
 {id:'strong-weak',a:[90,'4-3-3','balanced'],b:[65,'4-4-2','balanced']},
 {id:'narrow-wide',a:[80,'4-2-3-1','possession'],b:[80,'4-2-3-1','wide']},
 {id:'underdog-counter',a:[68,'4-4-2','counter'],b:[86,'3-5-2','press']}
];
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
function fingerprints(){
 const files=['football-sim.js','player-model.js','player-model-profiles.json','player-perception.js','player-brain.js','team-intent.js','tactics.js','match-rules.js','referee-laws.js','pitch-laws.js','tools/audit-match-balance.cjs'];
 return Object.fromEntries(files.map(f=>[f,digest(fs.readFileSync(path.join(root,f)))]));
}
function roster([rating,formation],team){
 return P.demoTeam(team,formation).map(p=>({...p,rating,fitness:95,form:80,...Object.fromEntries(P.attributes.filter(k=>k!=='weakFoot').map(k=>[k,Math.max(1,Math.min(99,p[k]+rating-80))]))}));
}
function cases(seeds,shards=1,shard=0){
 assert(Number.isInteger(seeds)&&seeds>=1&&seeds<=100);
 assert(Number.isInteger(shards)&&shards>=1&&Number.isInteger(shard)&&shard>=0&&shard<shards);
 return scenarios.flatMap(s=>Array.from({length:seeds},(_,i)=>[false,true].map(swap=>({id:s.id+':'+(i+1)+':'+Number(swap),scenario:s.id,seed:1009+i*7919,swap,a:s.a,b:s.b})))).flat(1).filter((_,i)=>i%shards===shard);
}
function config(c){
 const home=c.swap?c.b:c.a,away=c.swap?c.a:c.b;
 const players=roster(home,0),awayPlayers=roster(away,1);
 const preset=id=>({...T.presets.find(p=>p.id===id).tactics});
 return {seed:c.seed,matchMinutes:5,formation:home[1],awayFormation:away[1],players,awayPlayers,starters:players.map(p=>p.id),awayStarters:awayPlayers.map(p=>p.id),tactics:preset(home[2]),awayTactics:preset(away[2]),individualAI:true};
}
function simulate(c){
 const m=new Match(config(c)),started=process.hrtime.bigint(),max=1200*60;
 let ticks=0,controlled=0,loose=0,dead=0,finalThird=[0,0],box=[0,0],lastOwner=null;
 const zones=[null,null],entries={finalThird:[0,0],box:[0,0]};
 while(!m.done&&ticks<max){
  const isDead=!!(m.restart||m.kick?.restartContext||m.goalPause||m.matchClock.phase==='halftime'||m.substitutionPause);
  if(isDead){dead++;zones.fill(null);lastOwner=null;}
  else if(m.owner){
   const team=m.owner.team,depth=m.ball.x*m.direction(team),central=Math.abs(m.ball.z)<20.16;
   const z={finalThird:depth>=52/3,box:depth>=35.5&&central};
   if(z.finalThird)finalThird[team]++;if(z.box)box[team]++;
   if(lastOwner!==team)zones.fill(null);
   for(const k of ['finalThird','box'])if(z[k]&&!zones[team]?.[k])entries[k][team]++;
   zones[team]=z;lastOwner=team;controlled++;
  }else{loose++;} // retain prior zone while a same-team pass is in flight
  m.step(DT);ticks++;
  assert(Number.isFinite(m.ball.x)&&Number.isFinite(m.ball.y)&&Number.isFinite(m.ball.z),c.id+' nonfinite ball');
  if(ticks%60===0)assert(m.players.every(p=>[p.x,p.z,p.vx,p.vz].every(Number.isFinite)),c.id+' nonfinite player');
 }
 assert(m.done,c.id+' failed to terminate');assert(['full-time','abandoned'].includes(m.finishReason)||m.period===2,c.id+' invalid finish');
 const pairs={goals:m.score,shots:m.shots,onTarget:m.onTarget,passes:m.passes,completed:m.completed,fouls:m.fouls,yellows:m.cards,reds:m.reds,xg:m.xg,possessionSeconds:m.possession,finalThirdSeconds:finalThird.map(n=>n*DT),boxSeconds:box.map(n=>n*DT),finalThirdEntries:entries.finalThird,boxEntries:entries.box};
 for(const [k,v] of Object.entries(pairs))assert(v.length===2&&v.every(n=>Number.isFinite(n)&&n>=0),c.id+' invalid '+k);
 const counters=Object.fromEntries(['offsides','turnovers','duels','crosses','throughBalls','abortedKicks','touchDeferrals','restarts','shotsAfterPasses','progressiveFirstTouches','openShotReleases'].map(k=>[k,m.telemetry[k]??0]));
 return {...c,finishReason:m.finishReason,period:m.period,ticks,elapsed:m.time,seconds:{controlled:controlled*DT,loose:loose*DT,dead:dead*DT},pairs,counters,wallSeconds:Number(process.hrtime.bigint()-started)/1e9,finalSeed:m.seed};
}
const sum=a=>a.reduce((x,y)=>x+y,0),round=n=>Math.round(n*1000)/1000,ratio=(a,b)=>b?round(100*a/b):null;
function summarize(rows){
 const n=rows.length;assert(n>0);
 const full=rows.filter(r=>r.finishReason==='full-time'),f=full.length;
 const totals=k=>sum(full.map(r=>sum(r.pairs[k]))),counter=k=>sum(full.map(r=>r.counters[k]));
 const mean=k=>f?round(totals(k)/f):null;
 return {matches:n,fullTime:f,otherFinishes:n-f,goalsPerMatch:mean('goals'),shotsPerMatch:mean('shots'),shotsOnTargetPerMatch:mean('onTarget'),passesPerMatch:mean('passes'),passAccuracyPct:ratio(totals('completed'),totals('passes')),onTargetPct:ratio(totals('onTarget'),totals('shots')),goalsPerShotPct:ratio(totals('goals'),totals('shots')),zeroShotMatchPct:ratio(full.filter(r=>sum(r.pairs.shots)===0).length,f),scorelessMatchPct:ratio(full.filter(r=>sum(r.pairs.goals)===0).length,f),foulsPerMatch:mean('fouls'),yellowsPerMatch:mean('yellows'),redsPerMatch:mean('reds'),offsidesPerMatch:f?round(counter('offsides')/f):null,finalThirdEntriesPerMatch:mean('finalThirdEntries'),boxEntriesPerMatch:mean('boxEntries'),xgPerMatch:mean('xg'),controlledPct:ratio(sum(full.map(r=>r.seconds.controlled)),sum(full.map(r=>r.ticks*DT))),homePossessionPct:ratio(sum(full.map(r=>r.pairs.possessionSeconds[0])),totals('possessionSeconds')),abortedKicksPerMatch:f?round(counter('abortedKicks')/f):null,
 sideA:{wins:full.filter(r=>r.pairs.goals[r.swap?1:0]>r.pairs.goals[r.swap?0:1]).length,draws:full.filter(r=>r.pairs.goals[0]===r.pairs.goals[1]).length,losses:full.filter(r=>r.pairs.goals[r.swap?1:0]<r.pairs.goals[r.swap?0:1]).length,goals:sum(full.map(r=>r.pairs.goals[r.swap?1:0])),shots:sum(full.map(r=>r.pairs.shots[r.swap?1:0]))}};
}
function combine(parts){
 assert(parts.length>0);const first=parts[0],expected=cases(first.seeds);
 for(const p of parts){assert.equal(p.schema,1);assert.equal(p.seeds,first.seeds);assert.deepEqual(p.sources,first.sources);}
 const rows=parts.flatMap(p=>p.rows).sort((a,b)=>a.id.localeCompare(b.id));
 assert.deepEqual(rows.map(r=>r.id),expected.map(r=>r.id).sort((a,b)=>a.localeCompare(b)),'incomplete or duplicate cases');
 return {schema:1,seeds:first.seeds,sources:first.sources,method:'Natural five-minute matches with default competition rules, 60Hz physics, paired home/away assignment, explicit position-matched synthetic rosters; full-time matches only in averages. No extrapolation to 90 simulated minutes.',overall:summarize(rows),scenarios:scenarios.map(s=>({id:s.id,...summarize(rows.filter(r=>r.scenario===s.id))})),rows};
}
function main(){
 const args=process.argv.slice(2),get=(k,d)=>{const i=args.indexOf(k);return i<0?d:args[i+1];};
 const out=get('--out','docs/validation/match-balance.json');
 let report;
 if(args[0]==='--merge'){report=combine(args.slice(1,args.indexOf('--out')<0?undefined:args.indexOf('--out')).map(f=>JSON.parse(fs.readFileSync(f))));}
 else{
  const seeds=Number(get('--seeds','2')),shards=Number(get('--shards','1')),shard=Number(get('--shard','0')),sources=fingerprints(),rows=[];
  for(const c of cases(seeds,shards,shard)){const r=simulate(c);rows.push(r);console.log('MATCH_BALANCE '+JSON.stringify({id:r.id,goals:r.pairs.goals,shots:r.pairs.shots,seconds:r.elapsed,finish:r.finishReason}));}
  assert.deepEqual(fingerprints(),sources);
  const part={schema:1,seeds,shards,shard,sources,rows};
  report=shards===1?combine([part]):part;
 }
 fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');
 console.log('BALANCE_SUMMARY '+JSON.stringify(report.overall??{shard:report.shard,matches:report.rows.length}));
}
module.exports={cases,config,summarize,combine,simulate,scenarios,fingerprints};
if(require.main===module)main();
