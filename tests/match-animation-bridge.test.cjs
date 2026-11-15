'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Bridge=require('../match-animation-bridge.js');
const Rig=require('../humanoid-rig.js');
const Renderer=require('../player-renderer.js');
const Assets=require('../assets/player/player-model-data.js');

const near=(x,y,tol=2e-5)=>assert(Math.abs(x-y)<=tol,'expected '+x+' near '+y);
function matrix(angle=0,x=0,z=0){
 const c=Math.cos(angle),s=Math.sin(angle),m=new Float32Array(16);
 m.set([c,0,s,0,0,1,0,0,-s,0,c,0,x,0,z,1]);
 return m;
}
function group(angle=0,x=0,z=0){
 const one=matrix(angle,x,z),out=new Float32Array(19*16);
 for(let i=0;i<19;i++)out.set(one,i*16);
 return out;
}
function basisCheck(m,licensedScale=false){
 for(let i=0;i<m.length;i+=16){
  const sizes=[0,1,2].map(c=>Math.hypot(m[i+c*4],m[i+c*4+1],m[i+c*4+2]));
  for(const n of sizes){
   if(licensedScale)assert(n>=.45&&n<=1.75,'calibrated skeleton length is outside supported bounds: '+n);
   else near(n,1,4e-5);
  }
  for(let c=0;c<3;c++)for(let d=c+1;d<3;d++)
   near((m[i+4*c]*m[i+4*d]+m[i+4*c+1]*m[i+4*d+1]+m[i+4*c+2]*m[i+4*d+2])/(sizes[c]*sizes[d]),0,4e-5);
  assert(Number.isFinite(m[i+12])&&Number.isFinite(m[i+14]));
 }
}
test('match bridge SLERPs real bone matrices without shrinking bones',()=>{
 const bridge=Bridge.create({duration:.28}),p={x:0,z:0,action:'run',speed:3};
 const start=group(0),end=group(Math.PI/2,3,0);
 assert.equal(bridge.sample(p,start,1/60),start);
 p.x=3;p.action='shoot';
 const first=bridge.sample(p,end,0);
 near(first[0],1);near(first[12],3); // previous pose translated with match player
 const mid=bridge.sample(p,end,.14);
 near(mid[0],Math.SQRT1_2,1e-4);near(mid[2],Math.SQRT1_2,1e-4);
 near(mid[12],3);basisCheck(mid);
 const final=bridge.sample(p,end,.14);
 near(final[0],end[0]);near(final[2],end[2]);near(final[12],3);basisCheck(final);
 const meta=bridge.stats();
 assert.equal(meta.transitions,1);
 assert(meta.blendedFrames>=2);
 assert.equal(bridge.sample(p,end,1/60),end);
 bridge.reset();assert.equal(bridge.stats().transitions,0);
});
test('locomotion changes do not create a crossfade and player gameplay state stays untouched',()=>{
 const bridge=Bridge.create(),p={x:0,z:0,action:'run',speed:4,stamina:73,team:0};
 const original={...p},p0=group(0),p1=group(.5);
 bridge.sample(p,p0,1/60);
 p.action='sprint';const out=bridge.sample(p,p1,.1);
 assert.equal(out,p1,'run/jog/sprint are one locomotion family');
 assert.equal(bridge.stats().transitions,0);
 assert.equal(p.stamina,original.stamina);assert.equal(p.speed,original.speed);assert.equal(p.team,original.team);
 assert.deepEqual(Object.keys(p).sort(),Object.keys(original).sort());
 assert.throws(()=>Bridge.create({duration:-1}));
 assert.throws(()=>bridge.sample(p,p1,-.01));
});
test('22 active real footballer palettes blend independently and keep rigid bases',()=>{
 const bridge=Bridge.create({duration:.28});
 const players=Array.from({length:22},(_,i)=>({
  active:true,id:i,team:i<11?0:1,index:i%11,x:i%11*1.4,z:(i<11?-1:1)*5,
  speed:2.5,face:i<11?0:Math.PI,action:'run',actionClock:0,kickFoot:i%2
 }));
 for(const player of players){
  const pose=Rig.update(player,1/60);
  const raw=Renderer.palette(player,Assets,pose);
  assert.equal(bridge.sample(player,raw,1/60,pose.action),raw);
 }
 for(let k=0;k<18;k++){
  for(const p of players){
   if(p.id%4===0){p.action='shoot';p.actionClock=.4;p.actionElapsed=k/60;p.actionDuration=.4;p.contactTime=.2;}
   p.x+=p.speed/60;
   const pose=Rig.update(p,1/60),raw=Renderer.palette(p,Assets,pose);
   const blended=bridge.sample(p,raw,1/60,pose.action);
   assert.equal(blended.length,19*16);
   // The licensed renderer itself can contain slightly skewed matrices in
   // unblended poses. Only assert rigid axes for the new animation bridge output.
   if(blended!==raw)basisCheck(blended,true);
  }
 }
 assert.equal(bridge.stats().players,22);
 assert(bridge.stats().transitions>=5);
 assert(bridge.stats().blendedFrames>0);
});

test('licensed rig retains calibrated non-unit bind length without snapping on fade completion',()=>{
 const a=group(0),b=group(Math.PI/3);
 a[5]=.63;b[5]=1.48;
 const mid=Bridge.mixRigid(a,b,new Float32Array(a.length),.5);
 const end=Bridge.mixRigid(a,b,new Float32Array(a.length),1);
 near(Math.hypot(mid[4],mid[5],mid[6]),1.055,2e-5);
 near(Math.hypot(end[4],end[5],end[6]),1.48,2e-5);
 basisCheck(mid,true);basisCheck(end,true);
});
