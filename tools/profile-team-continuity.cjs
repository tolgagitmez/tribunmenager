#!/usr/bin/env node
'use strict';
// Passive, end-of-step observations of commands and real match outcomes.
// No planner/decision/perception query or method wrapper is installed.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),zlib=require('node:zlib'),crypto=require('node:crypto'),assert=require('node:assert/strict'),v8=require('node:v8');
const root=path.resolve(__dirname,'..'),T=require('../tactics');
const opt=(key,fallback)=>{const i=process.argv.indexOf(key);return i<0?fallback:process.argv[i+1];};
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z),yaw=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
const point=p=>p?{x:p.x,z:p.z}:null,add=(counts,key,n=1)=>{counts[key]=(counts[key]||0)+n;};
const baselineFile=path.resolve(opt('--baseline-file',path.join(root,'docs/validation/baselines/stage8-football-sim.js.gz'))),baselineBytes=fs.readFileSync(baselineFile);
const sources={baseline:(baselineFile.endsWith('.gz')?zlib.gunzipSync(baselineBytes):baselineBytes).toString(),current:fs.readFileSync(path.join(root,'football-sim.js'),'utf8')};
assert.equal(hash(sources.baseline),'e16642b50e1d0b7d31cdc375dea7a83af85cf3da194a28362b65007f8420ad2e','baseline must be the exact published stage8 engine');
function load(source,label){const m=new Module(path.join(root,label),module);m.filename=path.join(root,label);m.paths=module.paths;m._compile(source,m.filename);return m.exports.Match;}
const versions={baseline:load(sources.baseline,'continuity-stage8.js'),current:load(sources.current,'continuity-current.js')};
const seconds=Number(opt('--seconds','300')),selected=opt('--scenario',null);
assert(Number.isFinite(seconds)&&seconds>0&&seconds<=5400,'seconds must be in (0,5400]');
const preset=id=>{const p=T.presets.find(p=>p.id===id);assert(p);return p.tactics;};
const starters=[8,9,10,7,5,6,4,2,3,1,0],roster=strength=>Array.from({length:11},(_,id)=>({id,name:`Synthetic ${id}`,rating:strength,passing:strength,shooting:strength,tackling:strength,vision:strength,composure:strength,dribbling:strength,pace:strength,agility:strength,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:strength-12}));
const scenarios=[{id:'balanced21',seed:21},{id:'wide21',seed:21,home:'wide',away:'counter'},{id:'press42',seed:42,home:'press',away:'press'},{id:'weak442-77',seed:77,strength:65,formation:'4-4-2',home:'possession',away:'press'}].filter(s=>!selected||s.id===selected);
assert(scenarios.length,'unknown scenario');
const config=s=>({seed:s.seed,starters,formation:s.formation||'4-3-3',awayFormation:'4-2-3-1',matchMinutes:seconds>300?90:5,players:roster(s.strength||82),tactics:preset(s.home||'balanced'),awayTactics:preset(s.away||'counter')});
const supportStates=new Set(['support','build-support','return-support','between-lines','wide-support','inside-support','cutback-support']),runStates=new Set(['channel-run','penetration','overlap','box-run']),pressStates=new Set(['press','counterpress','intercept']),markStates=new Set(['mark','track-run']),coverStates=new Set(['cover','screen','recovery-screen','delay']);
const offBallFamilies=new Set(['support','run','press','mark','cover']);
function family(state){return supportStates.has(state)?'support':runStates.has(state)?'run':pressStates.has(state)?'press':markStates.has(state)?'mark':coverStates.has(state)?'cover':['dribble','receive','shield'].includes(state)?'carrier':state==='receive-run'?'receiver':state;}
function observe(m){
 const stats={planSamples:0,openPlanSamples:0,commandSamples:0,stateChanges:0,familyChanges:0,sameContextStateChanges:0,sameContextFamilyChanges:0,sameContextPartnerChanges:0,sameContextMarkChanges:0,offBallReassignments:0,shortOffBallReassignments:0,forcedContextEnds:0,carryTargetChanges:0,largeCarryTargetTurns:0,maxCarryTargetTurn:0,supportEpisodes:0,supportEndedInReplan:0,supportReplanWithoutSelection:0,supportReplanAfterNearEndpointWithoutSelection:0,supportEndedByContext:0,supportContextWithoutSelection:0,supportSelectedAsPassTarget:0,supportSelectedForKickPreparation:0,supportPendingAtWindowEnd:0,endedEpisodeReasons:{},taskHistoryReasons:{},phaseSamples:{},tacticalPhaseSamples:{},transitions:{},taskPurposeSamples:{},perceptionSamples:0,perceptionKnownRivals:0,perceptionRememberedRivals:0};
 let lastTargets=null,lastSerial=m.releaseSerial,lastCarrier=null,previousPhases=[null,null];
 const commands=new Map(),histories=new Map();
 const possession=()=>m.owner?.team??m.flight?.from?.team??m.lastTeam;
 const context=()=>{const team=possession();return `${team}:${m.attackEpoch?.[team]??0}`;};
 function finish(e,reason){
  add(stats.endedEpisodeReasons,reason);
  if(e.family!=='support')return;
  if(reason==='reassigned'){
   stats.supportEndedInReplan++;if(!e.selected&&!e.prepared){stats.supportReplanWithoutSelection++;if(e.near)stats.supportReplanAfterNearEndpointWithoutSelection++;}
  }else if(reason==='window-end')stats.supportPendingAtWindowEnd++;
  else{stats.supportEndedByContext++;if(!e.selected&&!e.prepared)stats.supportContextWithoutSelection++;}
 }
 function clear(reason){for(const e of commands.values())finish(e,reason);commands.clear();lastCarrier=null;}
 function readHistory(p){
  const history=p.taskHistory;if(!Array.isArray(history))return;
  const previous=histories.get(p.id),at=previous?history.indexOf(previous):-1;
  // Records are immutable observer inputs. The bounded list may be truncated;
  // a frame samples every surviving new record once, using object identity.
  for(const e of history.slice(at+1))add(stats.taskHistoryReasons,e.reason??e.endReason??e.status??'unspecified');
  histories.set(p.id,history.at(-1));
 }
 function sample(){
  const dead=!!m.restart||!!m.kick?.restartContext||!!m.goalPause;
  for(const p of m.players){if(!p.referee)readHistory(p);}
  const preparation=m.kick?.target&&commands.get(m.kick.target.id);
  if(preparation?.family==='support'&&!preparation.prepared){preparation.prepared=true;stats.supportSelectedForKickPreparation++;}
  if(m.releaseSerial!==lastSerial){
   const f=m.flight;if(f?.target&&f.from?.team===f.target.team){const e=commands.get(f.target.id);if(e?.family==='support'&&!e.selected){e.selected=true;stats.supportSelectedAsPassTarget++;}}
   lastSerial=m.releaseSerial;
  }
  for(const [id,e]of commands){const p=m.players.find(p=>p.id===id);if(!p?.active){finish(e,'inactive');commands.delete(id);}else if(distance(p,e.point)<=3)e.near=true;}
  const carrier=!dead&&!m.kick&&m.owner?.active?m.owner:null,target=carrier?.carryTarget;
  if(carrier&&target&&Number.isFinite(target.x)&&Number.isFinite(target.z)){
   if(lastCarrier?.id===carrier.id&&lastCarrier.context===context()&&distance(lastCarrier.point,target)>.2){
    const oldGap=distance(carrier,lastCarrier.point),newGap=distance(carrier,target);
    if(oldGap>.8&&newGap>.8){const turn=Math.abs(yaw(Math.atan2(target.z-carrier.z,target.x-carrier.x),Math.atan2(lastCarrier.point.z-carrier.z,lastCarrier.point.x-carrier.x)));stats.carryTargetChanges++;stats.maxCarryTargetTurn=Math.max(stats.maxCarryTargetTurn,turn);if(turn>1.1)stats.largeCarryTargetTurns++;}
   }
   lastCarrier={id:carrier.id,point:point(target),context:context()};
  }else lastCarrier=null;
  if(dead){if(commands.size)clear('dead-ball');lastTargets=m.targets;return;}
  if(m.targets===lastTargets)return;lastTargets=m.targets;stats.planSamples++;stats.openPlanSamples++;
  const ctx=context(),active=new Set();
  for(const team of [0,1]){
   const phase=m.teamPhases?.[team]?.phase??null,tactical=m.tacticalPhase?.[team]??'unknown';
   if(phase!==null){add(stats.phaseSamples,`${team}:${phase}`);if(previousPhases[team]!==null&&previousPhases[team]!==phase)add(stats.transitions,`${team}:${previousPhases[team]}->${phase}`);previousPhases[team]=phase;}
   add(stats.tacticalPhaseSamples,`${team}:${tactical}`);
  }
  for(const [p,t]of m.targets){
   if(!p.active||p.referee||p.role==='GK')continue;active.add(p.id);stats.commandSamples++;
   const f=family(t.state),sp=m.supportPlans?.[p.team],mark=m.defensiveUnits?.[p.team]?.assignments?.get(p);
   const partner=p.task?.partnerId??(supportStates.has(t.state)?sp?.ownerId??m.owner?.id??m.flight?.target?.id:p.runIntent?.partnerId??p.supportIntent?.qId)??null;
   const focus=markStates.has(t.state)?p.task?.focusId??mark?.id??null:null;
   const old=commands.get(p.id),identity=`${f}:${partner}:${focus}`,sameContext=old?.context===ctx;
   if(old){
    if(old.state!==t.state){stats.stateChanges++;if(sameContext)stats.sameContextStateChanges++;}
    if(old.family!==f){stats.familyChanges++;if(sameContext)stats.sameContextFamilyChanges++;}
    if(sameContext&&old.partner!==partner&&old.family===f)stats.sameContextPartnerChanges++;
    if(sameContext&&old.focus!==focus&&old.family===f&&f==='mark')stats.sameContextMarkChanges++;
   }
   if(!old||old.identity!==identity||!sameContext){
    if(old){
     if(sameContext){if(offBallFamilies.has(old.family)){stats.offBallReassignments++;if(m.time-old.since<.45-1e-8)stats.shortOffBallReassignments++;}finish(old,'reassigned');}
     else{stats.forcedContextEnds++;finish(old,'possession-context');}
    }
    const e={identity,family:f,state:t.state,partner,focus,point:point(t),since:m.time,context:ctx,selected:false,prepared:false,near:distance(p,t)<=3};commands.set(p.id,e);if(f==='support')stats.supportEpisodes++;
   }else{old.state=t.state;old.point=point(t);old.near||=distance(p,t)<=3;}
   if(p.task?.purpose)add(stats.taskPurposeSamples,p.task.purpose);
   const memories=p.perception?.records??p.perception?.memory??p.perception?.observations??p.perception?.rivals;
   if(memories){const values=Array.isArray(memories)?memories:Object.values(memories);stats.perceptionSamples++;stats.perceptionKnownRivals+=values.length;stats.perceptionRememberedRivals+=values.filter(v=>Number.isFinite(v.seenAt)&&m.time-v.seenAt>.05).length;}
  }
  for(const [id,e]of commands)if(!active.has(id)){finish(e,'uncommanded');commands.delete(id);}
 }
 function results(){for(const e of commands.values())finish(e,'window-end');return stats;}
 return {sample,results};
}
function run(m,duration,observeCommands){
 const observer=observeCommands?observe(m):null,previous=m.players.map(point);let previousBall=point(m.ball),maxPlayerStep=0,maxFreeBallStep=0;
 for(let tick=0;tick<Math.round(duration*60)&&!m.done;tick++){
  const dead=!!m.restart||!!m.goalPause||!!m.kick?.restartContext;m.step();if(observer)observer.sample();
  for(const [i,p]of m.players.entries()){
   assert(['x','z','vx','vz','face'].every(k=>Number.isFinite(p[k])),`nonfinite player ${p.id}`);
   if(!p.referee)assert([p.stamina,p.energy].every(Number.isFinite),`nonfinite effort ${p.id}`);
   maxPlayerStep=Math.max(maxPlayerStep,distance(p,previous[i]));previous[i]=point(p);
  }
  assert(['x','y','z','vx','vy','vz'].every(k=>Number.isFinite(m.ball[k])),'nonfinite ball');
  if(!dead&&!m.restart&&!m.goalPause&&!m.kick?.restartContext)maxFreeBallStep=Math.max(maxFreeBallStep,distance(m.ball,previousBall));previousBall=point(m.ball);
 }
 assert(maxPlayerStep<=.15,`player step exceeded .15m at 60Hz: ${maxPlayerStep}`);
 assert.deepEqual(m.score,[0,1].map(team=>m.events.filter(e=>e.type==='goal'&&e.team===team).length),'score must be actual goal events');
 if(duration===m.duration)assert(m.done,'complete match must finish');
 return {end:m.time,completed:m.done,score:[...m.score],shots:[...m.shots],passes:[...m.passes],completedPasses:[...m.completed],turnovers:m.telemetry.turnovers,abortedKicks:m.telemetry.abortedKicks||0,finalSeed:m.seed,finalOwner:m.owner?.id??null,finalPhase:m.phase,finalBall:{...m.ball},maxPlayerStep,maxFreeBallStep,telemetry:structuredClone(m.telemetry),...(observer?{commands:observer.results()}:{})};
}
function state(m){return v8.deserialize(v8.serialize(m));}
function stateHash(value){
 const seen=new Map();
 const encode=v=>{
  if(v===null)return ['null'];if(typeof v==='undefined')return ['undefined'];
  if(typeof v==='number')return ['number',Number.isNaN(v)?'NaN':v===Infinity?'Infinity':v===-Infinity?'-Infinity':Object.is(v,-0)?'-0':v];
  if(typeof v!=='object')return [typeof v,String(v)];
  if(seen.has(v))return ['ref',seen.get(v)];const id=seen.size;seen.set(v,id);
  if(v instanceof Map)return ['map',id,[...v].map(([k,x])=>[encode(k),encode(x)])];
  if(v instanceof Set)return ['set',id,[...v].map(encode)];
  if(v instanceof Date)return ['date',id,v.toISOString()];
  return [Array.isArray(v)?'array':'object',id,Object.keys(v).sort().map(k=>[k,encode(v[k])])];
 };return hash(JSON.stringify(encode(value)));
}
const optionalHash=file=>fs.existsSync(path.join(root,file))?hash(fs.readFileSync(path.join(root,file))):null;
const report={generatedAt:new Date().toISOString(),seconds,scenarioFilter:selected,sources:{baseline:hash(sources.baseline),current:hash(sources.current),tactics:optionalHash('tactics.js'),perception:optionalHash('player-perception.js'),intent:optionalHash('team-intent.js'),observer:hash(fs.readFileSync(__filename))},definitions:{baseline:'Exact retained published stage8 engine e16642b5 from commit 68d0ea7; not the old local Git HEAD.',method:'No engine method wrappers. Sample only completed real steps and command maps when their identity changes. No planner, perception or decision query is invoked by this observer. Complete V8-roundtrip snapshots are deeply compared with a plain run and a separate deterministic replay for each engine/scenario. Canonical complete-graph hashes retain object references, Maps, undefined and numeric edge cases; raw V8 bytes are not a stable value encoding.',sameContext:'The same actual possession/flight/lastTeam and its attackEpoch. A possession-context change is recorded separately; restart/goal pauses close episodes as dead-ball.',family:'Fixed observer mapping shared by both engines: support includes support/build/return/between-lines/wide/inside/cutback; run includes channel/penetration/overlap/box; press includes press/counterpress/intercept; mark includes mark/track-run; cover includes cover/screen/recovery-screen/delay. These are command categories, not inferred player intentions.',shortOffBallReassignments:'An off-ball support/run/press/mark/cover episode changes family or partner/mark identity within .45s under the same possession context. Legitimate urgent changes also count; this is a churn proxy, not an error verdict.',carryTurns:'The actual owner carryTarget changes by more than .2m while both the previous and new target are over .8m away. Compare bearings from the same current player position; a turn over1.1rad counts as large. No candidate decisions are queried.',supportSelection:'A support command selection is observed separately at live kick preparation and real release. A replan counts as unselected only if neither targeted the helper during the episode; a receive-run handoff after live windup is therefore not silently treated as an unused link. Release counts require the command episode still to be active at release. Neither preparation nor release proves reception, pass-lane openness, execution feasibility or a wasted real opportunity. Near endpoint means centre gap<=3m. Replan/context/window-end terminations are separate.',taskReasons:'Optional current taskHistory records are read without mutation; records added between samples are counted once by object identity. Histories may be bounded and observer summaries do not claim unrecorded reasons.',phaseCoverage:'Current teamPhases records are sampled when a new open-play command map appears. Baseline phase coverage is absent because stage8 had only tacticalPhase; raw tacticalPhase is reported for both.',limits:'Four synthetic configurations and deterministic seeds, with no real squad data or win target. Changed perception and task timing naturally change future trajectories. Fewer command changes do not by themselves prove better football or possession.'},runs:[],verification:{observerConsistency:{baseline:{},current:{}},deterministicReplay:{baseline:{},current:{}},stateHashes:{baseline:{},current:{}}}};
for(const s of scenarios){
 const cfg=config(s),row={scenario:s,config:cfg};
 for(const [name,C]of Object.entries(versions)){
  const observed=new C(cfg),result=run(observed,seconds,true),observedState=state(observed),observedHash=stateHash(observedState);
  const plain=new C(cfg);run(plain,seconds,false);const plainState=state(plain);
  assert.deepEqual(observedState,plainState,`${name}/${s.id}: observer changed engine state`);assert.equal(observedHash,stateHash(plainState),`${name}/${s.id}: canonical complete-state hash differs from plain run`);
  const replay=new C(cfg),repeated=run(replay,seconds,true);assert.deepEqual(repeated,result,`${name}/${s.id}: summary replay differs`);assert.deepEqual(observedState,state(replay),`${name}/${s.id}: complete replay state differs`);assert.equal(observedHash,stateHash(state(replay)),`${name}/${s.id}: canonical complete-state replay hash differs`);
  row[name]=result;report.verification.observerConsistency[name][s.id]=true;report.verification.deterministicReplay[name][s.id]=true;report.verification.stateHashes[name][s.id]=observedHash;
 }
 report.runs.push(row);process.stderr.write(`${s.id}: ${row.baseline.score.join('-')} -> ${row.current.score.join('-')}; short changes ${row.baseline.commands.shortOffBallReassignments} -> ${row.current.commands.shortOffBallReassignments}\n`);
}
for(const [key,file]of Object.entries({current:'football-sim.js',tactics:'tactics.js',perception:'player-perception.js',intent:'team-intent.js',observer:path.relative(root,__filename)}))assert.equal(optionalHash(file),report.sources[key],`source changed during profiling: ${file}`);
const output=opt('--output',null),json=JSON.stringify(report,null,2)+'\n';if(output){fs.mkdirSync(path.dirname(path.resolve(output)),{recursive:true});fs.writeFileSync(output,json);}else process.stdout.write(json);
