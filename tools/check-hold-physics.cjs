#!/usr/bin/env node
'use strict';
// Source preservation and a reproducible mixed-prefix natural decision fork.
// The prefix intentionally uses stage5 to149s, then stage6 to150.433333s.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),Module=require('node:module'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const readStage=n=>zlib.gunzipSync(fs.readFileSync(path.join(root,`docs/validation/baselines/stage${n}-football-sim.js.gz`))).toString();
const sources={stage5:readStage(5),baseline:readStage(6),current:fs.readFileSync(path.join(root,'football-sim.js'),'utf8')};
assert.equal(hash(sources.stage5),'7038778922feb9f8f24389003b5ddf92fb8c0790280af84ae9818a04198acf60');
assert.equal(hash(sources.baseline),'108d47253d775de6638460d5fa90dd6bbe2ab2e1e066b581e17591350c4917b6');
function load(source,label){const m=new Module(path.join(root,label),module);m.filename=path.join(root,label);m.paths=module.paths;m._compile(source,m.filename);return m.exports;}
const engines={stage5:load(sources.stage5,'hold-physics-stage5.js'),baseline:load(sources.baseline,'hold-physics-stage6.js'),current:load(sources.current,'hold-physics-current.js')};
const methods=e=>Object.fromEntries(Object.getOwnPropertyNames(e.Match.prototype).filter(k=>k!=='constructor').map(k=>[k,hash(e.Match.prototype[k].toString())]));
const oldMethods=methods(engines.baseline),newMethods=methods(engines.current),changed=Object.keys(oldMethods).filter(k=>k in newMethods&&oldMethods[k]!==newMethods[k]),added=Object.keys(newMethods).filter(k=>!(k in oldMethods)),removed=Object.keys(oldMethods).filter(k=>!(k in newMethods));
assert.deepEqual(changed,['step']);assert.deepEqual(added,['postReceiveHold']);assert.deepEqual(removed,[]);
const protectedMethods=['move','effort','controlPreparation','preparationContext','acquire','firstControlContact','dribbleTouch','release','doTackle','tackleAccess','startKick','kickStep','contactPoint','integrateBall','ballStep','choose','startCarry'];
for(const name of protectedMethods)assert.equal(oldMethods[name],newMethods[name],name);
const physics=Object.keys(engines.baseline.BallPhysics).map(key=>{const before=engines.baseline.BallPhysics[key],after=engines.current.BallPhysics[key],render=value=>typeof value==='function'?value.toString():JSON.stringify(value);assert.equal(render(before),render(after),key);return {key,sha256:hash(render(after)),unchanged:true};});
const cfg=JSON.parse(fs.readFileSync(path.join(root,'docs/validation/reception-facing-counter-fork.json'),'utf8')).config;
const first=new engines.stage5.Match(cfg);for(let tick=0;tick<149*60;tick++)first.step();
const prefix=Object.assign(Object.create(engines.baseline.Match.prototype),structuredClone(first));
for(let tick=0;tick<86;tick++)prefix.step();
const snapshot=structuredClone(prefix),clone=(Engine,state=snapshot)=>Object.assign(Object.create(Engine.Match.prototype),structuredClone(state));
const plainState=m=>{const state={...m};for(const k of Object.keys(state))if(typeof state[k]==='function')delete state[k];return structuredClone(state);};
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
function run(engine,observe){
 const m=clone(engine),events=[],changes=[];let firstOpponent=null,maxPlayerStep=0;
 if(observe){
  const acquire=m.acquire,release=m.release;
  m.acquire=function(...args){const success=acquire.apply(this,args);if(success)events.push({type:'acquire',time:this.time,player:args[0].id,team:args[0].team});return success;};
  m.release=function(...args){const k=this.kick,out=release.apply(this,args);events.push({type:'release',time:this.time,from:k.p.id,target:k.target?.id??null,kind:k.kind});return out;};
  if(engine.Match.prototype.postReceiveHold)m.postReceiveHold=function(p,choice){
   const before=plainState(this),ownRandom=Object.hasOwn(this,'random'),random=this.random,ownPlan=Object.hasOwn(this,'plan'),plan=this.plan,rival=this.field(1-p.team)[0],hadTarget=rival&&this.targets.has(rival),oldTarget=rival&&this.targets.get(rival),hidden={};
   Object.defineProperty(hidden,'x',{get(){throw Error('Hidden opponent command was read');}});
   this.random=()=>{throw Error('Live RNG was read');};this.plan=()=>{throw Error('Future tactical plan was run');};if(rival)this.targets.set(rival,hidden);
   let out;try{out=engine.Match.prototype.postReceiveHold.call(this,p,choice);}finally{if(ownRandom)this.random=random;else delete this.random;if(ownPlan)this.plan=plan;else delete this.plan;if(rival){if(hadTarget)this.targets.set(rival,oldTarget);else this.targets.delete(rival);}}
   assert.deepEqual(plainState(this),before,'decision query mutated live match state');
   if(out!==choice)changes.push({time:this.time,player:p.id,requested:structuredClone(choice),returned:structuredClone(out),queryStateEquality:true,liveRngGuard:true,futurePlanGuard:true,hiddenOpponentCommandGuard:true});
   return out;
  };
 }
 for(let tick=0;tick<300&&!m.done;tick++){
  const old=m.players.map(p=>({x:p.x,z:p.z}));m.step();
  for(const [i,p]of m.players.entries()){assert([p.x,p.z,p.vx,p.vz,p.face].every(Number.isFinite));maxPlayerStep=Math.max(maxPlayerStep,distance(p,old[i]));}
  assert(Object.values(m.ball).every(Number.isFinite));
  if(!firstOpponent&&m.owner?.team===1-snapshot.owner.team)firstOpponent={time:m.time,player:m.owner.id,team:m.owner.team};
 }
 assert(maxPlayerStep<=.15);return {state:plainState(m),summary:{end:m.time,firstOpponent,finalOwner:m.owner?.id??null,finalBall:{...m.ball},score:[...m.score],maxPlayerStep,events,changes,telemetry:structuredClone(m.telemetry)}};
}
const branches={};
for(const name of ['baseline','current']){const observed=run(engines[name],true),plain=run(engines[name],false);assert.deepEqual(observed.state,plain.state,`${name}: observer changed engine state`);branches[name]={...observed.summary,observerConsistency:true};}
assert.equal(branches.current.changes.length,1);assert.equal(branches.current.changes[0].player,11);assert(branches.current.changes[0].returned.holdContinuation);
assert.equal(branches.baseline.firstOpponent.player,4);
const report={generatedAt:new Date().toISOString(),sources:{stage5:hash(sources.stage5),baseline:hash(sources.baseline),current:hash(sources.current),check:hash(fs.readFileSync(__filename))},changedExistingMatchMethods:changed,addedMatchMethods:added,removedMatchMethods:removed,unchangedMatchMethods:Object.keys(oldMethods).filter(k=>oldMethods[k]===newMethods[k]),unchangedMatchMethodCount:Object.keys(oldMethods).filter(k=>oldMethods[k]===newMethods[k]).length,protectedMethods:Object.fromEntries(protectedMethods.map(k=>[k,{sha256:newMethods[k],unchanged:true}])),ballPhysics:physics,naturalFork:{provenance:'Complete exact stage5 engine from kickoff to149s using the retained counter-fork config, followed by exact stage6 for86 steps (to150.433333333345s). Both branches start from the identical complete state, including Map references and RNG. This is explicitly a mixed prefix, not a complete stage6 kickoff match.',config:cfg,at:snapshot.time,initialSeed:snapshot.seed,initialOwner:snapshot.owner.id,initialPlayer:structuredClone(snapshot.players[11]),initialBall:{...snapshot.ball},followSeconds:5,branches},verified:true};
const index=process.argv.indexOf('--output'),output=index<0?path.join(root,'docs/validation/hold-continuation-physics-check.json'):path.resolve(process.argv[index+1]);fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({output,changed,added,unchanged:report.unchangedMatchMethodCount,firstOpponent:Object.fromEntries(Object.entries(branches).map(([k,b])=>[k,b.firstOpponent])),verified:true}));
