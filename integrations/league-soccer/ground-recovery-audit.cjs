'use strict';
const fs=require('node:fs'),R=require('./native-replay.js'),Rig=require('../../humanoid-rig.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
if(frames.some(f=>f.players.some(p=>p.groundAction===undefined)))throw Error('Native ground state missing');
const baseline=R.create(frames,null,{contactPrecision:true}),candidate=R.create(frames,null,{groundRecovery:true});
const start=frames[0].elapsedMs,events=frames.flatMap(f=>f.nativeDuels||[]).filter(e=>e.kind!=='bump'&&e.tripType>=2).slice(0,80);
const report={schema:1,authoritative:false,events:events.length,samples:0,groundSamples:0,phases:{},baselineOverlapSum:0,candidateOverlapSum:0,lowestToe:null,lowestPalm:null,maxBoneError:0};
// Approximate upper torso as a sphere (not the skinned mesh).
const overlap=(a,b)=>Math.max(0,.42-Math.hypot(...a.torsoUpper.map((v,i)=>v-b.torsoUpper[i])));
for(const e of events){
 const at=e.timeMs-start;if(at<100||at>candidate.duration)continue;
 baseline.reset(Rig);candidate.reset(Rig);
 for(let t=at-100;t<=Math.min(at+900,candidate.duration);t+=20){
  const x=baseline.sample(t,Rig,.02),y=candidate.sample(t,Rig,.02);
  const idx=y.players.findIndex(p=>p.id===e.playerId&&p.databaseId===e.databaseId&&p.team===e.team),opp=y.players.findIndex(p=>p.id===e.opponentId);
  if(idx<0||opp<0)continue;const q=Rig.getPose(y.players[idx]),old=Rig.getPose(x.players[idx]);report.samples++;
  if(!q.nativeGroundRecovery)continue;report.groundSamples++;
  const g=q.nativeGroundRecovery;report.phases[g.phase]=(report.phases[g.phase]||0)+1;
  report.baselineOverlapSum+=overlap(old,Rig.getPose(x.players[opp]));report.candidateOverlapSum+=overlap(q,Rig.getPose(y.players[opp]));
  report.lowestToe=report.lowestToe===null?g.lowestToe:Math.min(report.lowestToe,g.lowestToe);
  report.lowestPalm=report.lowestPalm===null?g.supportPalmHeight:Math.min(report.lowestPalm,g.supportPalmHeight);
  const an=Rig.anatomyFor(y.players[idx]);for(const l of q.legs)report.maxBoneError=Math.max(report.maxBoneError,Math.abs(Math.hypot(...l.knee.map((v,i)=>v-l.hip[i]))-an.thigh),Math.abs(Math.hypot(...l.ankle.map((v,i)=>v-l.knee[i]))-an.shin));
 }
}
report.note='Severe recorded trip events only. Torso sphere overlap and toe/palm heights are proxies, not mesh collisions or planted hands. Zero samples inconclusive.';
console.log(JSON.stringify(report,null,2));
