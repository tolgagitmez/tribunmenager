'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8')),start=frames[0].elapsedMs;
if(frames.some(f=>f.players.some(p=>p.goalkeeper&&p.keeperAction===undefined)))throw Error('Keeper action trace missing');
const a=R.create(frames,null,{groundRecovery:true}),b=R.create(frames,null,{keeperCompletion:true});
const report={schema:1,authoritative:false,events:0,eligible:0,palms:0,baselineErrorCm:0,candidateErrorCm:0,phases:{}};
for(const e of frames.flatMap(f=>f.nativeKeeperEvents||[]).slice(0,100)){
 report.events++;const at=e.timeMs-start;if(at<100||at>b.duration)continue;
 a.reset(Rig);b.reset(Rig);
 for(let t=at-100;t<=at;t+=10){a.sample(t,Rig,.01);b.sample(t,Rig,.01);}
 const match=p=>p.id===e.playerId&&p.team===e.team&&p.databaseId===e.databaseId;
 const x=a.sample(at,Rig,0).players.find(match),y=b.sample(at,Rig,0).players.find(match);
 if(!x||!y||!y.nativeKeeperDive)continue;
 const old=Rig.getPose(x),q=Rig.getPose(y);if(!q.nativeKeeperDive)continue;
 report.eligible++;const phase=q.nativeKeeperDive.phase;report.phases[phase]=(report.phases[phase]||0)+1;
 const c=R.coord(e.ball),point=[c.x,c.y,c.z];
 for(let i=0;i<2;i++)if(old.arms[i].contactTarget&&q.arms[i].contactTarget){
  report.palms++;report.baselineErrorCm+=100*Rig.surfaceError(old.arms[i].palm,point);
  report.candidateErrorCm+=100*Rig.surfaceError(q.arms[i].palm,point);
 }
}
report.baselineMeanCm=report.palms?report.baselineErrorCm/report.palms:null;
report.candidateMeanCm=report.palms?report.candidateErrorCm/report.palms:null;
report.note='Native confirmed lateral reach only; point proxy, not glove mesh or verified saved goal. Zero samples inconclusive.';
console.log(JSON.stringify(report,null,2));
