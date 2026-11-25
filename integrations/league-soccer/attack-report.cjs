'use strict';
// Sampled native telemetry, not inferred goals or synthetic AI actions.
const fs=require('node:fs');
const Replay=require('./native-replay.js');
const pair=()=>[0,0];
const validDirection=v=>Array.isArray(v)&&v.length===2&&[1,-1].includes(v[0])&&v[1]===-v[0];
function report(frames){
 if(frames.length<2||!frames.at(-1).done||frames.at(-1).matchMs<5400000)throw Error('Full native match required');
 const completeTelemetry=frames.every(f=>typeof f.inPlay==='boolean'&&validDirection(f.attackDirection)&&f.players.every(p=>typeof p.uniquePossession==='boolean'));
 const last=frames.at(-1),stats=last.stats||null;
 if(!stats)throw Error('Native cumulative statistics missing');
 const result={schema:1,engine:'league-soccer',frames:frames.length,nativeElapsedMs:last.elapsedMs-frames[0].elapsedMs,score:last.score.slice(),shots:stats.shots.slice(),onTarget:stats.onTarget.slice(),passes:stats.passes.slice(),completed:stats.completed.slice(),fouls:stats.fouls.slice(),possessionMs:stats.possessionMs.slice(),sampled:null};
 if(!completeTelemetry)return result;
 // Dimensions are pinned upstream gamedefines.hpp (55 x 36 half-pitch).
 const m={observedOpenPlayMs:0,excludedGapMs:0,controlledMs:pair(),controlledFinalThirdMs:pair(),controlledBoxMs:pair(),observedBoxCrossings:pair(),controlledBoxCrossings:pair(),keeperControlMs:pair()};
 const owner=f=>{const p=f.players.filter(p=>p.uniquePossession);return p.length===1?p[0]:null;};
 const inside=(f,t)=>f.ball[0]*f.attackDirection[t]>=55-16.5&&f.ball[0]*f.attackDirection[t]<=55&&Math.abs(f.ball[1])<=20.15;
 for(let i=1;i<frames.length;i++){
  const a=frames[i-1],b=frames[i],dt=b.elapsedMs-a.elapsedMs;
  if(dt<=0)continue;
  if(dt>250){m.excludedGapMs+=dt;continue;}
  if(!a.inPlay||!b.inPlay||a.attackDirection[0]!==b.attackDirection[0])continue;
  m.observedOpenPlayMs+=dt;
  const pa=owner(a),pb=owner(b);
  if(pa&&pb&&pa.team===pb.team){
   const t=pa.team;m.controlledMs[t]+=dt;
   if(a.ball[0]*a.attackDirection[t]>=55/3&&b.ball[0]*b.attackDirection[t]>=55/3)m.controlledFinalThirdMs[t]+=dt;
   if(inside(a,t)&&inside(b,t))m.controlledBoxMs[t]+=dt;
   if(pa.goalkeeper&&pb.goalkeeper&&pa.id===pb.id&&inside(a,1-t)&&inside(b,1-t))m.keeperControlMs[t]+=dt;
  }
  for(let t=0;t<2;t++){
   if(!inside(a,t)&&inside(b,t)){
    m.observedBoxCrossings[t]++;
    if(pb?.team===t)m.controlledBoxCrossings[t]++;
   }
  }
 }
 result.sampled=m;return result;
}
if(require.main===module){
 const [input,output]=process.argv.slice(2);
 if(!input||!output)throw Error('Usage: node attack-report.cjs trace.ndjson report.json');
 const r=report(Replay.parse(fs.readFileSync(input,'utf8')));
 fs.writeFileSync(output,JSON.stringify(r,null,2)+'\n');console.log(JSON.stringify(r));
}
module.exports={report};
