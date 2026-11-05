#!/usr/bin/env node
'use strict';
// Stage 1 is an exact retained source, not HEAD (which still names v1.27).
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),zlib=require('node:zlib'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const v8=require('node:v8');
const root=path.resolve(__dirname,'..');const T=require('../tactics');
const opt=(key,def)=>{const at=process.argv.indexOf(key);return at<0?def:process.argv[at+1];};
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const baselinePath=path.resolve(opt('--baseline-file',path.join(root,'docs/validation/baselines/stage1-football-sim.js.gz')));
const bytes=fs.readFileSync(baselinePath),sources={baseline:(baselinePath.endsWith('.gz')?zlib.gunzipSync(bytes):bytes).toString(),current:fs.readFileSync(path.join(root,'football-sim.js'),'utf8')};
function load(source,label){const mod=new Module(path.join(root,label),module);mod.filename=path.join(root,label);mod.paths=module.paths;mod._compile(source,mod.filename);return mod.exports.Match;}
const versions=Object.fromEntries(Object.entries(sources).map(([key,source])=>[key,load(source,`support-${key}.js`)]));
const preset=id=>{const p=T.presets.find(p=>p.id===id);assert(p);return p.tactics;};
const starters=[8,9,10,7,5,6,4,2,3,1,0];
const roster=strength=>Array.from({length:11},(_,id)=>({id,name:`Synthetic ${id}`,rating:strength,passing:strength,shooting:strength,tackling:strength,vision:strength,composure:strength,dribbling:strength,pace:strength,agility:strength,fitness:92,preferredFoot:id%2?'right':'left',weakFoot:strength-12}));
function config(s){return {seed:s.seed,starters,formation:s.formation||'4-3-3',awayFormation:'4-2-3-1',matchMinutes:5,players:roster(s.strength||82),tactics:{...preset(s.home||'balanced'),...s.change},awayTactics:preset(s.away||'counter')};}
const mode=opt('--mode','matrix'),seconds=Number(opt('--seconds','300')),follow=Number(opt('--follow-seconds','8'));
assert(['matrix','fork','controlled'].includes(mode));assert(seconds>0&&seconds<=5400&&Number.isFinite(seconds));assert(follow>0&&follow<=30&&Number.isFinite(follow));
const dist=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
function observe(m,detailed=false){
 const stats={receivesByTeam:[0,0],safeHelperByTeam:[0,0],receivesWithSafeHelperByTeam:[0,0],helperDistanceSumByTeam:[0,0],helperDistanceCountByTeam:[0,0],receives:0,intendedReceives:0,receivesWithArrivalPlan:0,safeOptionsAtReceive:0,safeHelperOptionsAtReceive:0,receivesWithSafeHelper:0,helperDistanceSum:0,helperDistanceCount:0,flightSamples:0,receiverCentredSamples:0,flightHelperTargets:0};
 const events=[],trace=[],passes=[0,1].map(()=>({count:0,totalDistance:0,forward:0,backward:0,lateral:0}));const acquire=m.acquire,release=m.release,plan=m.plan,choose=m.choose,tackle=m.doTackle;
 m.choose=function(p){const out=choose.call(this,p);if(detailed)events.push({type:'choose',time:this.time,id:p.id,kind:out.kind,target:out.q?.id??null,point:out.point,hold:!!out.hold,shield:!!out.shield,carryTime:p.carryTime,ballGap:dist(p,this.ball),pressure:Math.min(30,...this.field(1-p.team).map(q=>dist(q,p))),support:[...(this.supportPlans[p.team]?.points||[])].map(([id,point])=>({id,readyDistance:dist(this.players.find(p=>p.id===id),point)}))});return out;};
 m.doTackle=function(p,carrier){const before=this.telemetry.duels,out=tackle.call(this,p,carrier);if(detailed&&this.telemetry.duels>before)events.push({type:'duel',time:this.time,id:p.id,carrier:carrier.id,retains:this.owner===carrier});return out;};
 m.acquire=function(p){
  const f=this.flight,sp=this.supportPlans[p.team],ids=new Set(sp?.points?.keys()||[]),out=acquire.call(this,p);
  if(out&&f&&f.from.team===p.team&&f.from!==p){
   const options=this.passOptions(p).filter(o=>o.kind==='pass'&&o.risk<.35&&o.arrivalRisk<.65&&o.space>2.4),helpers=options.filter(o=>ids.has(o.q.id));
   stats.receivesByTeam[p.team]++;stats.safeHelperByTeam[p.team]+=helpers.length;stats.receivesWithSafeHelperByTeam[p.team]+=+(helpers.length>0);stats.receives++;stats.intendedReceives+=+(f.target===p);stats.receivesWithArrivalPlan+=+(sp?.ownerId===p.id&&!!sp.arrival);stats.safeOptionsAtReceive+=options.length;stats.safeHelperOptionsAtReceive+=helpers.length;stats.receivesWithSafeHelper+=+(helpers.length>0);
   for(const id of ids){const q=this.players.find(q=>q.id===id&&q.active);if(q&&q!==p){stats.helperDistanceSum+=dist(p,q);stats.helperDistanceCount++;stats.helperDistanceSumByTeam[p.team]+=dist(p,q);stats.helperDistanceCountByTeam[p.team]++;}}
   if(detailed)events.push({type:'receive',time:this.time,id:p.id,from:f.from.id,intended:f.target?.id,planOwner:sp?.ownerId??null,helpers:[...ids],safeOptions:options.map(o=>o.q.id),safeHelpers:helpers.map(o=>o.q.id),receiveClock:p.receiveClock,mode:p.receiveMode});
  }else if(out&&detailed)events.push({type:'acquire',time:this.time,id:p.id,team:p.team});
  return out;
 };
 m.release=function(){const k=this.kick,count=this.passes[k.p.team]+this.shots[k.p.team],passCount=this.passes[k.p.team],origin={...this.ball},out=release.call(this);if(this.passes[k.p.team]>passCount){const a=passes[k.p.team],dx=(k.point.x-origin.x)*(k.p.team===0?1:-1);a.count++;a.totalDistance+=dist(k.point,origin);a[dx>2?'forward':dx< -2?'backward':'lateral']++;}if(detailed&&this.passes[k.p.team]+this.shots[k.p.team]>count)events.push({type:'release',time:this.time,from:k.p.id,target:k.target?.id??null,kind:k.kind});return out;};
 m.plan=function(){const out=plan.call(this),f=this.flight;if(f?.target&&f.from.team===f.target.team){const sp=this.supportPlans[f.from.team];stats.flightSamples++;stats.receiverCentredSamples+=+(sp?.ownerId===f.target.id);stats.flightHelperTargets+=sp?.points.size||0;if(detailed)trace.push({time:this.time,flightId:f.id,target:f.target.id,ball:{x:this.ball.x,z:this.ball.z},planOwner:sp?.ownerId??null,lead:sp?.arrival?.lead??null,helpers:[...(sp?.points||[])].map(([id,point])=>({id,target:{x:point.x,z:point.z},distanceToReceiver:dist(point,f.target),actualDistance:dist(this.players.find(p=>p.id===id),f.target),command:this.targets.get(this.players.find(p=>p.id===id))?.state}))});}return out;};
 return {stats,events,trace,passes};
}
function run(m,duration,detailed=false){
 const seen=observe(m,detailed),start=m.time,initialSeed=m.seed;let maxStep=0,previous=m.players.map(p=>({x:p.x,z:p.z})),firstOpponent=null;
 const own=m.owner?.team??m.flight?.from.team??0,shape=[0,1].map(()=>({samples:0,width:0,line:0}));
 for(let tick=0;tick<Math.round(duration*60)&&!m.done;tick++){
  m.step();for(const [i,p]of m.players.entries()){assert([p.x,p.z,p.vx,p.vz,p.face].every(Number.isFinite));maxStep=Math.max(maxStep,dist(p,previous[i]));previous[i]={x:p.x,z:p.z};}
  assert(Object.values(m.ball).every(Number.isFinite));if(tick%60===0&&!m.restart&&!m.kick?.restartContext&&!m.goalPause)for(const t of [0,1]){const field=m.field(t),defs=field.filter(p=>p.role==='DEF'),a=shape[t];a.samples++;a.width+=Math.max(...field.map(p=>p.z))-Math.min(...field.map(p=>p.z));a.line+=defs.reduce((v,p)=>v+p.x*(t===0?1:-1),0)/(defs.length||1);}
  if(m.owner&&m.owner.team!==own&&firstOpponent===null)firstOpponent={time:m.time,id:m.owner.id,team:m.owner.team};
 }
 if(duration===m.duration)assert(m.done,'full match must finish');
 assert(maxStep<=.15,`step ${maxStep}`);assert.deepEqual(m.score,[0,1].map(t=>m.events.filter(e=>e.type==='goal'&&e.team===t).length));
 return {start,end:m.time,completed:m.done,initialSeed,finalSeed:m.seed,score:[...m.score],shots:[...m.shots],passes:[...m.passes],completedPasses:[...m.completed],firstOpponent,finalOwner:m.owner?.id??null,finalPhase:m.phase,finalRestart:m.restart?{kind:m.restart.kind,team:m.restart.team,spot:{...m.restart.spot}}:null,finalBall:{...m.ball},finalFlight:m.flight?{kind:m.flight.kind,age:m.flight.age,target:m.flight.target?.id}:null,maxStep,stats:seen.stats,passMetrics:seen.passes.map(a=>({...a,meanDistance:a.totalDistance/(a.count||1)})),shape:shape.map(a=>({samples:a.samples,meanWidth:a.width/(a.samples||1),meanDefenceLine:a.line/(a.samples||1)})),meanHelperDistance:seen.stats.helperDistanceSum/(seen.stats.helperDistanceCount||1),telemetry:JSON.parse(JSON.stringify(m.telemetry)),...(detailed?{events:seen.events,trace:seen.trace}:{})};
}
const report={generatedAt:new Date().toISOString(),mode,sources:{baseline:hash(sources.baseline),current:hash(sources.current),tactics:hash(fs.readFileSync(path.join(root,'tactics.js'))),observer:hash(fs.readFileSync(__filename))},definitions:{baseline:'Exact published stage1 source cb35f481; retained gzip defaults to docs/validation/baselines/stage1-football-sim.js.gz.',safeHelper:'Existing pass option at actual reception: normal pass, risk<.35, arrivalRisk<.65, receiver space>2.4 and teammate is in current support plan. A read is not an executed or completed pass.',flightTargets:'Commanded destinations; actual helper distances at reception are recorded separately.',limits:'Small synthetic sample, no hidden opponent orders/RNG forcing, scores are actual event goals. Natural branches share complete stage1 state then diverge normally.'}};
if(mode==='matrix'){
 const scenarios=[{id:'balanced21',seed:21},{id:'press42',seed:42,away:'press'},{id:'narrow21',seed:21,change:{width:'narrow'}},{id:'wide21',seed:21,change:{width:'wide'}},{id:'short42',seed:42,away:'press',change:{passing:'short'}},{id:'direct42',seed:42,away:'press',change:{passing:'direct'}},{id:'weak442-77',seed:77,strength:65,formation:'4-4-2',home:'possession',away:'press'},{id:'strong352-21',seed:21,strength:91,formation:'3-5-2',home:'counter',away:'wide'}];
 report.seconds=seconds;report.runs=[];for(const s of scenarios){const cfg=config(s);cfg.matchMinutes=seconds>300?90:5;const row={scenario:s,config:cfg};for(const[name,C]of Object.entries(versions))row[name]=run(new C(cfg),seconds);report.runs.push(row);process.stderr.write(`${s.id} ${row.baseline.score}->${row.current.score}\n`);}
 report.replay={};for(const[name,C]of Object.entries(versions)){const a=run(new C(report.runs[0].config),seconds);assert.deepEqual(a,report.runs[0][name]);report.replay[name]=true;}
}else{
 let state;
 if(mode==='fork'){
  const at=Number(opt('--at','3652.25'));assert(at>=0&&at<5400);const cfg={seed:77,starters,formation:'4-3-3',matchMinutes:90,tactics:preset('press')};
  const saved=opt('--snapshot-file',null);
  if(saved){const snapshot=v8.deserialize(fs.readFileSync(saved));assert.equal(snapshot.baselineHash,hash(sources.baseline));assert.equal(snapshot.at,at);state=snapshot.state;}else{const base=new versions.baseline(cfg);for(let i=0;i<Math.round(at*60);i++)base.step();state=structuredClone(base);}
  const save=opt('--save-snapshot',null);if(save)fs.writeFileSync(save,v8.serialize({baselineHash:hash(sources.baseline),at,state}));
  report.config=cfg;report.at=state.time;
 }else{
  const base=new versions.baseline({seed:21,tactics:{passing:'short',playstyle:'possession'}});base.restart=null;base.time=10;base.phase='open';base.planClock=0;
  for(const p of base.players){p.vx=p.vz=p.speed=0;p.duelRecovery=0;if(p.team===1){p.x=38;p.z=p.index*5-25;}}
  const[from,receiver,anchor,helper]=[base.players[3],base.players[5],base.players[4],base.players[0]];
  for(const[p,x,z]of [[from,-15,0],[receiver,2,8],[anchor,-14,-11],[helper,-7,13]])Object.assign(p,{x,z});Object.assign(helper,{role:'MID',homeX:0,homeZ:13});
  base.owner=from;base.lastTeam=0;base.lastTouch=from;base.ball={x:-14,y:.11,z:0,vx:15,vy:0,vz:6};
  base.supportUnit(0,from,[from,receiver,anchor,helper],anchor,null,null,null,null,38);
  base.owner=null;base.flight={id:7,from,target:receiver,kind:'pass',age:.3,point:{x:2,z:8},offsidePlayers:[]};base.ball={x:-5,y:.11,z:5,vx:15,vy:0,vz:6};
  state=structuredClone(base);report.controlled='Synthetic same-state rolling pass; all following commands/movement/duels/contacts use the normal engine. Fourth midfielder is synthetic, no real player data added.';
 }
 report.branches={};for(const[name,C]of Object.entries(versions)){const m=Object.assign(Object.create(C.prototype),structuredClone(state));report.branches[name]=run(m,follow,true);}
 assert.equal(report.branches.baseline.initialSeed,report.branches.current.initialSeed);
}
const output=opt('--output',null),json=JSON.stringify(report,null,2)+'\n';if(output){fs.mkdirSync(path.dirname(path.resolve(output)),{recursive:true});fs.writeFileSync(output,json);}else process.stdout.write(json);
