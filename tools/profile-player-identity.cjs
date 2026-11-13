#!/usr/bin/env node
'use strict';
// Real fixed-step games; passive diagnostics never request extra AI decisions.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const zlib=require('node:zlib'),crypto=require('node:crypto'),assert=require('node:assert/strict'),v8=require('node:v8'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const option=(name,fallback)=>{const i=process.argv.indexOf(name);return i<0?fallback:process.argv[i+1];};
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const seconds=Number(option('--seconds','300')),filter=option('--scenario',null);
assert(Number.isFinite(seconds)&&seconds>=1&&seconds<=5400,'seconds must be 1–5400');
const paths=['football-sim.js','player-model.js','player-model-profiles.json','club-data.js','tactics.js','player-perception.js','team-intent.js','attack-diagnostics.js',path.relative(root,__filename).replaceAll(path.sep,'/')];
const sources=Object.fromEntries(paths.map(p=>[p,hash(fs.readFileSync(path.join(root,p)))]));
const baselinePath='docs/validation/baselines/stage9-football-sim.js.gz';
const oldSource=zlib.gunzipSync(fs.readFileSync(path.join(root,baselinePath))).toString();
const baselineSHA256=hash(oldSource);
assert.equal(baselineSHA256,'b29a8f9b49638ec6559bc58df6b9504400eaaaf3b44bd14439d4643c3bd394f3');
function compile(source,label){const filename=path.join(root,label),m=new Module(filename,module);m.filename=filename;m.paths=module.paths;m._compile(source,filename);return m.exports.Match;}
const versions={baseline:compile(oldSource,'identity-baseline.js'),current:compile(fs.readFileSync(path.join(root,'football-sim.js'),'utf8'),'identity-current.js')};
const C=require('../club-data'),P=require('../player-model'),T=require('../tactics'),D=require('../attack-diagnostics');
const preset=id=>T.presets.find(p=>p.id===id).tactics;
const scenarios=[
 {id:'balanced21',seed:21},
 {id:'press42',seed:42,away:'press'},
 {id:'narrow21',seed:21,change:{width:'narrow'}},
 {id:'wide21',seed:21,change:{width:'wide'}},
 {id:'short42',seed:42,away:'press',change:{passing:'short'}},
 {id:'direct42',seed:42,away:'press',change:{passing:'direct'}},
 {id:'weak442-77',seed:77,rating:65,formation:'4-4-2',home:'possession',away:'press'},
 {id:'strong352-21',seed:21,rating:91,formation:'3-5-2',home:'counter',away:'wide'}
].filter(s=>!filter||filter.split(',').includes(s.id));
assert(scenarios.length,'unknown scenarios');
const config=s=>{
 const players=C.createRoster().map(p=>({...p,...(s.rating?{rating:s.rating}:{})})),formation=s.formation||'4-3-3';
 const awayFormation='4-2-3-1',awayPlayers=P.demoTeam(1,awayFormation);
 return {seed:s.seed,players,starters:C.reorder(C.starters,formation,players),formation,
  awayPlayers,awayStarters:awayPlayers.map(p=>p.id),awayFormation,opponentSource:'demo',
  matchMinutes:seconds>900?90:seconds>300?15:5,
  tactics:{...preset(s.home||'balanced'),...s.change},awayTactics:preset(s.away||'counter')};
};
function stateHash(value){
 const seen=new Map(),encode=v=>{
  if(v===null)return ['null'];if(v===undefined)return ['undefined'];
  if(typeof v==='number')return ['number',Number.isNaN(v)?'NaN':v===Infinity?'Infinity':v===-Infinity?'-Infinity':Object.is(v,-0)?'-0':v];
  if(typeof v!=='object')return [typeof v,String(v)];
  if(seen.has(v))return ['ref',seen.get(v)];const id=seen.size;seen.set(v,id);
  if(v instanceof Map)return ['map',id,[...v].map(([k,x])=>[encode(k),encode(x)])];
  if(v instanceof Set)return ['set',id,[...v].map(encode)];
  return [Array.isArray(v)?'array':'object',id,Object.keys(v).sort().map(k=>[k,encode(v[k])])];
 };return hash(JSON.stringify(encode(value)));
}
const snapshot=m=>v8.deserialize(v8.serialize(m));
function run(M,cfg,observed){
 const m=new M(structuredClone(cfg)),obs=observed?D.attach(m,{maxEpisodes:100000}):null;
 const previous=m.players.map(p=>({x:p.x,z:p.z}));let maxPlayerStep=0;
 for(let i=0;i<Math.round(seconds*60)&&!m.done;i++){
  if(obs)obs.step(1/60);else m.step(1/60);
  m.players.forEach((p,j)=>{
   assert(['x','z','vx','vz','face','stamina'].every(k=>Number.isFinite(p[k])),`nonfinite player ${p.id}`);
   if(!p.referee)assert(Number.isFinite(p.energy),`nonfinite energy ${p.id}`);
   maxPlayerStep=Math.max(maxPlayerStep,Math.hypot(p.x-previous[j].x,p.z-previous[j].z));previous[j]={x:p.x,z:p.z};
  });
  assert(['x','y','z','vx','vy','vz'].every(k=>Number.isFinite(m.ball[k])),'nonfinite ball');
 }
 assert(maxPlayerStep<=.15,`step too large: ${maxPlayerStep}`);
 assert.deepEqual(m.score,[0,1].map(team=>m.events.filter(e=>e.type==='goal'&&e.team===team).length));
 if(seconds===m.duration)assert.equal(m.done,true);
 let diagnostic=null;
 if(obs){
  const active=snapshot(m);diagnostic=obs.report();assert.deepEqual(obs.report(),diagnostic);assert.deepEqual(snapshot(m),active,'query modified game');
  assert.equal(diagnostic.valid,true,JSON.stringify(diagnostic.errors));
  assert.equal(diagnostic.truncatedEpisodes||0,0);
  const c=diagnostic.clock;
  assert(Math.abs(c.observedSeconds-m.time)<1e-7);
  assert(Math.abs(c.observedSeconds-c.inPlaySeconds-c.deadBallSeconds)<1e-7);
  assert.equal(c.unobservedSeconds,0);
  for(const team of [0,1]){
   assert.equal(diagnostic.teams[team].shots,m.shots[team]);
   assert.equal(diagnostic.teams[team].passes.attempted,m.passes[team]);
   assert.equal(diagnostic.teams[team].passes.completed,m.completed[team]);
  }
  assert.equal(diagnostic.teams.reduce((n,t)=>n+t.contactGains,0),m.telemetry.turnovers);
  obs.detach();assert.deepEqual(snapshot(m),active,'detach modified game');
 }
 return {state:snapshot(m),summary:{time:m.time,done:m.done,score:[...m.score],shots:[...m.shots],passes:[...m.passes],completedPasses:[...m.completed],turnovers:m.telemetry.turnovers,abortedKicks:m.telemetry.abortedKicks||0,maxPlayerStep,finalSeed:m.seed},diagnostic};
}
const report={generatedAt:new Date().toISOString(),version:1,seconds,scenarioCount:scenarios.length,runtime:{node:process.version,v8:process.versions.v8,platform:process.platform,arch:process.arch},sources,baseline:{path:baselinePath,decompressedSHA256:baselineSHA256,publicationCommit:'0777710e9635a2fbb1e51f399705d6b37556ec2d'},definitions:{
 method:'Each engine/scenario runs observed, plain and observed replay with identical raw configuration and seed. The passive attach observer forwards actual calls; no extra decision, pass, movement forecast or keeper query is requested. Complete detached state is compared, not only scores. Report reads are idempotent and leave live values unchanged.',
 inputs:'Both versions receive the current authored fictional seed roster for team0 and the same explicit demo roster for team1. The old engine ignores awayPlayers and generates its own synthetic team1; its old own-team interpretation also ignores form/position effects. Therefore this comparison measures the overall player-contract change, not an isolated attribute effect, and is not a replay of the earlier stage10 input matrix.',
 clocks:'Fixed 1/60 second game steps. Rates use actual observed in-play exposure, not nominal match minutes or wall-clock runtime. Shots/pass releases/completions and gains agree with native engine counters.',
 profiles:'Raw home profile includes real records only when supplied externally; these scenarios intentionally use authored fictional/demonstration data. Equal overall profile behavior is checked independently by player-identity-integration tests.',
 limits:'Eight short deterministic configurations are descriptive regression coverage. They do not certify real football balance, general skill calibration or season outcomes. Differences do not establish that new behavior is better. Zero observed events do not establish broken features.'
 },runs:[],totals:{},verification:{observerConsistent:true,deterministicReplay:true,finite:true,clockAndEventsConsistent:true,queryReadOnly:true}};
const ratio=(n,d)=>d>0?n/d:null;
function finish(){
 for(const name of Object.keys(versions)){
  const rows=report.runs.map(r=>r[name]),sum=f=>rows.reduce((n,r)=>n+f(r),0);
  const totals={observedSeconds:sum(r=>r.time),inPlaySeconds:sum(r=>r.clock.inPlaySeconds),shots:sum(r=>r.shots.reduce((a,b)=>a+b,0)),passes:sum(r=>r.passes.reduce((a,b)=>a+b,0)),completedPasses:sum(r=>r.completedPasses.reduce((a,b)=>a+b,0)),turnovers:sum(r=>r.turnovers),abortedKicks:sum(r=>r.abortedKicks),attackEpisodes:sum(r=>r.attackEpisodes)};
  totals.shotsPerTenInPlayMinutes=ratio(totals.shots*600,totals.inPlaySeconds);totals.passCompletion=ratio(totals.completedPasses,totals.passes);report.totals[name]=totals;
 }
 for(const p of paths)assert.equal(hash(fs.readFileSync(path.join(root,p))),sources[p],`source changed while profiling: ${p}`);
 assert.equal(hash(zlib.gunzipSync(fs.readFileSync(path.join(root,baselinePath)))),baselineSHA256);
 const output=path.resolve(option('--output',path.join(root,'docs/validation/player-identity-natural.json')));
 fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
 process.stdout.write(JSON.stringify({output,scenarioCount:report.scenarioCount,seconds,totals:report.totals,verification:report.verification})+'\n');
}
const jobs=Number(option('--jobs','3'));
assert(Number.isInteger(jobs)&&jobs>=1&&jobs<=3,'jobs must be 1–3');
if(!process.argv.includes('--worker')&&scenarios.length>1&&jobs>1){
 (async()=>{
  const directory=path.join(root,'work/stage11/natural-profile-workers',sources['tools/profile-player-identity.cjs'].slice(0,12));
  fs.mkdirSync(directory,{recursive:true});
  let next=0;const rows=new Map();
  async function worker(){
   while(next<scenarios.length){
    const scenario=scenarios[next++],output=path.join(directory,scenario.id+'.json'),log=path.join(directory,scenario.id+'.log');
    process.stderr.write(`${scenario.id}: worker start\n`);
    const fd=fs.openSync(log,'w');
    try{
     await new Promise((resolve,reject)=>{
      const child=spawn(process.execPath,[__filename,'--worker','--seconds',String(seconds),'--scenario',scenario.id,'--output',output,'--jobs','1'],{cwd:root,stdio:['ignore',fd,fd]});
      child.once('error',reject);child.once('exit',(code,signal)=>code===0?resolve():reject(Error(`${scenario.id} worker failed code=${code} signal=${signal}; see ${log}`)));
     });
    }finally{fs.closeSync(fd);}
    const one=JSON.parse(fs.readFileSync(output,'utf8'));
    assert.deepEqual(one.sources,sources);assert.deepEqual(one.baseline,report.baseline);assert.equal(one.seconds,seconds);assert.equal(one.scenarioCount,1);
    assert.deepEqual(one.verification,report.verification);assert.equal(one.runs[0].scenario.id,scenario.id);
    rows.set(scenario.id,one.runs[0]);process.stderr.write(`${scenario.id}: worker verified\n`);
   }
  }
  await Promise.all(Array.from({length:Math.min(jobs,scenarios.length)},worker));
  report.runs=scenarios.map(s=>rows.get(s.id));assert.equal(report.runs.length,scenarios.length);finish();
 })().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
 return;
}
for(const scenario of scenarios){
 const cfg=config(scenario),row={scenario,configSHA256:hash(JSON.stringify(cfg))};
 for(const [name,M]of Object.entries(versions)){
  process.stderr.write(`${scenario.id}/${name}: observed\n`);
  const observed=run(M,cfg,true),plain=run(M,cfg,false),replay=run(M,cfg,true);
  assert.deepEqual(observed.summary,plain.summary,`${scenario.id}/${name}: observer changed outcomes`);
  assert.deepEqual(observed.state,plain.state,`${scenario.id}/${name}: observer changed full state`);
  assert.deepEqual(observed,replay,`${scenario.id}/${name}: replay differs`);
  const d=observed.diagnostic;
  row[name]={...observed.summary,clock:d.clock,attackEpisodes:d.episodes.length,teamEpisodes:[0,1].map(team=>d.episodes.filter(e=>e.team===team).length),coverage:d.coverage,
   shotsPerTenInPlayMinutes:ratio(observed.summary.shots.reduce((a,b)=>a+b,0)*600,d.clock.inPlaySeconds),stateSHA256:stateHash(observed.state),verification:{observerConsistent:true,deterministicReplay:true,finite:true,clockAndEventsConsistent:true,queryReadOnly:true}};
  process.stderr.write(`${scenario.id}/${name}: verified shots ${row[name].shots.join('/')} turnover ${row[name].turnovers}, in-play ${d.clock.inPlaySeconds.toFixed(3)}s\n`);
 }
 report.runs.push(row);
}
finish();
