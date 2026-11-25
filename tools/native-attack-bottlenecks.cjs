'use strict';
// Offline diagnostic only. Geometry is not native shot selection, xG, or causal proof.
const fs=require('node:fs');
const Replay=require('../integrations/league-soccer/native-replay.js');
const sum=(xs)=>xs.reduce((a,b)=>a+b,0);
const teamRow=()=>({episodes:0,boxEpisodes:0,shotEpisodes:0,controlledMs:0,boxMs:0,windowMs:0,
 windowEpisodes:0,windowEpisodesWithoutObservedShot:0,shotsDuringEpisodes:0,shotsOutsideEpisodes:0,
 endings:{opponent:0,retreat:0,loose:0,stoppage:0,gap:0,fullTime:0},details:[]});
const owner=f=>{const a=f.players.filter(p=>p.uniquePossession===true);return a.length===1?a[0]:null;};
const third=(f,t)=>f.ball[0]*f.attackDirection[t]>=55/3;
const box=(f,t)=>f.ball[0]*f.attackDirection[t]>=38.5&&f.ball[0]*f.attackDirection[t]<=55&&Math.abs(f.ball[1])<=20.15;
function windowAt(f,p){
 if(!p||p.goalkeeper||f.ball[2]>1.0)return false;
 const d=f.attackDirection[p.team],x=f.ball[0]*d,y=f.ball[1],depth=55-x;
 if(depth<2||Math.hypot(depth,y)>19||Math.abs(y)>13)return false;
 if(Math.hypot(p.position[0]-f.ball[0],p.position[1]-y)>1.6)return false;
 const defenders=f.players.filter(q=>q.team!==p.team&&!q.goalkeeper);
 if(defenders.some(q=>Math.hypot(q.position[0]-p.position[0],q.position[1]-p.position[1])<1.5))return false;
 // At least one unobstructed *sampled* outfield corridor to a point inside the goal.
 // Keeper position, ball trajectory, animation feasibility and timing are NOT predicted.
 return [-2.5,0,2.5].some(target=>{
  const dx=depth,dy=target-y,den=dx*dx+dy*dy;
  return !defenders.some(q=>{
   const qx=q.position[0]*d-x,qy=q.position[1]-y,u=(qx*dx+qy*dy)/den;
   return u>0&&u<1&&Math.hypot(qx-u*dx,qy-u*dy)<1.15;
  });
 });
}
function analyze(frames){
 if(!Array.isArray(frames)||frames.length<2||!frames.at(-1).done||frames.at(-1).matchMs<5400000)throw Error('Full native trace required');
 if(!frames.every(f=>typeof f.inPlay==='boolean'&&Array.isArray(f.attackDirection)&&f.attackDirection.length===2&&[1,-1].includes(f.attackDirection[0])&&f.attackDirection[1]===-f.attackDirection[0]&&f.players.every(p=>typeof p.uniquePossession==='boolean'&&typeof p.goalkeeper==='boolean')&&f.stats?.shots?.length===2&&f.stats.shots.every(x=>Number.isSafeInteger(x)&&x>=0)))throw Error('Incomplete possession or shot telemetry');
 const teams=[teamRow(),teamRow()];let active=null,excludedGapMs=0,observedOpenMs=0;
 function close(reason,end){
  if(!active)return;
  const e=active,r=teams[e.team];
  r.episodes++;r.boxEpisodes+=Number(e.box);r.shotEpisodes+=Number(e.shots>0);
  r.windowEpisodes+=Number(e.windowMs>=200);
  r.windowEpisodesWithoutObservedShot+=Number(e.windowMs>=200&&e.shots===0);
  r.endings[reason]++;
  r.details.push({...e,endMs:end,reason});
  active=null;
 }
 function begin(f,p){
  active={team:p.team,startMs:f.elapsedMs,startMatchMs:f.matchMs,box:box(f,p.team),windowMs:0,shots:0,controlledMs:0};
 }
 for(let i=1;i<frames.length;i++){
  const a=frames[i-1],b=frames[i],dt=b.elapsedMs-a.elapsedMs,pa=owner(a),pb=owner(b);
  const delta=b.stats.shots.map((v,t)=>v-a.stats.shots[t]);
  if(delta.some(x=>x<0))throw Error('Regressing shot counters');
  const contiguous=dt>0&&dt<=250&&a.attackDirection[0]===b.attackDirection[0]&&a.inPlay&&b.inPlay&&!a.done;
  // A shot delta belongs only to the immediately preceding controlled episode,
  // never to an inferred shooter or a gap across halftime.
  if(contiguous){
   observedOpenMs+=dt;
   if(pa&&third(a,pa.team)&&!active)begin(a,pa);
   if(active&&pa?.team===active.team){
    const r=teams[active.team];
    if(pb?.team===active.team&&third(b,active.team)){
     r.controlledMs+=dt;active.controlledMs+=dt;
     if(box(a,active.team)&&box(b,active.team)){r.boxMs+=dt;active.box=true;}
     if(windowAt(a,pa)&&windowAt(b,pb)){r.windowMs+=dt;active.windowMs+=dt;}
    }
    active.shots+=delta[active.team];r.shotsDuringEpisodes+=delta[active.team];
    delta[active.team]=0;
   }
   if(active){
    if(!pb)close('loose',b.elapsedMs);
    else if(pb.team!==active.team)close('opponent',b.elapsedMs);
    else if(!third(b,active.team))close('retreat',b.elapsedMs);
    else if(box(b,active.team))active.box=true;
   }
   if(!active&&pb&&third(b,pb.team))begin(b,pb);
  }else{
   if(dt>250)excludedGapMs+=dt;
   close(b.done?'fullTime':dt>250||a.attackDirection[0]!==b.attackDirection[0]?'gap':'stoppage',a.elapsedMs);
  }
  for(let t=0;t<2;t++)teams[t].shotsOutsideEpisodes+=delta[t];
 }
 close('fullTime',frames.at(-1).elapsedMs);
 for(let t=0;t<2;t++){
  const r=teams[t];
  if(r.shotsDuringEpisodes+r.shotsOutsideEpisodes!==frames.at(-1).stats.shots[t]-frames[0].stats.shots[t])throw Error('Shot accounting mismatch');
  r.details.sort((a,b)=>b.windowMs-a.windowMs||b.controlledMs-a.controlledMs);
  r.details=r.details.slice(0,50);
 }
 return {schema:1,engine:'league-soccer',authoritative:false,observedOpenMs,excludedGapMs,teams,
 note:'Sampled episodes split immediately on lost unique control, retreat, stoppage or gap. Shot counts are actual cumulative deltas, not inferred player actions. Geometric windows are screening proxies, not proof of a missed shot or causal attribution.'};
}
if(require.main===module){
 const [input,output]=process.argv.slice(2);
 if(!input)throw Error('Usage: node tools/native-attack-bottlenecks.cjs trace.ndjson [report.json]');
 const result=analyze(Replay.parse(fs.readFileSync(input,'utf8')));
 const json=JSON.stringify(result,null,2)+'\n';
 if(output)fs.writeFileSync(output,json);else process.stdout.write(json);
}
module.exports={analyze,windowAt};
