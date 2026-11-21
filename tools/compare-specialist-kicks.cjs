'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process'),Module=require('node:module');
const {Match,BallPhysics}=require('../football-sim');
const Club=require('../club-data');
const dt=1/60,baseRef='254b0c67041490f312fff9c8022ce186cf7e61a9';
const fields={'penalty':'penalty','free-kick':'freeKick','corner':'corner'};
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const round=n=>Number.isFinite(n)?Math.round(n*10000)/10000:null;
const headingDiff=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
function drop(ball){
 const b=BallPhysics.copy(ball);let crossed=false,elapsed=0;
 for(let i=0;i<1400;i++){
  const old={...b};BallPhysics.step(b,1/240);elapsed+=1/240;
  crossed ||= b.y>.13;
  if(crossed && ((old.vy<0&&b.vy>=0)||(b.y<=BallPhysics.radius+1e-6&&b.vy<=0))){
   return {x:round(b.x),z:round(b.z),time:round(elapsed)};
  }
 }
 return null;
}
function config(kind,rating,mode){
 const players=Club.createRoster(),starters=Club.starters.slice(),id=starters[1];
 players[id]={...players[id],[fields[kind]]:rating,preferredFoot:'both'};
 return {seed:21,players,starters,managerKicks:mode==='manager',tactics:{playstyle:'wing'},
  awayTactics:{playstyle:'wing'},rules:{minPlayers:1,periodSeconds:160}};
}
function evaluate(kind,rating,mode,Engine=Match,forceSameControl=false){
 assert(fields[kind]&&[20,94].includes(rating));
 const m=new Engine(config(kind,rating,mode)),p=m.players[1],side=m.direction(0);
 const spot=kind==='corner'?{x:side*51.8,z:-33.8}:{x:side*30,z:side*3};
 m.setRestart(kind,0,spot,p);
 let released=null,keeperQueries=0;
 const oldRelease=m.release,oldKeeper=m.keeper;
 m.release=function(...args){
  const k=this.kick,prior=this.releaseSerial;
  if(forceSameControl){
   assert.equal(mode,'automatic');
   k.managerControl=this.automaticSpecialistControl(k,kind);
  }
  const control=k.managerControl??null;
  const requested=control?.angle??Math.atan2(k.point.z-this.ball.z,k.point.x-this.ball.x);
  const aim={...k.point},before={...this.ball};
  const okay=oldRelease.apply(this,args);
  if(this.releaseSerial>prior){
   const velocity={...this.ball},angle=Math.atan2(velocity.vz,velocity.vx);
   const speed=Math.hypot(velocity.vx,velocity.vz);
   const expected={...velocity,vx:Math.cos(requested)*speed,vz:Math.sin(requested)*speed};
   const land=drop(velocity),ideal=drop(expected);
   released={requestedAngle:requested,aim,control,from:before,velocity,skillUsed:control?.kind?this.managerKickSkill(k.p,control.kind,k.p.kickFoot):
     this.managerKickSkill(k.p,kind,k.p.kickFoot),
    angleError:Math.abs(headingDiff(angle,requested)),landing:land,idealLanding:ideal,
    landingDeviation:land&&ideal?Math.hypot(land.x-ideal.x,land.z-ideal.z):null,
    releaseTime:this.time,seed:this.seed,flightKind:this.flight?.kind};
  }
  return okay;
 };
 m.keeper=function(...args){keeperQueries++;return oldKeeper.apply(this,args);};
 const limit=kind==='penalty'?55:65;
 for(let i=0;i<limit*60&&!released;i++){
  if(m.pendingManagerKick){
   assert.equal(mode,'manager','unexpected manager prompt in automatic scenario');
   const offer=m.pendingManagerKick,goalAngle=Math.atan2(-offer.origin.z,side*52-offer.origin.x);
   const heading=kind==='free-kick'?goalAngle:offer.angle;
   assert(m.resolveManagerKick(offer.id,{angle:heading,power:.72,contactX:0,contactY:0}));
  }else m.step(dt);
  if(m.done)break;
 }
 assert(released,kind+'/'+mode+'/'+rating+' never released a physical kick');
 const beforeEvents=m.events.length,keeperBefore=m.telemetry.keeperCatches||0;
 let keeperDives=0,keeperSet=0;
 const gk=m.players.find(x=>x.team===1&&x.role==='GK');
 for(let i=0;i<180&&!m.done&&!m.restart&&!m.goalPause;i++){
  m.step(dt);
  keeperDives+=gk?.action==='dive'?1:0;
  keeperSet+=gk?.action==='catch-ready'?1:0;
 }
 const after=m.events.slice(beforeEvents);
 return {kind,rating,mode,skill:round(released.skillUsed),
  targetAngle:round(released.requestedAngle),aim:{x:round(released.aim.x),z:round(released.aim.z)},
  velocity:{vx:round(released.velocity.vx),vz:round(released.velocity.vz),vy:round(released.velocity.vy),spin:round(released.velocity.spin||0)},
  rawVelocity:released.velocity,seedAtRelease:released.seed,
  targetDeviationDegrees:round(released.angleError*180/Math.PI),
  firstLanding:released.landing,firstLandingDeviationMeters:round(released.landingDeviation),
  keeper:{checks:keeperQueries,catches:(m.telemetry.keeperCatches||0)-keeperBefore,diveFrames:keeperDives,
   catchPreparationFrames:keeperSet,saves:after.filter(e=>e.type==='save').length,goals:after.filter(e=>e.type==='goal').length},
  flightKind:released.flightKind};
}
function baselineMatch(){
 const source=execFileSync('git',['show',baseRef+':football-sim.js'],{cwd:path.join(__dirname,'..'),encoding:'utf8',maxBuffer:5e6});
 const digest=hash(source);
 assert(source.includes(' managerKickVelocity(k){')&&!source.includes(' specialistKickType(k){'), 'baseline must be the historical manager-only impulse; never compare against an already-unified engine');
 const filename=path.join(__dirname,'../specialist-kick-original.js');
 const mod=new Module(filename,module);mod.filename=filename;mod.paths=Module._nodeModulePaths(path.dirname(filename));
 mod._compile(source,filename);
 return {Match:mod.exports.Match,sha:digest};
}
function createReport(){
 const previous=baselineMatch(),matrix=[];
 for(const [engine,Engine]of [['before',previous.Match],['after',Match]]){
  for(const kind of Object.keys(fields))for(const mode of ['automatic','manager'])for(const rating of [20,94]){
   const result=evaluate(kind,rating,mode,Engine);
   matrix.push({engine,...result});
   process.stderr.write(engine+'/'+kind+'/'+mode+'/'+rating+': '+result.targetDeviationDegrees+'deg, '+JSON.stringify(result.firstLanding)+', goalkeeper '+JSON.stringify(result.keeper)+'\n');
  }
 }
 const rows=[];
 for(const kind of Object.keys(fields))for(const mode of ['automatic','manager']){
  const of=(engine,rating)=>matrix.find(r=>r.engine===engine&&r.kind===kind&&r.mode===mode&&r.rating===rating);
  rows.push({kind,mode,before:{weak:of('before',20),strong:of('before',94)},
   after:{weak:of('after',20),strong:of('after',94)}});
 }
 const report={reference:{commit:baseRef,sha256:previous.sha},current:{sha256:hash(fs.readFileSync(path.join(__dirname,'../football-sim.js')))},
  method:'Main 254b0c6 historical engine versus unified engine. Same roster, same seed, real AI/manager choice, normal 60 Hz physical windup and unchanged BallPhysics; landing is independently predicted, keeper reactions observed without force-spawned events.',rows};
 const filename=path.join(__dirname,'../docs/validation/kick-specialist-parity.json');fs.mkdirSync(path.dirname(filename),{recursive:true});
 fs.writeFileSync(filename,JSON.stringify(report,null,2)+'\n');
 console.log('KICK_SKILL_COMPARISON '+JSON.stringify(rows.map(r=>({kind:r.kind,mode:r.mode,
  before:{weak:r.before.weak.targetDeviationDegrees,strong:r.before.strong.targetDeviationDegrees,
   weakLanding:r.before.weak.firstLanding,strongLanding:r.before.strong.firstLanding},
  after:{weak:r.after.weak.targetDeviationDegrees,strong:r.after.strong.targetDeviationDegrees,
   weakLanding:r.after.weak.firstLanding,strongLanding:r.after.strong.firstLanding,
   weakKeeper:r.after.weak.keeper,strongKeeper:r.after.strong.keeper}}))));
 return report;
}
if(require.main===module)createReport();
module.exports={evaluate,createReport,drop};
