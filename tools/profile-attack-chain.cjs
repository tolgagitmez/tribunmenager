#!/usr/bin/env node
'use strict';
// Actual-call diagnostics, independent plain runs and deterministic replays.
// No extra decision, planning, reception, shot-window or keeper query is made.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),zlib=require('node:zlib'),crypto=require('node:crypto'),assert=require('node:assert/strict'),v8=require('node:v8');
const root=path.resolve(__dirname,'..');
const opt=(key,fallback)=>{const i=process.argv.indexOf(key);return i<0?fallback:process.argv[i+1];};
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const fileHash=file=>hash(fs.readFileSync(path.join(root,file)));
// Bind hashes before requiring/compiling modules, then reject any changed file
// at the end. A later hash must never describe an earlier loaded module.
const sourceFiles={current:'football-sim.js',tactics:'tactics.js',perception:'player-perception.js',intent:'team-intent.js',diagnostics:'attack-diagnostics.js',profiler:path.relative(root,__filename)};
const initialFileHashes=Object.fromEntries(Object.entries(sourceFiles).map(([key,file])=>[key,fileHash(file)]));
const T=require('../tactics');
const sourceAt=file=>{const b=fs.readFileSync(file);return (file.endsWith('.gz')?zlib.gunzipSync(b):b).toString();};
const seconds=Number(opt('--seconds','300')),selected=opt('--scenario',null),engineFilter=opt('--engine','both');
assert(Number.isFinite(seconds)&&seconds>0&&seconds<=5400,'seconds must be in (0,5400]');
assert(['baseline','current','both'].includes(engineFilter),'engine must be baseline, current or both');
const baselineFile=path.resolve(opt('--baseline-file',path.join(root,'docs/validation/baselines/stage8-football-sim.js.gz')));
const sources={baseline:sourceAt(baselineFile),current:sourceAt(path.join(root,'football-sim.js'))};
assert.equal(hash(sources.current),initialFileHashes.current,'current engine changed between hash and source read');
assert.equal(hash(sources.baseline),'e16642b50e1d0b7d31cdc375dea7a83af85cf3da194a28362b65007f8420ad2e','baseline must be the retained published stage8 source');
assert.equal(hash(sources.current),'b29a8f9b49638ec6559bc58df6b9504400eaaaf3b44bd14439d4643c3bd394f3','stage10 observes the exact retained stage9 engine; changing the engine requires a new baseline contract');
const Diagnostics=require('../attack-diagnostics');
function load(source,label){const filename=path.join(root,label),m=new Module(filename,module);m.filename=filename;m.paths=module.paths;m._compile(source,filename);return m.exports.Match;}
const versions=Object.fromEntries(Object.entries(sources).filter(([name])=>engineFilter==='both'||engineFilter===name).map(([name,source])=>[name,load(source,`attack-chain-${name}.js`)]));
const preset=id=>{const p=T.presets.find(p=>p.id===id);assert(p);return p.tactics;};
const starters=[8,9,10,7,5,6,4,2,3,1,0],roster=strength=>Array.from({length:11},(_,id)=>({id,name:`Synthetic ${id}`,rating:strength,passing:strength,shooting:strength,tackling:strength,vision:strength,composure:strength,dribbling:strength,pace:strength,agility:strength,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:strength-12}));
const scenarios=[{id:'balanced21',seed:21},{id:'press42',seed:42,away:'press'},{id:'narrow21',seed:21,change:{width:'narrow'}},{id:'wide21',seed:21,change:{width:'wide'}},{id:'short42',seed:42,away:'press',change:{passing:'short'}},{id:'direct42',seed:42,away:'press',change:{passing:'direct'}},{id:'weak442-77',seed:77,strength:65,formation:'4-4-2',home:'possession',away:'press'},{id:'strong352-21',seed:21,strength:91,formation:'3-5-2',home:'counter',away:'wide'}].filter(s=>!selected||selected.split(',').includes(s.id));
assert(scenarios.length,'unknown scenario');
if(selected)for(const id of selected.split(','))assert(scenarios.some(s=>s.id===id),`unknown scenario ${id}`);
const config=s=>({seed:s.seed,starters,formation:s.formation||'4-3-3',awayFormation:'4-2-3-1',matchMinutes:seconds>300?90:5,players:roster(s.strength||82),tactics:{...preset(s.home||'balanced'),...s.change},awayTactics:preset(s.away||'counter')});
const point=p=>({x:p.x,z:p.z}),distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z),ratio=(n,d)=>d>0?n/d:null;
const snapshot=m=>v8.deserialize(v8.serialize(m));
function stateHash(value){
 const seen=new Map(),encode=v=>{
  if(v===null)return ['null'];if(v===undefined)return ['undefined'];
  if(typeof v==='number')return ['number',Number.isNaN(v)?'NaN':v===Infinity?'Infinity':v===-Infinity?'-Infinity':Object.is(v,-0)?'-0':v];
  if(typeof v!=='object')return [typeof v,String(v)];
  if(seen.has(v))return ['ref',seen.get(v)];const id=seen.size;seen.set(v,id);
  if(v instanceof Map)return ['map',id,[...v].map(([k,x])=>[encode(k),encode(x)])];
  if(v instanceof Set)return ['set',id,[...v].map(encode)];
  if(v instanceof Date)return ['date',id,v.toISOString()];
  return [Array.isArray(v)?'array':'object',id,Object.keys(v).sort().map(k=>[k,encode(v[k])])];
 };return hash(JSON.stringify(encode(value)));
}
function descriptorContract(m){
 const methods=new Set(Reflect.ownKeys(m).filter(key=>typeof m[key]==='function'));let proto=Object.getPrototypeOf(m);
 while(proto&&proto!==Object.prototype){for(const key of Reflect.ownKeys(proto))if(key!=='constructor'&&typeof Object.getOwnPropertyDescriptor(proto,key)?.value==='function')methods.add(key);proto=Object.getPrototypeOf(proto);}
 return {methods:Object.fromEntries([...methods].map(key=>[key,Object.getOwnPropertyDescriptor(m,key)||null])),nonEnumerableOwn:Reflect.ownKeys(m).filter(key=>!Object.getOwnPropertyDescriptor(m,key).enumerable)};
}
const timestamp=entry=>Number.isFinite(entry?.time)?entry.time:null;
function orderedPath(episodes,path){
 let entrants=episodes;
 const counts=[{stage:path[0],attacks:entrants.length}],transitions=[];
 for(let i=1;i<path.length;i++){
  const from=path[i-1],to=path[i],reached=[],ended=[],pending=[],censored=[],outOfOrder=[];
  for(const e of entrants){
   const previous=e.stages?.[from],next=e.stages?.[to],a=timestamp(previous),b=timestamp(next);
   const inOrder=b!==null&&a!==null&&b>=a-1e-8&&next.entryMode!=='at-start';
   if(inOrder){reached.push(e);continue;}
   if(b!==null){outOfOrder.push(e.id);continue;}
   if(e.status==='pending')pending.push(e);else if(e.status==='censored')censored.push(e);else ended.push(e);
  }
  assert.equal(entrants.length,reached.length+ended.length+pending.length+censored.length+outOfOrder.length);
  transitions.push({from,to,entered:entrants.length,reached:reached.length,endedWithoutNext:ended.length,firstMilestoneOrderIncompatible:outOfOrder.length,pendingWithoutNext:pending.length,censoredWithoutNext:censored.length,outOfOrderOrAtStartIds:outOfOrder,observedWindowRate:ratio(reached.length,entrants.length),resolvedOnlyRate:ratio(reached.length,reached.length+ended.length+outOfOrder.length)});
  entrants=reached;counts.push({stage:to,attacks:entrants.length});
 }
 return {path,cohort:episodes.length,counts,transitions};
}
function derive(d){
 const episodes=d.episodes||[];
 return {traceLimited:(d.truncatedEpisodes||0)>0,teams:[0,1].map(team=>{
  const own=episodes.filter(e=>e.team===team),gain=own.filter(e=>e.origin==='gain'),confirmed=gain.filter(e=>e.confirmedControl&&timestamp(e.stages?.gain)!==null),high=confirmed.filter(e=>e.startedBeyond?.finalThird||e.startedBeyond?.box),eligible=confirmed.filter(e=>!e.startedBeyond?.finalThird&&!e.startedBeyond?.box);
  const yes=(e,key)=>e.eligibility?.[key]===true;
  const groups={pressuredGainWithScreen:eligible.filter(e=>e.pressureRequired===true&&yes(e,'lineBreak')),unpressuredGainWithScreen:eligible.filter(e=>e.pressureRequired===false&&yes(e,'lineBreak')),pressuredGainWithoutScreen:eligible.filter(e=>e.pressureRequired===true&&!yes(e,'lineBreak')),unpressuredGainWithoutScreen:eligible.filter(e=>e.pressureRequired===false&&!yes(e,'lineBreak'))};
  const paths={pressuredGainWithScreen:['gain','pressureEscape','lineBreak','finalThird','box','shot'],unpressuredGainWithScreen:['gain','lineBreak','finalThird','box','shot'],pressuredGainWithoutScreen:['gain','pressureEscape','finalThird','box','shot'],unpressuredGainWithoutScreen:['gain','finalThird','box','shot']};
  const stats=d.teams?.find(t=>t.team===team)||d.teams?.[team];
  return {team,contactGainEpisodes:gain.length,confirmedGainEpisodes:confirmed.length,unconfirmedGainEpisodes:gain.length-confirmed.length,alreadyHighConfirmedGainEpisodes:high.length,unclassifiedPressureGainEpisodes:eligible.filter(e=>e.pressureRequired!==true&&e.pressureRequired!==false).length,marginal:stats?{stageCounts:stats.stageCounts,eligibleReached:stats.eligibleReached,stageEligibility:stats.stageEligibility,startedBeyond:stats.startedBeyond,notRequired:stats.notRequired,endedByStage:stats.endedByStage,endReasons:stats.endReasons,evidence:stats.evidence,rates:stats.rates}:null,orderedGainPaths:Object.fromEntries(Object.entries(groups).map(([key,group])=>[key,orderedPath(group,paths[key])]))};
 })};
}
function run(m,observed){
 const descriptors=descriptorContract(m),obs=observed?Diagnostics.attach(m,{maxEpisodes:100000}):null,previous=m.players.map(point);
 let maxPlayerStep=0;
 for(let i=0;i<Math.round(seconds*60)&&!m.done;i++){
  if(obs)obs.step(1/60);else m.step(1/60);
  for(const [index,p]of m.players.entries()){
   assert(['x','z','vx','vz','face'].every(k=>Number.isFinite(p[k])),`nonfinite player ${p.id}`);
   if(!p.referee)assert([p.stamina,p.energy].every(Number.isFinite),`nonfinite effort ${p.id}`);
   maxPlayerStep=Math.max(maxPlayerStep,distance(p,previous[index]));previous[index]=point(p);
  }
  assert(['x','y','z','vx','vy','vz'].every(k=>Number.isFinite(m.ball[k])),'nonfinite ball');
 }
 assert(maxPlayerStep<=.15,`player step exceeded .15m: ${maxPlayerStep}`);
 assert.deepEqual(m.score,[0,1].map(team=>m.events.filter(e=>e.type==='goal'&&e.team===team).length),'score must equal actual goal events');
 if(seconds===m.duration)assert(m.done,'full match did not finish');
 let diagnostics=null,derived=null;
 if(obs){
  const activeState=snapshot(m);diagnostics=obs.report();assert.deepEqual(obs.report(),diagnostics,'report query is not idempotent');assert.deepEqual(snapshot(m),activeState,'report query changed live match state');
  assert.equal(diagnostics.valid,true,`invalid diagnostics: ${JSON.stringify(diagnostics.errors)}`);
  assert.equal(diagnostics.truncatedEpisodes||0,0,'trace limit reached: complete ordered-cohort derivation would be invalid');
  const c=diagnostics.clock;
  assert(Math.abs(c.observedSeconds-m.time)<1e-7,'observation window differs from simulated time');
  assert(Math.abs(c.observedSeconds-c.inPlaySeconds-c.deadBallSeconds)<1e-7,'in-play/dead exposure does not partition time');
  assert(Math.abs(c.deadBallSeconds-c.restartSeconds-c.goalPauseSeconds)<1e-7,'restart/goal exposure does not partition dead time');
  assert(Math.abs(c.inPlaySeconds-c.controlledSeconds.reduce((a,b)=>a+b,0)-c.flightSeconds.reduce((a,b)=>a+b,0)-c.looseSeconds)<1e-7,'controlled/flight/loose exposure does not partition in-play time');
  assert.equal(c.unobservedSeconds,0,'natural run contains an unobserved gap');
  for(const team of [0,1]){
   assert.equal(diagnostics.teams[team].shots,m.shots[team],`team ${team}: physical shots differ from engine`);
   assert.equal(diagnostics.teams[team].passes.attempted,m.passes[team],`team ${team}: actual pass releases differ from engine`);
   assert.equal(diagnostics.teams[team].passes.completed,m.completed[team],`team ${team}: actual completed passes differ from engine`);
  }
  assert.equal(diagnostics.teams.reduce((n,t)=>n+t.contactGains,0),m.telemetry.turnovers,'actual gain contacts differ from engine turnover events');
  derived=derive(diagnostics);obs.detach();assert.deepEqual(snapshot(m),activeState,'detach changed engine values');assert.deepEqual(descriptorContract(m),descriptors,'detach did not restore exact own-method/property contract');
 }
 return {summary:{end:m.time,completed:m.done,score:[...m.score],shots:[...m.shots],passes:[...m.passes],completedPasses:[...m.completed],turnovers:m.telemetry.turnovers,abortedKicks:m.telemetry.abortedKicks||0,finalSeed:m.seed,finalOwner:m.owner?.id??null,finalPhase:m.phase,finalBall:{...m.ball},maxPlayerStep,telemetry:structuredClone(m.telemetry)},...(obs?{diagnostics,derived}:{}),state:snapshot(m)};
}
const sourceHashes={baseline:hash(sources.baseline),...initialFileHashes};
const report={generatedAt:new Date().toISOString(),runtime:{node:process.version,v8:process.versions.v8,platform:process.platform,arch:process.arch},seconds,scenarioFilter:selected,engineFilter,sources:sourceHashes,definitions:{baseline:'Exact published stable stage8 engine e16642b5, retained from commit 68d0ea7.',current:'Exact stage9 review engine b29a8f9b from commit c64270f; diagnostics do not change its decisions or physics.',method:'The shared attach() observer forwards actual calls and records actual event boundaries. It never invokes extra AI/planning/keeper/forecast queries. Each observed run is compared to an independent plain engine run and an observed deterministic replay. Non-enumerable forwarding hooks are removed before final complete-state comparison, and exact own-property descriptor/method contracts must be restored. Active-state value snapshots before/after report and detach must also remain equal.',time:'Observer clocks allocate each real fixed-step delta using the state at step start. In-play plus dead-ball equals the observed simulated window; controlled, flight and loose categories partition in-play exposure. Restart and goal pauses partition dead time. Real elapsed wall time and simulation speed controls are not denominators.',stages:'Marginal stage presence is not an ordered funnel. The shared observer definitions specify contact/control confirmation, pressure eligibility, frozen/current opponent-screen line crossing, actual final-third/box control and physical shot release. Planned destinations and shot windup do not grant progress. At-start advanced territory is recorded separately.',orderedGainCohort:'Only confirmed-control episodes with actual gain origin enter the derived gain paths. Already-high gains are separated. Four paths split initial pressure required/not-required and initial eligible opponent screen/no-screen. N/A nodes are explicitly omitted from the corresponding path, never counted as achieved. Progression milestones must have nondecreasing actual timestamps and entryMode other than at-start; simultaneous milestones at one actual contact are permitted. Restart/rebound/aerial/left-censored origins remain available in marginal and per-episode reports.',transitionRates:'Each strict first-milestone transition partitions entrants into reached, ended without next, already order-incompatible first milestone, pending without next and right-censored without next. An existing next milestone before the previous one (or labelled at-start) is a resolved incompatibility with this observed first-milestone path, even while the live attack remains pending. It is not an attack failure verdict and does not describe later re-entries. observedWindowRate is reached/entrants, not a final conversion estimate. resolvedOnlyRate excludes pending/censored non-arrivals but includes resolved first-milestone incompatibilities; it is a conditional descriptive rate, not an unbiased survival or causal estimate. Zero denominators are null.',endReasons:'Actual terminal events and the latest reached stage are separate from support/hold/pass/box-run evidence. Evidence does not establish that a wait or choice was unnecessary; no counterfactual decision was simulated.',coverage:'Natural aerial/keeper opportunities and outcomes are retained exactly as the shared observer defines them. Zero observed opportunities do not imply an absent or broken feature. Controlled coverage fixtures are a separate dataset, not added to natural success rates.',limits:'Eight short synthetic configurations, two deterministic engine versions and synthetic rosters; neither real squad quality, whole-season balance, long-match fatigue nor general football quality is certified. Engine results must remain actual and unchanged by observation.'},runs:[],verification:{observerConsistency:{},deterministicReplay:{},descriptorRestoration:{},stateHashes:{}}};
for(const name of Object.keys(versions))for(const key of Object.keys(report.verification))report.verification[key][name]={};
for(const scenario of scenarios){
 const cfg=config(scenario),row={scenario,config:cfg};
 for(const [name,C]of Object.entries(versions)){
  process.stderr.write(`${scenario.id}/${name}: observed start\n`);const observed=run(new C(cfg),true),observedHash=stateHash(observed.state);
  process.stderr.write(`${scenario.id}/${name}: plain start\n`);const plain=run(new C(cfg),false);assert.deepEqual(observed.summary,plain.summary,`${name}/${scenario.id}: observer changed outcomes`);assert.deepEqual(observed.state,plain.state,`${name}/${scenario.id}: observer changed complete engine state`);assert.equal(observedHash,stateHash(plain.state));
  process.stderr.write(`${scenario.id}/${name}: replay start\n`);const replay=run(new C(cfg),true);assert.deepEqual(observed,replay,`${name}/${scenario.id}: deterministic observer/engine replay differs`);assert.equal(observedHash,stateHash(replay.state));
  const {state,...result}=observed;row[name]=result;report.verification.observerConsistency[name][scenario.id]=true;report.verification.deterministicReplay[name][scenario.id]=true;report.verification.descriptorRestoration[name][scenario.id]=true;report.verification.stateHashes[name][scenario.id]=observedHash;
  process.stderr.write(`${scenario.id}/${name}: verified ${result.summary.score.join('-')}, shots ${result.summary.shots.join('/')}, in-play ${result.diagnostics.clock.inPlaySeconds.toFixed(3)}s\n`);
 }
 report.runs.push(row);
}
for(const [key,file]of Object.entries(sourceFiles))assert.equal(fileHash(file),sourceHashes[key],`source changed during profiling: ${file}`);
assert.equal(hash(sourceAt(baselineFile)),sourceHashes.baseline,'retained baseline changed during profiling');
const output=opt('--output',null),json=JSON.stringify(report,null,2)+'\n';if(output){fs.mkdirSync(path.dirname(path.resolve(output)),{recursive:true});fs.writeFileSync(output,json);}else process.stdout.write(json);
