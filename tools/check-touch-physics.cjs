'use strict';
// Focused, deterministic checks of this game's existing movement/foot model.
// Run: node tools/check-touch-physics.cjs [--output path/to/report.json]
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto'),Module=require('node:module');
const root=path.resolve(__dirname,'..'),dt=1/60,hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const currentSource=fs.readFileSync(path.join(root,'football-sim.js'));
const baseSource=zlib.gunzipSync(fs.readFileSync(path.join(root,'docs/validation/baselines/stage8-integration-base.js.gz')));
const baselineHash='16d6d78ac01b5490bbb8a178b4134a2f8c41224ad7091fb1e0b6b37aafa07360';
assert.equal(hash(baseSource),baselineHash,'retained integration baseline must match its recorded source hash');
const oldModule=new Module(path.join(root,'touch-physics-baseline.js'),module);oldModule.filename=path.join(root,'touch-physics-baseline.js');oldModule.paths=module.paths;oldModule._compile(baseSource.toString(),oldModule.filename);
const {Match,BallPhysics}=require('../football-sim'),OldMatch=oldModule.exports.Match,OldBallPhysics=oldModule.exports.BallPhysics;
const pose=p=>({x:p.x,z:p.z,vx:p.vx,vz:p.vz,face:p.face}),position=b=>({x:b.x,y:b.y,z:b.z});
const report={generatedAt:new Date().toISOString(),sources:{baseline:baselineHash,current:hash(currentSource),checker:hash(fs.readFileSync(__filename))},scope:{claim:'Deterministic consistency with the existing 60 Hz game movement, foot window and shared ball integrator.',clocks:{carryAndShield:'The global dribble cadence and receive cooldown must expire before another carry touch; the forecast uses the same literal 60 Hz clock decrements as live play.',firstControl:'The already-established receive and touch cooldowns determine the next ordinary carry-contact horizon.',setupAndRelease:'Ground kick setup and release use the selected foot\'s remaining existing footTouch recovery plus receive cooldown, rather than the global dribble cadence. A recently used dribble foot may still recover while the other foot is available. The existing kick nextSetup interval remains separate.'},limits:['These checks are not biomechanical validation of human balance, anatomy or real foot forces.','The foot window, acceleration limits and recovery horizons are gameplay approximations.','Live phase fixtures isolate a held owner intention without future decisions, extra control touches or interventions.','Other players in the forecast use their observed positions and velocities; their future actions and collisions are not predicted.','Small selected fixtures do not establish whole-match tactical quality or real-world football accuracy.']},protectedFunctions:{},pureQueries:{},liveCarry:[],liveReceive:[],liveSetup:[],selectedFootClocks:[],liveReleaseClocks:[]};

for(const name of ['release','tackleAccess','doTackle','integrateBall','ballStep','step','startKick','contactPoint','effort']){
 const before=OldMatch.prototype[name].toString(),after=Match.prototype[name].toString();assert.equal(after,before,`${name} changed outside the touch-model scope`);
 report.protectedFunctions[name]={identicalToIntegrationBase:true,sha256:hash(after)};
}
assert.deepEqual(Object.keys(BallPhysics),Object.keys(OldBallPhysics));
report.protectedFunctions.BallPhysics={identicalToIntegrationBase:true,members:{}};
for(const key of Object.keys(BallPhysics)){
 const current=typeof BallPhysics[key]==='function'?BallPhysics[key].toString():BallPhysics[key],base=typeof OldBallPhysics[key]==='function'?OldBallPhysics[key].toString():OldBallPhysics[key];assert.deepEqual(current,base,`BallPhysics.${key} changed`);
 report.protectedFunctions.BallPhysics.members[key]=typeof current==='string'?{sha256:hash(current)}:current;
}

function fixture({side=1,speed=4,yaw=0,lateral=.18,skill=82,shield=false,ballX=.8,ballSpeed=3,refresh=.03}={}){
 const m=new Match({seed:21});m.restart=null;m.kick=null;m.time=10;m.planClock=refresh;m.players.forEach(q=>q.active=false);
 const p=m.players[3],target={x:6*Math.cos(yaw)*side,z:6*Math.sin(yaw)*side};
 Object.assign(p,{active:true,x:0,z:0,vx:speed*side,vz:0,speed,face:side>0?0:Math.PI,skill,dribbling:skill,agility:skill,pace:skill,stamina:95,energy:1,touchClock:0,receiveClock:0,duelRecovery:0,action:'idle',actionClock:0,actionElapsed:0,decision:100,carryTarget:target,shieldUntil:shield?11:0,shieldFace:side>0?0:Math.PI,preferredFoot:1,kickFoot:1});
 m.owner=p;m.lastTouch=p;m.lastTeam=p.team;m.ball={x:ballX*side,y:.11,z:lateral*side,vx:ballSpeed*side,vy:0,vz:0};m.targets=new Map([[p,{...target,state:shield?'shield':'dribble',pace:shield?.56:.98}]]);return {m,p,target};
}

// Every result must be independent of RNG and opponent commands, and none of
// these queries may mutate the live match, input velocity or target object.
{
 const {m,p,target}=fixture({speed:4,yaw:Math.PI}),rival=m.players[14];Object.assign(rival,{active:true,x:8,z:4,vx:-1,vz:.2});m.targets.set(rival,{x:1,z:1,state:'press',pace:1});
 const velocity={vx:-4,vy:.1,vz:0},options={interval:.3416,target},before=structuredClone(m),inputBefore=structuredClone({velocity,options});
 m.random=function(){throw new Error('a pure touch query consumed RNG')};
 const first={contact:m.touchContact(p),recovery:m.touchRecovery(p,velocity,options),plan:m.touchPlan(p,velocity,options)};
 for(let i=0;i<3;i++)assert.deepEqual({contact:m.touchContact(p),recovery:m.touchRecovery(p,velocity,options),plan:m.touchPlan(p,velocity,options)},first);
 delete m.random;assert.deepEqual(structuredClone(m),before);assert.deepEqual({velocity,options},inputBefore);
 m.targets.set(rival,{x:-49,z:-31,state:'goal',pace:0});assert.deepEqual({contact:m.touchContact(p),recovery:m.touchRecovery(p,velocity,options),plan:m.touchPlan(p,velocity,options)},first);
 const clonedBall=m.touchRecovery(p,velocity,options).ball;clonedBall.x+=100;assert.deepEqual(m.ball,before.ball);
 report.pureQueries={passed:true,repeatedQueries:4,liveStateUnchanged:true,inputObjectsUnchanged:true,rngDraws:0,opponentCommandIndependent:true,resultBallDoesNotAliasLiveBall:true};
}

const carryCases=[
 {id:'ordinary-forward',speed:4,yaw:0},
 {id:'turn-from-run',speed:4,yaw:Math.PI},
 {id:'turn-from-sprint',speed:6,yaw:Math.PI},
 {id:'shield-from-sprint',speed:6,yaw:Math.PI,shield:true},
 {id:'wide-front-sharp-turn',speed:6,yaw:.6,lateral:.8},
 {id:'standing-reverse-wide-ball',speed:0,yaw:Math.PI,lateral:-.8},
 {id:'literal-clock-forward',speed:6,yaw:0,skill:75},
 {id:'literal-clock-turn',speed:6,yaw:.3,lateral:.8,skill:75}
];
for(const side of [1,-1])for(const item of carryCases){
 const {m,p}=fixture({...item,side}),initialBall={...m.ball};let accepted,attempt;
 const touchPlan=m.touchPlan;m.touchPlan=function(actor,velocity,options){const r=touchPlan.call(this,actor,velocity,options);attempt=r;if(r.ready&&!accepted)accepted={plan:r,options,ballBefore:{...this.ball}};return r};
 m.step(dt);delete m.touchPlan;
 if(!accepted){assert.deepEqual(m.ball,BallPhysics.predict(initialBall,dt));report.liveCarry.push({id:item.id,side,accepted:false,reason:attempt?.reason??'contact-unavailable',noImpulse:true});continue;}
 const f=accepted.plan.recovery;assert.deepEqual(m.ball,BallPhysics.predict({...accepted.ballBefore,...accepted.plan.velocity},dt));
 // Suppress subsequent touches only; keep the actual live cooldowns, planner,
 // action clocks, movement and free ball integration running.
 m.dribbleTouch=function(){return false};p.decision=100;const ticks=Math.round(f.time*60);
 for(let i=0;i<ticks-1;i++)m.step(dt);
 let observed;const ballStep=m.ballStep;m.ballStep=function(d){observed={player:pose(p),ball:{...this.ball},contact:this.touchContact(p),clock:p.touchClock,receiveClock:p.receiveClock};return ballStep.call(this,d)};m.step(dt);
 assert(observed);assert.deepEqual(observed.player,f.player);assert.deepEqual(observed.ball,f.ball);assert(observed.contact.ready);assert.equal(observed.clock,0);assert.equal(observed.receiveClock,0);assert.equal(m.owner,p);
 report.liveCarry.push({id:item.id,side,accepted:true,weight:accepted.plan.weight,nominalInterval:accepted.options.interval,contactTime:f.time,ballTime:f.ballTime,nextFoot:f.foot,nextGap:f.gap,nextForward:f.forward,actualMatchesForecast:true,actualFootAvailable:true,cooldownsExactlyZero:true,positionChangedOnlyByBallPhysics:true});
}
assert(report.liveCarry.some(r=>r.accepted&&r.weight<1));assert(report.liveCarry.some(r=>!r.accepted));

for(const side of [1,-1])for(const actionClock of [0,.15,.3,.6]){
 const {m,p,target}=fixture({side,speed:6,yaw:Math.PI,ballSpeed:-10}),from=m.players[4];Object.assign(from,{active:true,x:-8*side,z:8*side,vx:0,vz:0,speed:0});m.owner=null;m.planClock=100;
 Object.assign(p,{action:actionClock?'pass':'idle',actionClock,kickMoving:false});m.flight={id:7,kind:'pass',from,target:p,age:0,point:{...target},offsidePlayers:[]};p.reception={flightId:7,fromId:from.id,at:10,mode:'open',point:{...target},face:Math.PI+(side<0?Math.PI:0)};
 const beforePosition=position(m.ball);let accepted;const touchPlan=m.touchPlan;m.touchPlan=function(actor,velocity,options){const r=touchPlan.call(this,actor,velocity,options);if(r.ready)accepted={plan:r,options};return r};assert.equal(m.acquire(p),true);delete m.touchPlan;assert.deepEqual(position(m.ball),beforePosition);assert(accepted);
 const f=accepted.plan.recovery;p.decision=100;m.dribbleTouch=function(){return false};const ticks=Math.round(f.time*60);for(let i=0;i<ticks-1;i++)m.step(dt);
 let observed;const ballStep=m.ballStep;m.ballStep=function(d){observed={player:pose(p),ball:{...this.ball},contact:this.touchContact(p),receiveClock:p.receiveClock,touchClock:p.touchClock};return ballStep.call(this,d)};m.step(dt);
 assert.deepEqual(observed.player,f.player);assert.deepEqual(observed.ball,f.ball);assert(observed.contact.ready);assert.equal(observed.receiveClock,0);assert.equal(observed.touchClock,0);assert.equal(m.owner,p);
 report.liveReceive.push({side,priorPassActionClock:actionClock,weight:accepted.plan.weight,contactTime:f.time,ballTime:f.ballTime,nextGap:f.gap,actualMatchesForecast:true,actualFootAvailable:true,cooldownsExactlyZero:true,noPositionCorrection:true});
}

for(const side of [1,-1])for(const item of [
 {id:'front-stationary',speed:0,yaw:0,ballX:.8},
 {id:'recover-behind-stationary',speed:0,yaw:.8,ballX:-.7},
 {id:'front-running-turn',speed:2,yaw:.8,ballX:.8},
 {id:'front-sprint-reverse',speed:6,yaw:Math.PI,ballX:.8},
 {id:'unrecoverable-behind-sprint',speed:6,yaw:0,ballX:-.7}
]){
 const {m,p,target}=fixture({...item,side,ballSpeed:0,refresh:100});assert(m.startKick(p,'pass',null,target));let accepted;const touchPlan=m.touchPlan;
 m.touchPlan=function(actor,velocity,options){if(accepted)return {ready:false};const r=touchPlan.call(this,actor,velocity,options);if(r.ready)accepted={plan:r,options,time:this.time};return r};
 // Hold the same kick intention without subsequent setup touches or release.
 // This isolates the forecast horizon while retaining real kick recovery.
 m.release=function(){return false};for(let i=0;i<60&&!accepted&&m.kick;i++)m.step(dt);
 if(!accepted){assert.equal(item.id,'unrecoverable-behind-sprint');report.liveSetup.push({id:item.id,side,accepted:false,kickEnded:!m.kick});continue;}
 const f=accepted.plan.recovery;for(let i=0;i<Math.round(f.time*60);i++)m.step(dt);
 const contact=m.touchContact(p,m.ball,p.kickFoot);assert.deepEqual(pose(p),f.player);assert.deepEqual(m.ball,f.ball);assert(contact.ready);assert.equal(contact.footClock,0);assert.equal(p.receiveClock,0);assert(m.kick);
 report.liveSetup.push({id:item.id,side,accepted:true,weight:accepted.plan.weight,contactTime:f.time,ballTime:f.ballTime,nextGap:f.gap,actualMatchesForecast:true,actualFootAvailable:true,selectedFootClockExactlyZero:true,receiveClockExactlyZero:true,heldIntentionOnly:true});
}

for(const side of [1,-1])for(const foot of [0,1])for(const sameFoot of [true,false]){
 const {m,p,target}=fixture({side,speed:0,ballSpeed:0,lateral:foot?.18:-.18});
 Object.assign(p,{preferredFoot:foot,kickFoot:foot,dribbleFoot:sameFoot?foot:1-foot,footTouch:.14,touchClock:.4});
 const velocity={vx:0,vy:0,vz:0},options={mode:'setup',interval:.18,target};
 assert.equal(m.touchPlan(p,velocity,options).reason,'unavailable');assert.equal(m.touchRecovery(p,velocity,options).reason,'unavailable');assert(m.startKick(p,'pass',null,target));assert.equal(p.kickFoot,foot);
 const before=structuredClone(m),contact=m.touchContact(p,m.ball,foot),plan=m.touchPlan(p,velocity,options);
 assert.equal(contact.footClock,sameFoot?.14:0);assert.equal(plan.ready,!sameFoot);if(sameFoot)assert.equal(plan.reason,'foot-clock');
 for(const mode of ['carry','shield'])assert.equal(m.touchPlan(p,velocity,{...options,mode}).reason,'foot-clock');
 const readyLater=m.touchRecovery(p,velocity,options);assert(readyLater.ready);assert.equal(p.touchClock,.4);assert.deepEqual(structuredClone(m),before);
 p.receiveClock=.01;assert.equal(m.touchPlan(p,velocity,options).reason,'foot-clock');p.receiveClock=0;
 report.selectedFootClocks.push({side,foot,lastDribbleFoot:p.dribbleFoot,sameFoot,globalDribbleClock:.4,selectedFootClock:contact.footClock,initialSetupAllowed:plan.ready,carryAndShieldStillBlocked:true,receiveCooldownStillBlocks:true,forecastExpiresSelectedFootRecovery:true,pureQuery:true});
}

// A short prepared strike can reach its duration before the existing .14s
// same-foot recovery expires. Check the actual final release gate as well as
// setup queries; the other foot must remain free to act during carry cadence.
for(const side of [1,-1])for(const foot of [0,1])for(const sameFoot of [true,false]){
 const {m,p,target}=fixture({side,speed:0,ballSpeed:0,ballX:.88,lateral:foot?.18:-.18,refresh:100});
 Object.assign(p,{preferredFoot:foot,kickFoot:foot,dribbleFoot:sameFoot?foot:1-foot,footTouch:.14,touchClock:.4,oneTouchUntil:m.time+.48});assert(m.startKick(p,'pass',null,target));
 let released;const start=m.time,release=m.release;m.release=function(){const contact=this.touchContact(p,this.ball,p.kickFoot),before={...this.ball};assert(contact.ready);assert.equal(contact.footClock,0);assert.equal(p.receiveClock,0);assert(this.ball.y<.45);released={time:this.time-start,selectedFootClock:contact.footClock,globalDribbleClock:p.touchClock,receiveClock:p.receiveClock,setupImpulse:this.kick.setupImpulse};const out=release.call(this);assert.deepEqual(position(this.ball),position(before));return out};
 for(let i=0;i<30&&m.kick;i++)m.step(dt);assert(released);assert(released.globalDribbleClock>0);assert.equal(m.flight.kind,'pass');assert(released.time+1e-9>=(sameFoot?.14:.12));
 report.liveReleaseClocks.push({side,foot,sameFoot,...released,selectedFootAvailableAtActualRelease:true,globalCarryCadenceDoesNotBlockTheAvailableFoot:true,noPositionCorrection:true});
}

report.summary={passed:true,protectedFunctions:Object.keys(report.protectedFunctions).length,pureQueryChecks:true,carryFixtures:report.liveCarry.length,acceptedCarry:report.liveCarry.filter(r=>r.accepted).length,deferredCarry:report.liveCarry.filter(r=>!r.accepted).length,receiveFixtures:report.liveReceive.length,setupFixtures:report.liveSetup.length,acceptedSetup:report.liveSetup.filter(r=>r.accepted).length,selectedFootClockFixtures:report.selectedFootClocks.length,actualReleaseClockFixtures:report.liveReleaseClocks.length};
const outputIndex=process.argv.indexOf('--output'),output=outputIndex>=0?path.resolve(process.argv[outputIndex+1]):path.join(root,'docs/validation/touch-feasibility-physics-check.json');
fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({output:path.relative(root,output),...report.summary},null,2));
