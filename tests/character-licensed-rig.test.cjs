'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Rig=require('../humanoid-rig'),Scenarios=require('../animation-scenarios');
const length=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
const close=(a,b,epsilon=1e-7)=>assert(Math.abs(a-b)<epsilon,`${a} differs from ${b}`);
const player=extra=>({x:0,z:0,face:0,speed:0,action:'idle',actionClock:0,kickFoot:1,...extra});
const sub=(a,b)=>a.map((v,i)=>v-b[i]),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),unit=a=>a.map(v=>v/Math.hypot(...a)),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const sizes={pelvis:.085,spine:.18,chest:.205,neck:.13,head:.25,clavicle:.22,upper_arm:.315,forearm:.29,hand:.17,thigh:.475,shin:.431,foot:Math.hypot(.2,.075)};
function anatomy(q){
 const frames=Rig.boneFrames(q);assert.equal(Object.keys(frames).length,19);
 for(const [name,[a,b]] of Object.entries(frames)){assert([...a,...b].every(Number.isFinite));close(length(a,b),sizes[name.split('.')[0]],1e-6);}
 const up=unit(sub(q.torsoUpper,q.pelvis)),right=unit(sub(q.arms[1].shoulder,q.arms[0].shoulder)),forward=unit(cross(up,right));
 for(let i=0;i<2;i++)for(const [limb,start,joint] of [[q.arms[i],q.arms[i].shoulder,q.arms[i].elbow],[q.legs[i],q.legs[i].hip,q.legs[i].knee]]){
  const v=unit(sub(joint,start)),flex=Math.atan2(dot(v,forward),-dot(v,up)),abduct=Math.atan2(dot(v,right)*(i?1:-1),Math.hypot(dot(v,forward),dot(v,up)));
  close(Math.atan2(Math.sin(flex-limb.flex),Math.cos(flex-limb.flex)),0,1e-6);close(abduct,limb.abduct,1e-6);
 }
 close(length(q.legs[0].hip,q.legs[1].hip),.26);close(length(q.arms[0].shoulder,q.arms[1].shoulder),.44);
 for(const leg of q.legs){assert(leg.bend>=Rig.LIMITS.knee.min-1e-8&&leg.bend<=Rig.LIMITS.knee.max+1e-8);assert(leg.flex>=Rig.LIMITS.hip.flexMin-1e-8&&leg.flex<=Rig.LIMITS.hip.flexMax+1e-8);assert(leg.abduct>=Rig.LIMITS.hip.abductMin-1e-8&&leg.abduct<=Rig.LIMITS.hip.abductMax+1e-8);}
 for(const arm of q.arms){assert(arm.bend>=Rig.LIMITS.elbow.min-1e-8&&arm.bend<=Rig.LIMITS.elbow.max+1e-8);assert(arm.flex>=Rig.LIMITS.shoulder.flexMin-1e-8&&arm.flex<=Rig.LIMITS.shoulder.flexMax+1e-8);assert(arm.abduct>=Rig.LIMITS.shoulder.abductMin-1e-8&&arm.abduct<=Rig.LIMITS.shoulder.abductMax+1e-8);}
}
test('licensed hero has upright human proportions and one immutable shared skeleton',()=>{
 const p=player(),q=Rig.update(p,0),frames=Rig.boneFrames(q);anatomy(q);
 close(q.pelvis[1],1.03);close(q.torsoUpper[1],1.50);close(q.neck[1],1.63);close(q.headTop[1],1.88);
 for(const leg of q.legs){assert(leg.bend<15*Math.PI/180,'rest knees must not crouch');close(leg.ankle[1],.13);}
 for(const arm of q.arms){assert(arm.wrist[1]>.90&&arm.wrist[1]<1.0);assert(arm.bend<55*Math.PI/180);}
 assert.equal(Rig.boneFrames(q),frames);assert(Object.isFrozen(frames));assert(Object.isFrozen(Rig.ANATOMY));assert(Object.isFrozen(Rig.LIMITS.shoulder));
 for(const frame of Object.values(frames)){assert(Object.isFrozen(frame));assert(frame.every(Object.isFrozen));}
 assert.throws(()=>{frames['upper_arm.L'][0][0]=123;},TypeError);
});
test('bounded IK projects unreachable endpoints without shortening or stretching either bone',()=>{
 for(const upper of [.315,.475])for(const lower of [.29,.431])for(const goal of [[0,0,0],[0,-.01,0],[0,-.6,0],[3,7,-2],[-5,-3,8],[0,-1,0]])for(const pole of [[1,0,0],[0,-1,0],[0,0,1]]){
  const ik=Rig.solveLimb([0,0,0],goal,upper,lower,pole);
  close(length([0,0,0],ik.joint),upper);close(length(ik.joint,ik.end),lower);
  assert(ik.bend>=.045-1e-8&&ik.bend<=150*Math.PI/180+1e-8);close(ik.error,length(ik.end,goal));
 }
 assert.throws(()=>Rig.solveLimb([0,0,0],[NaN,0,0],.3,.3));
});
test('every licensed action keeps fixed torso, clavicle, hand, arm, leg and foot lengths',()=>{
 for(const mode of ['walk','jog','sprint','turn','pass','shoot','run-pass','run-shoot','dive-left','dive-right']){
  const s=Scenarios.create(mode);
  for(let i=0;i<300;i++){Scenarios.sample(s,i/60,Rig);const before=structuredClone(s.p),q=Rig.update(s.p,1/60);anatomy(q);assert.deepEqual(s.p,before);}
 }
 for(const action of ['catch','catch-ready','throw','header','celebrate','protest','tackle','receive'])for(const h of [.11,.4,1.05,1.8,2.6]){
  const p=player({action,actionClock:1,actionElapsed:.34,actionDuration:.95,catchPoint:{x:.25,y:h,z:0},headerHeight:h});anatomy(Rig.update(p,1/60));
 }
});
// Frozen numerical outputs from the production physical contact API before
// canonical retargeting. These protect football-sim's ball/hand/boot geometry.
const contacts=[
 {p:{x:2,z:-3,face:1.2,action:'catch',actionClock:.3,actionElapsed:.2,catchPoint:{x:2.3,y:.2,z:-2.6}},hands:[[2.3484472004254964,.41009814571371306,-2.755410024768176],[2.0628375230156744,.45091854200256876,-2.6709062021395806]],kick:[2.4866418594135733,.11,-2.245030000154642],ankle:[2.327204447443837,.13,-2.655127197980222]},
 {p:{x:-4,z:3,face:-.7,action:'catch-ready',actionClock:.7,actionElapsed:.12,catchPoint:{x:-3,y:2.4,z:4}},hands:[[-3.7963698971199333,1.792226425672554,3.16166602633709],[-3.415794573008754,1.88200418306148,3.5976732708104993]],kick:[-3.4428980588924345,.11,2.295416841519624],ankle:[-3.779428621297609,.13,2.578872623904208]},
 {p:{x:1,z:2,face:.8,action:'dive',actionElapsed:.34,diveSide:1,diveContactTime:.34,actionDuration:.95,saveTarget:{x:.5,y:1.05,z:3.65}},hands:[[.6290836407558,1.0352214023773274,3.5081787126833497],[.58,1.11,3.65]],kick:[1.7422260005874195,.11,2.50586615230909],ankle:[1.4356750484746668,.13,2.1902294723133]},
 {p:{x:1,z:-2,face:2.1,action:'dive',actionElapsed:.24,diveSide:-1,diveForward:.23,diveContactTime:.4,actionDuration:1.1,saveTarget:{x:1.8,y:2.5,z:-4}},hands:[[1.5829485722652161,1.9287644699508084,-3.202202717361615],[1.2923437609855388,1.8988031657221596,-3.3424949650736524]],kick:[.7111131139489226,.11,-1.1495034585210167],ankle:[.9332453999728599,.13,-1.529315579846521]},
 {p:{x:-4,z:1,face:-2.4,action:'dive',actionElapsed:.78,diveSide:1,diveContactTime:.22,actionDuration:.95,saveTarget:{x:-5,y:.2,z:2.4}},hands:[[-4.51193652848158,.8046563604051502,1.572906587120207],[-4.01088762208152,.9319690996598862,1.0698033483449576]],kick:[-4.770489842175503,.11,.5383232699124114],ankle:[-4.446036607337355,.13,.8355270693549177]}
];
test('physical catch, dive, save and kick contacts retain their exact production coordinates',()=>{
 for(const fixture of contacts){const p=player({...fixture.p,kickFoot:0}),before=structuredClone(p);assert.deepEqual(Rig.saveHands(p),fixture.hands);assert.deepEqual(Rig.kickContact(p),fixture.kick);assert.deepEqual(Rig.kickAnkle(p),fixture.ankle);Rig.update(p,1/60);assert.deepEqual(p,before);assert.deepEqual(Rig.saveHands(p),fixture.hands);}
 for(const face of [0,Math.PI/2,Math.PI])for(const kickFoot of [0,1]){
  const p=player({face,kickFoot,action:'shoot',actionClock:.2,actionElapsed:.38,contactTime:.38,actionDuration:.68}),q=Rig.update(p,1/60);close(length(q.legs[kickFoot].ankle,Rig.kickAnkle(p)),0);
 }
});
test('save palms meet normal contact targets and explicitly measure bounded presentation residuals',()=>{
 for(const mode of ['dive-left','dive-right']){
  const s=Scenarios.create(mode);
  for(let i=0;i<57;i++){Scenarios.sample(s,i/60,Rig);const q=Rig.update(s.p,1/60);assert(q.contactError<.003);if(i===21)assert(q.contactError<1e-6);}
 }
 let maxError=0,limited=0;
 for(const action of ['catch','catch-ready','dive'])for(const face of [0,Math.PI/2,Math.PI,-Math.PI/2])for(const h of [.11,.4,1.05,1.8,2.6,4])for(const side of [-1,1])for(const f of [-1,0,1]){
  const p=player({x:2,z:-3,face,action,actionClock:.6,actionElapsed:.34,actionDuration:.95,diveContactTime:.34,diveSide:side,saveTarget:{x:2+f,y:h,z:-3+side*1.65},catchPoint:{x:2+f,y:h,z:-3+side*.2}}),before=structuredClone(p),q=Rig.update(p,1/60);anatomy(q);
  assert.deepEqual(p,before);assert(Math.hypot(...q.presentationOffset)<=Rig.LIMITS.presentationReach+1e-8);
  const targets=Rig.saveHands(p);for(let i=0;i<2;i++){assert.deepEqual(q.arms[i].contactTarget,targets[i]);close(q.arms[i].contactError,length(q.arms[i].palm,targets[i]));}
  close(q.contactError,Math.max(...q.arms.map(a=>a.contactError)));maxError=Math.max(maxError,q.contactError);if(q.contactError>.005)limited++;
 }
 assert(maxError>.1&&maxError<.17,`adversarial residual ${maxError} must stay measured, never hidden by limb stretch`);assert(limited>0);
});
test('draw and zero-time queries reuse poses without advancing state or scan angles',()=>{
 const p=player({perception:{headYaw:.7}}),q=Rig.update(p,1/60),before=structuredClone(q),frames=Rig.boneFrames(q);p.perception.headYaw=-.7;
 for(let i=0;i<20;i++){assert.equal(Rig.getPose(p),q);assert.equal(Rig.update(p,0),q);assert.equal(Rig.boneFrames(q),frames);}assert.deepEqual(q,before);
});
