'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Rig=require('../humanoid-rig');
const player=extra=>({x:0,z:0,vx:0,vz:0,speed:0,face:0,action:'idle',actionClock:0,...extra});
const dt=1/60;
test('head scan eases in, stays bounded and returns smoothly',()=>{
 const p=player({perception:{headYaw:1.55}}),before=structuredClone(p);
 const first=Rig.update(p,dt);assert(first.headYaw>0&&first.headYaw<.8);assert.equal(first.headFace,first.headYaw);
 let previous=first.headYaw;
 for(let i=0;i<9;i++){const pose=Rig.update(p,dt);assert(pose.headYaw>=previous&&pose.headYaw<=.8);previous=pose.headYaw;}
 assert(previous>.7);p.perception.headYaw=0;
 const returning=Rig.update(p,dt);assert(returning.headYaw>0&&returning.headYaw<previous);
 for(let i=0;i<90;i++)Rig.update(p,dt);
 assert.equal(Rig.getPose(p).headYaw,0);
 p.perception.headYaw=before.perception.headYaw;assert.deepEqual(p,before);
});
test('mirrored scan follows body heading without changing the body or contact geometry',()=>{
 for(const face of [0,Math.PI])for(const direction of [-1,1]){
  const p=player({face,perception:{headYaw:direction*1.55}}),plain=player({face});
  for(let i=0;i<20;i++){
   p.x=plain.x=i*.03;p.speed=plain.speed=2;
   const scan=Rig.update(p,dt),baseline=Rig.update(plain,dt);
   assert.equal(Math.sign(scan.headYaw),direction);assert(Math.abs(scan.headYaw)<=.8);assert.equal(scan.headFace,face+scan.headYaw);
   const stripped={...scan};delete stripped.headYaw;delete stripped.headFace;assert.deepEqual(stripped,baseline);
   assert.deepEqual(Rig.kickContact(p),Rig.kickContact(plain));assert.deepEqual(Rig.kickAnkle(p),Rig.kickAnkle(plain));assert.equal(p.face,face);
  }
 }
});
test('draw and zero-time queries do not advance a head scan',()=>{
 const p=player({perception:{headYaw:1.55}}),pose=Rig.update(p,dt),before=structuredClone(pose);
 p.perception.headYaw=-1.55;
 for(let i=0;i<20;i++){assert.equal(Rig.getPose(p),pose);assert.equal(Rig.update(p,0),pose);}
 assert.deepEqual(pose,before);
});
test('missing or invalid scan input retains the old pose shape',()=>{
 for(const perception of [undefined,{}, {headYaw:NaN},{headYaw:Infinity}]){
  const p=player({perception}),pose=Rig.update(p,dt);assert.equal('headYaw' in pose,false);assert.equal('headFace' in pose,false);
 }
});
test('GPU head and neck yaw do not rotate the body palette or change bone anchors',()=>{
 const Renderer=require('../player-renderer'),identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
 const assets={bones:['head','neck','spine'].map(name=>({name,head:[0,0,0],tail:[0,1,0],matrix:identity,inverseBind:identity}))};
 const p=player(),pose=Rig.update(p,dt),baseline=Renderer.palette(p,assets,pose),zero=Renderer.palette(p,assets,{...pose,headYaw:0});assert.deepEqual(zero,baseline);
 const scanned=Renderer.palette(p,assets,{...pose,headYaw:.8});
 assert.notDeepEqual(scanned.slice(0,12),baseline.slice(0,12));assert.notDeepEqual(scanned.slice(16,28),baseline.slice(16,28));
 assert.deepEqual(scanned.slice(32),baseline.slice(32));
 for(const offset of [0,16,32])assert.deepEqual(scanned.slice(offset+12,offset+16),baseline.slice(offset+12,offset+16));
});
test('procedural eyes follow head facing while the body and feet keep their pose',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),window={TribunHumanoidRig:Rig,TribunPitchLaws:require('../pitch-laws')};
 vm.runInNewContext(fs.readFileSync(require.resolve('../scene3d'),'utf8'),{window});
 const p=player({active:true,team:0,index:0}),pose=Rig.update(p,dt),figure=window.Stadium3D.prototype.figure;
 const draw=headFace=>{
  const calls=[];window.TribunHumanoidRig={getPose:()=>({...pose,...headFace===undefined?{}:{headFace}})};
  const mesh=new Proxy({},{get:(_,method)=>(...args)=>calls.push({method,args})});figure.call({camera:'close',debugRig:false},mesh,p,dt);return calls;
 };
 const baseline=draw(),zero=draw(0),scan=draw(.8);assert.deepEqual(zero,baseline);
 const eye=calls=>calls.find(c=>c.method==='sphere'&&c.args[3]===.010&&c.args[4]===.010&&c.args[5]===.016).args.slice(0,3);
 assert.notDeepEqual(eye(scan),eye(baseline));
 const firstEye=scan.findIndex(c=>c.method==='sphere'&&c.args[3]===.010&&c.args[4]===.010&&c.args[5]===.016);
 assert.deepEqual(scan.slice(0,firstEye-4),baseline.slice(0,firstEye-4));
});
