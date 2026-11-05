#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),zlib=require('node:zlib'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const sources={baseline:zlib.gunzipSync(fs.readFileSync(path.join(root,'docs/validation/baselines/stage2-football-sim.js.gz'))).toString(),current:fs.readFileSync(path.join(root,'football-sim.js'),'utf8')};
function load(s,n){const mod=new Module(path.join(root,n+'.cjs'),module);mod.filename=path.join(root,n+'.cjs');mod._compile(s,mod.filename);return mod.exports.Match;}
function fixture(C,side,block){
 const m=new C({seed:21});m.restart=null;m.time=10;m.phase='carry';m.planClock=100;m.players.forEach(p=>p.active=false);
 const p=m.players[3],q=m.players[1],gk=m.players[21],cover=m.players[20];
 for(const a of [p,q,gk,cover])Object.assign(a,{active:true,vx:0,vz:0,speed:0,face:side===1?0:Math.PI,action:'idle',actionClock:0,touchClock:0,receiveClock:0,duelRecovery:0,tackleClock:0});
 Object.assign(p,{x:0,z:0});Object.assign(q,{x:18*side,z:-4*side,vx:.6*side,vz:4.5*side,speed:Math.hypot(.6,4.5),face:Math.atan2(4.5*side,.6*side)});Object.assign(gk,{x:49*side,z:0});Object.assign(cover,{x:40*side,z:-25*side});
 m.ball={x:.88*side,y:.11,z:.18*side,vx:0,vy:0,vz:0};m.owner=p;m.lastTeam=0;m.lastTouch=p;
 m.targets=new Map([[p,{x:0,z:0,pace:1,state:'dribble'}],[q,{x:18.5*side,z:0,pace:.88,state:'shape'}]]);
 const d=m.players[14];if(block){Object.assign(d,{active:true,x:8*side,z:0,vx:0,vz:0,speed:0,face:side===1?Math.PI:0,touchClock:0,duelRecovery:0});m.targets.set(d,{x:d.x,z:d.z,pace:0,state:'cover'});}
 const lead=m.passTime('pass',Math.hypot(p.x-q.x,p.z-q.z),m.passSpeed('pass',Math.hypot(p.x-q.x,p.z-q.z),m.t[0]));
 const initialAim=m.receiverPoint(q,lead),seed=m.seed;assert(m.startKick(p,'pass',q,initialAim));return {m,p,q,initialAim,seed};
}
function run(C,side,block){
 const {m,p,q,initialAim,seed}=fixture(C,side,block),events=[];let resolved=null,minGap=null,maxStep=0,previous=m.players.map(p=>({x:p.x,z:p.z}));
 const release=m.release,acquire=m.acquire,restart=m.setRestart;
 m.release=function(){const k=this.kick;events.push({type:'release',time:this.time,kind:k.kind,point:{...k.point},target:k.target.id,ball:{...this.ball},receiver:{x:q.x,z:q.z}});return release.call(this);};
 m.acquire=function(actor){const f=this.flight;if(f?.from===p){const gap=Math.hypot(this.ball.x-q.x,this.ball.z-q.z);minGap=minGap===null?gap:Math.min(minGap,gap);}const out=acquire.call(this,actor);if(out&&f&&f.from===p){resolved={type:actor===q?'intended':actor.team===p.team?'other-own':'opponent',time:this.time,id:actor.id};events.push(resolved);}return out;};
 m.setRestart=function(...args){if(this.flight?.from===p){resolved={type:'restart',time:this.time,kind:args[0],team:args[1]};events.push(resolved);}return restart.apply(this,args);};
 for(let i=0;i<360&&!resolved;i++){m.step();for(const [id,p]of m.players.entries()){assert([p.x,p.z,p.vx,p.vz,p.face].every(Number.isFinite));maxStep=Math.max(maxStep,Math.hypot(p.x-previous[id].x,p.z-previous[id].z));previous[id]={x:p.x,z:p.z};}
  if(m.flight?.from===p){const gap=Math.hypot(m.ball.x-q.x,m.ball.z-q.z);minGap=minGap===null?gap:Math.min(minGap,gap);}assert(Object.values(m.ball).every(Number.isFinite));}
 assert(maxStep<=.15);return {initialSeed:seed,initialAim,events,resolution:resolved||{type:'unresolved'},minimumSampledCentreGap:minGap,maxStep,finalSeed:m.seed};
}
const versions=Object.fromEntries(Object.entries(sources).map(([name,s])=>[name,load(s,'controlled-'+name)]));
const result={generatedAt:new Date().toISOString(),sources:{baseline:sha(sources.baseline),current:sha(sources.current),observer:sha(fs.readFileSync(__filename)),tactics:sha(fs.readFileSync(path.join(root,'tactics.js')))},definition:'Same synthetic seed and fixed known team commands for at most 6 seconds. Ball physics, real kick/contact, passive interception and RNG remain enabled; no result forcing. Each trial starts an ordinary pass. Unresolved is not success. Sampled centre gap is not swept contact radius.',runs:[]};
for(const side of [1,-1])for(const block of [false,true]){const row={side,block};for(const [name,C]of Object.entries(versions))row[name]=run(C,side,block);assert.equal(row.baseline.initialSeed,row.current.initialSeed);result.runs.push(row);}
const at=process.argv.indexOf('--output'),text=JSON.stringify(result,null,2)+'\n';if(at>=0)fs.writeFileSync(process.argv[at+1],text);else process.stdout.write(text);
