'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {analyze,windowAt}=require('./native-attack-bottlenecks.cjs');
function frame(i,{x=42,owner=0,shots=[0,0],inPlay=true,done=false,dir=1}={}){
 return {schema:1,engine:'league-soccer',elapsedMs:i*100,matchMs:done?5400000:i*1800,done,
 inPlay,attackDirection:[dir,-dir],ball:[x*dir,0,.11],stats:{shots},
 players:[{id:1,team:0,position:[x*dir,0,0],goalkeeper:false,uniquePossession:owner===0},
 {id:2,team:1,position:[20*dir,20,0],goalkeeper:false,uniquePossession:owner===1}]};
}
test('distinct retreat, loose control and observed shot windows',()=>{
 const frames=[frame(0),frame(1),frame(2),frame(3,{x:10}),frame(4),frame(5,{shots:[1,0]}),frame(6,{owner:null,shots:[1,0]}),frame(7,{inPlay:false,done:true,shots:[1,0]})];
 const r=analyze(frames).teams[0];
 assert.equal(r.episodes,2);assert.equal(r.boxEpisodes,2);
 assert.equal(r.windowEpisodesWithoutObservedShot,1);
 assert.equal(r.shotsDuringEpisodes,1);assert.equal(r.shotsOutsideEpisodes,0);
 assert.equal(r.endings.retreat,1);assert.equal(r.endings.loose,1);
});
test('gap cannot attribute shot or invent controlled interval',()=>{
 const r=analyze([frame(0),frame(10,{shots:[1,0]}),frame(11,{done:true,inPlay:false,shots:[1,0]})]);
 assert.equal(r.excludedGapMs,1000);assert.equal(r.teams[0].shotsOutsideEpisodes,1);
 assert.equal(r.teams[0].windowMs,0);
});
test('mirrored direction, defender blocking and missing telemetry',()=>{
 const f=frame(0,{dir:-1});
 assert.equal(windowAt(f,f.players[0]),true);
 f.players[1].position=[-43,0,0];
 assert.equal(windowAt(f,f.players[0]),false);
 delete f.players[0].uniquePossession;
 assert.throws(()=>analyze([f,frame(1,{done:true})]),/Incomplete/);
});

test('loose control separates recovered passes, opposition control and unresolved intervals',()=>{
 const f=[frame(0),frame(1,{owner:null}),frame(2),frame(3,{owner:null}),frame(4,{owner:1}),frame(5),frame(6,{owner:null}),frame(22,{owner:null}),frame(23,{done:true,inPlay:false,owner:null})];
 for(let i=0;i<f.length;i++)f[i].stats.passes=[i>=1?1:0,0];
 const r=analyze(f).controlTransitions[0];
 assert.equal(r.sameTeam,1);assert.equal(r.opponent,1);assert.equal(r.unresolved,1);assert.equal(r.passObserved,1);
 delete f[0].stats.passes;
 assert.equal(analyze(f).controlTransitions,null);
});
test('stoppage and telemetry gap are not counted as turnovers',()=>{
 const f=[frame(0),frame(1,{owner:null}),frame(2,{inPlay:false,owner:null}),frame(3),frame(4,{owner:null}),frame(10,{owner:1}),frame(11,{done:true,inPlay:false})];
 for(const a of f)a.stats.passes=[0,0];
 const r=analyze(f).controlTransitions[0];
 assert.equal(r.stoppage,1);assert.equal(r.gap,1);assert.equal(r.opponent,0);
});
