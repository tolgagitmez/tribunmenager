#!/usr/bin/env node
'use strict';
// Passive comparison of actual flights. A predicted aim is never a completion.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),zlib=require('node:zlib'),crypto=require('node:crypto'),assert=require('node:assert/strict'),v8=require('node:v8');
const root=path.resolve(__dirname,'..'),T=require('../tactics');
const opt=(key,fallback)=>{const i=process.argv.indexOf(key);return i<0?fallback:process.argv[i+1];};
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const sourceAt=file=>{const b=fs.readFileSync(file);return (file.endsWith('.gz')?zlib.gunzipSync(b):b).toString();};
const baselineFile=path.resolve(opt('--baseline-file',path.join(root,'docs/validation/baselines/stage2-football-sim.js.gz')));
const stage1File=path.resolve(opt('--stage1-file',path.join(root,'docs/validation/baselines/stage1-football-sim.js.gz')));
const sources={baseline:sourceAt(baselineFile),current:sourceAt(path.join(root,'football-sim.js')),stage1:sourceAt(stage1File)};
function load(source,label){const m=new Module(path.join(root,label),module);m.filename=path.join(root,label);m.paths=module.paths;m._compile(source,m.filename);return m.exports;}
const engines={baseline:load(sources.baseline,'arrival-stage2.js'),current:load(sources.current,'arrival-current.js')};
const stage1=load(sources.stage1,'arrival-stage1.js');
const mode=opt('--mode','matrix'),seconds=Number(opt('--seconds','300')),follow=Number(opt('--follow-seconds','8'));
assert(['fork','matrix'].includes(mode));assert(Number.isFinite(seconds)&&seconds>0&&seconds<=5400);assert(Number.isFinite(follow)&&follow>0&&follow<=30);
const preset=id=>{const p=T.presets.find(p=>p.id===id);assert(p);return p.tactics;};
const starters=[8,9,10,7,5,6,4,2,3,1,0],passKinds=new Set(['pass','through','cutback','cross','long-pass']);
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z),copyPoint=p=>p?{x:p.x,z:p.z}:null;
const pose=p=>p?Object.fromEntries(['id','team','role','x','z','vx','vz','face','speed','pace','energy','stamina','passing','kickFoot','preferredFoot','weakFoot'].map(k=>[k,p[k]??null])):null;
const copyCommand=c=>c?{x:c.x,z:c.z,pace:c.pace,state:c.state}:null;
const roster=strength=>Array.from({length:11},(_,id)=>({id,name:`Synthetic ${id}`,rating:strength,passing:strength,shooting:strength,tackling:strength,vision:strength,composure:strength,dribbling:strength,pace:strength,agility:strength,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:strength-12}));
function config(s){return {seed:s.seed,starters,formation:s.formation||'4-3-3',awayFormation:'4-2-3-1',matchMinutes:seconds>300?90:5,players:roster(s.strength||82),tactics:{...preset(s.home||'balanced'),...s.change},awayTactics:preset(s.away||'counter')};}
function observe(m,physics,detailed){
 const flights=[],events=[];let active=null;
 function sample(){
  if(!active||m.flight?.id!==active.id)return;
  const q=m.flight.target;if(!q?.active)return;
  const gap=distance(q,m.ball);
  if(gap<active.minGap){active.minGap=gap;active.closest={time:m.time,ball:copyPoint(m.ball),receiver:copyPoint(q)};}
 }
 function finish(reason,extra={}){
  if(!active)return;
  sample();Object.assign(active,{resolved:true,resolution:reason,end:m.time,elapsed:m.time-active.time,...extra});active=null;
 }
 const acquire=m.acquire,release=m.release,setRestart=m.setRestart;
 m.acquire=function(p){
  const f=this.flight;sample();const out=acquire.call(this,p);
  if(out){
   if(detailed)events.push({type:'acquire',time:this.time,playerId:p.id,team:p.team,from:f?.from?.id??null,intended:f?.target?.id??null});
   if(active&&f?.id===active.id)finish(p.id===active.targetId?'intended-reception':p.team===active.team?'other-own-reception':'opponent-reception',{acquiredBy:p.id,acquiredTeam:p.team});
  }
  return out;
 };
 m.setRestart=function(kind,team,spot,...args){
  sample();if(active)finish(['throw','goal-kick','corner'].includes(kind)?'out':'restart',{restart:{kind,team,spot:{...spot}},lastTouch:this.lastTouch?.id??null,ownLastTouchOut:['throw','goal-kick','corner'].includes(kind)&&this.lastTouch?.team===active.team});
  return setRestart.call(this,kind,team,spot,...args);
 };
 m.release=function(){
  const k=this.kick,before={...this.ball},command=copyCommand(this.targets.get(k.target)),from=pose(k.p),target=pose(k.target),previousSerial=this.releaseSerial;
  sample();const out=release.call(this);
  if(!this.flight||this.releaseSerial===previousSerial||!passKinds.has(k.kind))return out;
  if(active)finish('replaced-flight');
  const aimDistance=distance(before,k.point),power=Math.hypot(this.ball.vx,this.ball.vz),arrival=this.passTime(k.kind,aimDistance,power),speed=target?Math.hypot(target.vx,target.vz):null;
  const record={id:this.flight.id,kind:k.kind,team:k.p.team,time:this.time,fromId:k.p.id,targetId:k.target?.id??null,targetRole:k.target?.role??null,aimDistance,power,nominalArrival:Number.isFinite(arrival)?arrival:null,commandState:command?.state??null,targetSpeed:speed,targetCommandDistance:command&&target?distance(command,target):null,aimDistanceToCommand:command?distance(k.point,command):null,minGap:Infinity,resolved:false};
  if(detailed){Object.assign(record,{from,target,command,point:{...k.point},ballBefore:before,ballAfter:{...this.ball},duration:k.duration,contactClock:k.clock,physicalBallAtAimDistance:Number.isFinite(arrival)?physics.predict(this.ball,arrival):null});events.push({type:'release',time:this.time,id:record.id,from:record.fromId,target:record.targetId,kind:k.kind});}
  flights.push(record);active=record;sample();return out;
 };
 function settle(){sample();if(active&&m.flight?.id!==active.id)finish(m.goalPause?'goal':'flight-cleared');}
 function results(){
  if(active){sample();active.elapsed=m.time-active.time;active.resolution='pending-at-window-end';}
  const byTeam=[0,1].map(team=>{
   const all=flights.filter(f=>f.team===team),targeted=all.filter(f=>f.targetId!==null),resolved=targeted.filter(f=>f.resolved),ground=resolved.filter(f=>['pass','cutback','through'].includes(f.kind)),finite=resolved.filter(f=>Number.isFinite(f.minGap));
   const count=reason=>resolved.filter(f=>f.resolution===reason).length;
   return {released:all.length,targeted:targeted.length,resolvedTargeted:resolved.length,pendingTargeted:targeted.length-resolved.length,intendedReceives:count('intended-reception'),otherOwnReceives:count('other-own-reception'),opponentReceives:count('opponent-reception'),intendedMisses:resolved.filter(f=>f.resolution!=='intended-reception').length,ownLastTouchOut:resolved.filter(f=>f.ownLastTouchOut).length,out:count('out'),goalsFromPass:count('goal'),clearedOrReplaced:resolved.filter(f=>['flight-cleared','replaced-flight'].includes(f.resolution)).length,meanResolvedMinCentreGap:finite.length?finite.reduce((s,f)=>s+f.minGap,0)/finite.length:null,groundTargeted:{resolved:ground.length,intendedReceives:ground.filter(f=>f.resolution==='intended-reception').length,ownLastTouchOut:ground.filter(f=>f.ownLastTouchOut).length,meanMinCentreGap:ground.length?ground.reduce((s,f)=>s+f.minGap,0)/ground.length:null},byKind:Object.fromEntries([...passKinds].map(kind=>{const a=all.filter(f=>f.kind===kind);return [kind,{released:a.length,intendedReceives:a.filter(f=>f.resolution==='intended-reception').length,ownLastTouchOut:a.filter(f=>f.ownLastTouchOut).length}];}))};
  });
  // Untargeted and pending flights have no completed minimum-gap measurement.
  const serializable=flights.map(f=>({...f,minGap:Number.isFinite(f.minGap)?f.minGap:null}));
  return {byTeam,...(detailed?{flights:serializable,events}:{})};
 }
 return {sample:settle,results};
}
function run(m,engine,duration,detailed=false){
 const initial={time:m.time,seed:m.seed,owner:m.owner?.id??null,score:[...m.score],passes:[...m.passes],completed:[...m.completed]},observer=observe(m,engine.BallPhysics,detailed),previous=m.players.map(copyPoint),shape=[0,1].map(()=>({samples:0,width:0,defenceLine:0}));
 let maxPlayerStep=0,maxBallStep=0,firstOpponent=null,previousBall=copyPoint(m.ball);const own=m.owner?.team??m.flight?.from.team??0;
 for(let tick=0;tick<Math.round(duration*60)&&!m.done;tick++){
  const wasDead=!!m.restart||!!m.goalPause;m.step();observer.sample();
  for(const[i,p]of m.players.entries()){
   assert([p.x,p.z,p.vx,p.vz,p.face].every(Number.isFinite));if(!p.referee)assert([p.energy,p.stamina].every(Number.isFinite));maxPlayerStep=Math.max(maxPlayerStep,distance(p,previous[i]));previous[i]=copyPoint(p);
  }
  assert(['x','y','z','vx','vy','vz'].every(k=>Number.isFinite(m.ball[k])));
  if(!wasDead&&!m.restart&&!m.goalPause)maxBallStep=Math.max(maxBallStep,distance(m.ball,previousBall));previousBall=copyPoint(m.ball);
  if(firstOpponent===null&&m.owner?.team===1-own)firstOpponent={time:m.time,id:m.owner.id,team:m.owner.team};
  if(tick%60===0&&!m.restart&&!m.kick?.restartContext&&!m.goalPause)for(const team of [0,1]){
   const field=m.field(team),defs=field.filter(p=>p.role==='DEF'),s=shape[team];s.samples++;s.width+=Math.max(...field.map(p=>p.z))-Math.min(...field.map(p=>p.z));s.defenceLine+=defs.reduce((a,p)=>a+p.x*(team===0?1:-1),0)/(defs.length||1);
  }
 }
 assert(maxPlayerStep<=.15,`player step ${maxPlayerStep}`);assert.deepEqual(m.score,[0,1].map(t=>m.events.filter(e=>e.type==='goal'&&e.team===t).length));
 if(initial.time===0&&duration===m.duration)assert(m.done,'complete match must finish');
 return {initial,end:m.time,completed:m.done,finalSeed:m.seed,score:[...m.score],shots:[...m.shots],passes:[...m.passes],completedPasses:[...m.completed],windowPasses:m.passes.map((v,i)=>v-initial.passes[i]),windowCompleted:m.completed.map((v,i)=>v-initial.completed[i]),firstOpponent,finalOwner:m.owner?.id??null,finalPhase:m.phase,finalRestart:m.restart?{kind:m.restart.kind,team:m.restart.team,spot:{...m.restart.spot}}:null,finalBall:{...m.ball},finalFlight:m.flight?{kind:m.flight.kind,age:m.flight.age,target:m.flight.target?.id??null}:null,maxPlayerStep,maxFreeBallStep:maxBallStep,shape:shape.map(s=>({samples:s.samples,meanWidth:s.width/(s.samples||1),meanDefenceLine:s.defenceLine/(s.samples||1)})),arrivals:observer.results(),telemetry:structuredClone(m.telemetry)};
}
const report={generatedAt:new Date().toISOString(),mode,sources:{baseline:hash(sources.baseline),current:hash(sources.current),stage1Prefix:hash(sources.stage1),tactics:hash(fs.readFileSync(path.join(root,'tactics.js'))),observer:hash(fs.readFileSync(__filename))},definitions:{baseline:'Exact published stage2 engine 0adbed0b; retained gzip, not Git HEAD.',minimumGap:'Minimum sampled actual ball/selected receiver centre gap from release until resolution; acquire hook samples before normal first-touch impulse. A swept physical contact can occur between frames, so centre gap at acquisition can exceed1.10m.',resolvedTargeted:'Pass-kind flights with an intended recipient that resolve by actual acquisition, boundary restart, goal, replacement or flight clearing. Pending window-end flights are excluded from intended-miss denominators.',ownLastTouchOut:'Targeted flight directly resolving in throw/goal-kick/corner while passing team made last contact. It is not inferred from absence of opponent possession.',limits:'Small synthetic sample, no win target, ball/receiver repositioning, RNG forcing, hidden opponent commands or future plans. Tactical changes and preparation timing may diverge after the shared starting state.'}};
if(mode==='fork'){
 const at=Number(opt('--at','3655.30'));assert(Number.isFinite(at)&&at>=3652.25&&at<5400);
 const cache=opt('--snapshot-file',null);let state;
 const cfg={seed:77,starters,formation:'4-3-3',matchMinutes:90,tactics:preset('press')};
 if(cache){const s=v8.deserialize(fs.readFileSync(cache));assert.equal(s.baselineHash,hash(sources.baseline));assert(Math.abs(s.state.time-at)<2e-5,`snapshot time ${s.state.time} != ${at}`);state=s.state;}
 else{
  const prefix=new stage1.Match(cfg);for(let i=0;i<Math.round(3652.25*60);i++)prefix.step();
  const stage2=Object.assign(Object.create(engines.baseline.Match.prototype),structuredClone(prefix));for(let i=0;i<Math.round((at-3652.25)*60);i++)stage2.step();state=structuredClone(stage2);
 }
 const save=opt('--save-snapshot',null);if(save)fs.writeFileSync(save,v8.serialize({baselineHash:hash(sources.baseline),state}));
 report.config=cfg;report.at=state.time;report.prefix='Complete stage1 match to3652.25s, then published stage2 to selected fork time. Both branches receive identical complete state and RNG.';report.followSeconds=follow;report.branches={};
 for(const[name,engine]of Object.entries(engines)){const m=Object.assign(Object.create(engine.Match.prototype),structuredClone(state));report.branches[name]=run(m,engine,follow,true);}
 assert.deepEqual(report.branches.baseline.initial,report.branches.current.initial);
}else{
 const scenarios=[{id:'balanced21',seed:21},{id:'press42',seed:42,away:'press'},{id:'narrow21',seed:21,change:{width:'narrow'}},{id:'wide21',seed:21,change:{width:'wide'}},{id:'short42',seed:42,away:'press',change:{passing:'short'}},{id:'direct42',seed:42,away:'press',change:{passing:'direct'}},{id:'weak442-77',seed:77,strength:65,formation:'4-4-2',home:'possession',away:'press'},{id:'strong352-21',seed:21,strength:91,formation:'3-5-2',home:'counter',away:'wide'}];
 report.seconds=seconds;report.runs=[];report.observerConsistency={baseline:{},current:{}};
 for(const s of scenarios){
  const cfg=config(s),row={scenario:s,config:cfg};
  for(const[name,engine]of Object.entries(engines)){
   const observed=new engine.Match(cfg);row[name]=run(observed,engine,seconds);
   const unobserved=new engine.Match(cfg);for(let i=0;i<Math.round(seconds*60)&&!unobserved.done;i++)unobserved.step();
   // Remove only our own wrappers after the run. Compare all engine state,
   // including restart takers/flags and tactical targets, in every scenario.
   for(const hook of ['acquire','release','setRestart'])delete observed[hook];
   assert.deepEqual(structuredClone(observed),structuredClone(unobserved),`${name}/${s.id}: observer changed match state`);report.observerConsistency[name][s.id]=true;
  }
  report.runs.push(row);process.stderr.write(`${s.id} ${row.baseline.score}->${row.current.score}\n`);
 }
 report.replay={};
 for(const[name,engine]of Object.entries(engines)){
  const cfg=report.runs[0].config,observed=new engine.Match(cfg),result=run(observed,engine,seconds);assert.deepEqual(result,report.runs[0][name]);report.replay[name]=true;
 }
}
const output=opt('--output',null),json=JSON.stringify(report,null,2)+'\n';if(output){fs.mkdirSync(path.dirname(path.resolve(output)),{recursive:true});fs.writeFileSync(output,json);}else process.stdout.write(json);
