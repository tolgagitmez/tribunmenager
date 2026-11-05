#!/usr/bin/env node
'use strict';
// Passive comparison of actual flights. A predicted aim is never a completion.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),zlib=require('node:zlib'),crypto=require('node:crypto'),assert=require('node:assert/strict'),v8=require('node:v8');
const root=path.resolve(__dirname,'..'),T=require('../tactics');
const opt=(key,fallback)=>{const i=process.argv.indexOf(key);return i<0?fallback:process.argv[i+1];};
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const sourceAt=file=>{const b=fs.readFileSync(file);return (file.endsWith('.gz')?zlib.gunzipSync(b):b).toString();};
const baselineFile=path.resolve(opt('--baseline-file',path.join(root,'docs/validation/baselines/stage3-football-sim.js.gz')));
const sources={baseline:sourceAt(baselineFile),current:sourceAt(path.join(root,'football-sim.js'))};
assert.equal(hash(sources.baseline),'4c9279ad5411460bcbb349fa510ff1267607cc5f2e5292f371e256afe9857a6f','baseline must be the exact published stage3 engine');
function load(source,label){const m=new Module(path.join(root,label),module);m.filename=path.join(root,label);m.paths=module.paths;m._compile(source,m.filename);return m.exports;}
const engines={baseline:load(sources.baseline,'interception-stage3.js'),current:load(sources.current,'interception-current.js')};
const mode=opt('--mode','matrix'),seconds=Number(opt('--seconds','300')),follow=Number(opt('--follow-seconds','8'));
assert(['fork','matrix'].includes(mode));assert(Number.isFinite(seconds)&&seconds>0&&seconds<=5400);assert(Number.isFinite(follow)&&follow>0&&follow<=30);
const preset=id=>{const p=T.presets.find(p=>p.id===id);assert(p);return p.tactics;};
const starters=[8,9,10,7,5,6,4,2,3,1,0],passKinds=new Set(['pass','through','cutback','cross','long-pass']);
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z),copyPoint=p=>p?{x:p.x,z:p.z}:null;
const gaps=flights=>{const a=flights.map(f=>f.minGap).filter(Number.isFinite).sort((x,y)=>x-y);return {count:a.length,minimum:a[0]??null,median:a.length?a[Math.floor((a.length-1)*.5)]:null,p90:a.length?a[Math.floor((a.length-1)*.9)]:null,maximum:a.at(-1)??null,mean:a.length?a.reduce((s,n)=>s+n,0)/a.length:null};};
const pose=p=>p?Object.fromEntries(['id','team','role','x','z','vx','vz','face','speed','pace','energy','stamina','passing','kickFoot','preferredFoot','weakFoot'].map(k=>[k,p[k]??null])):null;
const copyCommand=c=>c?{x:c.x,z:c.z,pace:c.pace,state:c.state}:null;
const roster=strength=>Array.from({length:11},(_,id)=>({id,name:`Synthetic ${id}`,rating:strength,passing:strength,shooting:strength,tackling:strength,vision:strength,composure:strength,dribbling:strength,pace:strength,agility:strength,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:strength-12}));
function config(s){return {seed:s.seed,starters,formation:s.formation||'4-3-3',awayFormation:'4-2-3-1',matchMinutes:seconds>300?90:5,players:roster(s.strength||82),tactics:{...preset(s.home||'balanced'),...s.change},awayTactics:preset(s.away||'counter')};}
const scenarios=[{id:'balanced21',seed:21},{id:'press42',seed:42,away:'press'},{id:'narrow21',seed:21,change:{width:'narrow'}},{id:'wide21',seed:21,change:{width:'wide'}},{id:'short42',seed:42,away:'press',change:{passing:'short'}},{id:'direct42',seed:42,away:'press',change:{passing:'direct'}},{id:'weak442-77',seed:77,strength:65,formation:'4-4-2',home:'possession',away:'press'},{id:'strong352-21',seed:21,strength:91,formation:'3-5-2',home:'counter',away:'wide'}];
function observe(m,physics,detailed){
 const flights=[],events=[];let active=null;
 function sample(){
  if(!active||m.flight?.id!==active.id)return;
  const q=m.flight.target;if(!q?.active)return;
  const gap=distance(q,m.ball);
  if(gap<active.minGap){active.minGap=gap;active.closest={time:m.time,ball:copyPoint(m.ball),receiver:copyPoint(q)};}
  if(detailed){
   const command=copyCommand(m.targets.get(q)),last=active.commands?.at(-1);
   if(command&&(!last||command.x!==last.x||command.z!==last.z||command.state!==last.state||command.pace!==last.pace)){
    active.commands??=[];active.commands.push({time:m.time,...command,receiver:copyPoint(q),shift:last?distance(command,last):0,receiveRunShift:last?.state==='receive-run'&&command.state==='receive-run'?distance(command,last):0});
   }
  }
 }
 function finish(reason,extra={}){
  if(!active)return;
  sample();Object.assign(active,{resolved:true,resolution:reason,end:m.time,elapsed:m.time-active.time,...extra});active=null;
 }
 const acquire=m.acquire,release=m.release,setRestart=m.setRestart;
 m.acquire=function(...args){
  const [p]=args,f=this.flight;sample();const out=acquire.apply(this,args);
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
 m.release=function(...args){
  const k=this.kick,before={...this.ball},command=copyCommand(this.targets.get(k.target)),from=pose(k.p),target=pose(k.target),previousSerial=this.releaseSerial;
  sample();const out=release.apply(this,args);
  if(!this.flight||this.releaseSerial===previousSerial||!passKinds.has(k.kind))return out;
  if(active)finish('replaced-flight');
  const aimDistance=distance(before,k.point),power=Math.hypot(this.ball.vx,this.ball.vz),arrival=this.passTime(k.kind,aimDistance,power),speed=target?Math.hypot(target.vx,target.vz):null;
  const record={id:this.flight.id,kind:k.kind,team:k.p.team,time:this.time,releaseObserved:true,fromId:k.p.id,targetId:k.target?.id??null,targetRole:k.target?.role??null,aimDistance,power,nominalArrival:Number.isFinite(arrival)?arrival:null,commandState:command?.state??null,targetSpeed:speed,targetCommandDistance:command&&target?distance(command,target):null,aimDistanceToCommand:command?distance(k.point,command):null,minGap:Infinity,resolved:false};
  if(detailed){Object.assign(record,{from,target,command,point:{...k.point},ballBefore:before,ballAfter:{...this.ball},duration:k.duration,contactClock:k.clock,physicalBallAtAimDistance:Number.isFinite(arrival)?physics.predict(this.ball,arrival):null});events.push({type:'release',time:this.time,id:record.id,from:record.fromId,target:record.targetId,kind:k.kind});}
  flights.push(record);active=record;sample();return out;
 };
 // A fork can begin after a real release. Its minimum is measured only from
 // this window's start, and that already-released flight is labeled explicitly.
 if(m.flight&&passKinds.has(m.flight.kind)){
  const f=m.flight,q=f.target,command=copyCommand(m.targets.get(q));
  active={id:f.id,kind:f.kind,team:f.from.team,time:m.time,releaseObserved:false,ageAtWindowStart:f.age,fromId:f.from.id,targetId:q?.id??null,targetRole:q?.role??null,commandState:command?.state??null,targetSpeed:q?Math.hypot(q.vx,q.vz):null,minGap:Infinity,resolved:false};
  if(detailed)Object.assign(active,{from:pose(f.from),target:pose(q),command,point:{...f.point},ballAtWindowStart:{...m.ball}});
  flights.push(active);sample();
 }
 function settle(){sample();if(active&&m.flight?.id!==active.id)finish(m.goalPause?'goal':'flight-cleared');}
 function results(){
  if(active){sample();active.elapsed=m.time-active.time;active.resolution='pending-at-window-end';}
  const byTeam=[0,1].map(team=>{
   const all=flights.filter(f=>f.team===team),targeted=all.filter(f=>f.targetId!==null),resolved=targeted.filter(f=>f.resolved),ground=resolved.filter(f=>['pass','cutback','through'].includes(f.kind)),finite=resolved.filter(f=>Number.isFinite(f.minGap));
   const count=reason=>resolved.filter(f=>f.resolution===reason).length;
   const interceptKinds=resolved.filter(f=>['pass','cutback'].includes(f.kind));
   const interceptions={resolved:interceptKinds.length,intendedReceives:interceptKinds.filter(f=>f.resolution==='intended-reception').length,intendedMisses:interceptKinds.filter(f=>f.resolution!=='intended-reception').length,ownLastTouchOut:interceptKinds.filter(f=>f.ownLastTouchOut).length,gaps:gaps(interceptKinds),missGaps:gaps(interceptKinds.filter(f=>f.resolution!=='intended-reception')),closestMisses:interceptKinds.filter(f=>f.resolution!=='intended-reception').sort((a,b)=>a.minGap-b.minGap).slice(0,5).map(f=>({id:f.id,kind:f.kind,time:f.time,targetId:f.targetId,minGap:Number.isFinite(f.minGap)?f.minGap:null,resolution:f.resolution,closest:f.closest,ownLastTouchOut:f.ownLastTouchOut??false}))};
   return {tracked:all.length,released:all.filter(f=>f.releaseObserved).length,alreadyReleasedAtWindowStart:all.filter(f=>!f.releaseObserved).length,targeted:targeted.length,resolvedTargeted:resolved.length,pendingTargeted:targeted.length-resolved.length,intendedReceives:count('intended-reception'),otherOwnReceives:count('other-own-reception'),opponentReceives:count('opponent-reception'),intendedMisses:resolved.filter(f=>f.resolution!=='intended-reception').length,ownLastTouchOut:resolved.filter(f=>f.ownLastTouchOut).length,out:count('out'),goalsFromPass:count('goal'),clearedOrReplaced:resolved.filter(f=>['flight-cleared','replaced-flight'].includes(f.resolution)).length,meanResolvedMinCentreGap:finite.length?finite.reduce((s,f)=>s+f.minGap,0)/finite.length:null,receiverInterceptionKinds:interceptions,groundTargeted:{resolved:ground.length,intendedReceives:ground.filter(f=>f.resolution==='intended-reception').length,ownLastTouchOut:ground.filter(f=>f.ownLastTouchOut).length,meanMinCentreGap:ground.length?ground.reduce((s,f)=>s+f.minGap,0)/ground.length:null},byKind:Object.fromEntries([...passKinds].map(kind=>{const a=all.filter(f=>f.kind===kind),r=a.filter(f=>f.targetId!==null&&f.resolved);return [kind,{tracked:a.length,released:a.filter(f=>f.releaseObserved).length,resolvedTargeted:r.length,intendedReceives:r.filter(f=>f.resolution==='intended-reception').length,intendedMisses:r.filter(f=>f.resolution!=='intended-reception').length,ownLastTouchOut:r.filter(f=>f.ownLastTouchOut).length,gaps:gaps(r)}];}))};
  });
  // Untargeted and pending flights have no completed minimum-gap measurement.
  const serializable=flights.map(f=>({...f,minGap:Number.isFinite(f.minGap)?f.minGap:null,...(detailed?{maxCommandShift:Math.max(0,...(f.commands||[]).map(c=>c.shift)),maxReceiveRunCommandShift:Math.max(0,...(f.commands||[]).map(c=>c.receiveRunShift))}:{})}));
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
const report={generatedAt:new Date().toISOString(),mode,sources:{baseline:hash(sources.baseline),current:hash(sources.current),tactics:hash(fs.readFileSync(path.join(root,'tactics.js'))),observer:hash(fs.readFileSync(__filename))},definitions:{baseline:'Exact published stage3 engine 4c9279ad; retained gzip, not Git HEAD.',minimumGap:'Minimum sampled actual ball/selected receiver centre gap from release until resolution; acquire hook samples before normal first-touch impulse. A swept physical contact can occur between frames, so centre gap at acquisition can exceed1.10m.',resolvedTargeted:'Pass-kind flights with an intended recipient that resolve by actual acquisition, boundary restart, goal, replacement or flight clearing. Pending window-end flights are excluded from intended-miss denominators.',ownLastTouchOut:'Targeted flight directly resolving in throw/goal-kick/corner while passing team made last contact. It is not inferred from absence of opponent possession.',receiverInterceptionKinds:'Resolved targeted ordinary pass and cutback flights. Through/cross/long-pass flights remain separately counted; this label does not infer whether a particular planner branch was invoked.',existingFlight:'Fork snapshots may already contain a released pass. Its releaseObserved is false; its sampled gap starts at the fork, not original release.',limits:'Small synthetic sample, no win target, ball/receiver repositioning, RNG forcing, hidden opponent commands or future plans. Tactical changes and preparation timing may diverge after the shared starting state.'}};
if(mode==='fork'){
 const at=Number(opt('--at','29.183333333333334'));assert(Number.isFinite(at)&&at>=0&&at<5400);
 const cache=opt('--snapshot-file',null);let state,provenance,recordedConfig;
 const scenario=scenarios.find(s=>s.id===opt('--scenario','press42'));assert(scenario,'unknown scenario');const cfg=config(scenario);
 if(cache){
  const s=v8.deserialize(fs.readFileSync(cache));assert.equal(s.baselineHash??s.sourceHash,hash(sources.baseline));state=s.state;assert(Number.isFinite(state.time));
  recordedConfig=s.config??null;
  provenance=s.provenance||opt('--prefix-description','Caller-provided exact stage3 snapshot. Prefix provenance was not independently reconstructed by this command.');
 }else{
  const prefix=new engines.baseline.Match(cfg);for(let i=0;i<Math.round(at*60)&&!prefix.done;i++)prefix.step();state=structuredClone(prefix);
  recordedConfig=cfg;
  provenance='Complete exact published stage3 engine from initial kickoff to selected time, with the recorded config. Both branches receive identical complete state and RNG.';
 }
 const save=opt('--save-snapshot',null);if(save)fs.writeFileSync(save,v8.serialize({baselineHash:hash(sources.baseline),state,config:recordedConfig,provenance}));
 report.config=recordedConfig;report.at=state.time;report.prefix=provenance;report.followSeconds=follow;report.branches={};
 for(const[name,engine]of Object.entries(engines)){const m=Object.assign(Object.create(engine.Match.prototype),structuredClone(state));report.branches[name]=run(m,engine,follow,true);const plain=Object.assign(Object.create(engine.Match.prototype),structuredClone(state));for(let i=0;i<Math.round(follow*60)&&!plain.done;i++)plain.step();for(const hook of ['acquire','release','setRestart'])delete m[hook];assert.deepEqual(structuredClone(m),structuredClone(plain),`${name}/fork: observer changed state`);}report.observerConsistency={baseline:true,current:true};
 assert.deepEqual(report.branches.baseline.initial,report.branches.current.initial);
}else{
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
