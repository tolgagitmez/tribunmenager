'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{create}=require('./native-advisor.js');
function packet(seq,minute,score=[0,0],shots=[0,0],passes=[0,0]){
 const players=Array.from({length:22},(_,i)=>({databaseId:i+1,team:Math.floor(i/11),goalkeeper:i%11===10,formationTarget:[i%11<3?.45:i%11<6?0:-.5,0,0]}));
 return {engine:'league-soccer',authoritative:false,sequence:seq,phase:'playing',players:[],frame:{engine:'league-soccer',done:false,matchMs:minute*60000,elapsedMs:seq*100,score,players,stats:{shots,onTarget:[0,0],passes,completed:passes,possessionMs:[seq,seq]}}};
}
test('score-aware advice is different for both teams and no late final advice',()=>{
 const a=create(),p=packet(1,75,[0,1]);delete p.frame.players[0].formationTarget;assert(a.ingest(p));
 assert.equal(a.advice(0).mode,'chase');assert.equal(a.advice(0).values.formation,433);
 assert.equal(a.advice(1).mode,'protect');assert.equal(a.advice(1).values.formation,4231);
 const final=packet(2,90,[0,2]);final.frame.done=true;assert(a.ingest(final));assert.equal(a.advice(0),null);
});
test('rolling shot drought requires observed history and rejects stale samples',()=>{
 const a=create();a.ingest(packet(1,20,[0,0],[0,0],[20,20]));
 assert.equal(a.advice(0).mode,'balanced');
 a.ingest(packet(2,29,[0,0],[0,1],[33,30]));
 assert.equal(a.advice(0).mode,'attack-stall');assert.equal(a.advice(0).window.shots[0],0);
 assert.equal(a.ingest(packet(1,80,[0,4])),false);assert.equal(a.advice(0).minute,29);
 a.reset();a.ingest(packet(3,70));assert.equal(a.advice(0).window,null);
});
test('short-handed side never receives formation command',()=>{
 const a=create(),p=packet(1,75,[0,1]);p.frame.players.shift();a.ingest(p);
 assert.equal(a.advice(0).mode,'short-handed');assert.equal(a.advice(0).values.formation,0);
});
test('fatigue suggestions use compatible unused reserve and avoid low fitness or used players',()=>{
 const a=create(),p=packet(1,60);
 p.players=[{team:0,nativeId:1,name:'Tired',position:'ST',rating:80,reserve:false},{team:0,nativeId:23,name:'Fresh',position:'ST',rating:78,startFitness:96,reserve:true},{team:0,nativeId:24,name:'Used',position:'ST',rating:99,startFitness:100,reserve:true},{team:0,nativeId:25,name:'Keeper',position:'GK',rating:99,startFitness:100,reserve:true}];
 p.frame.participation=[{team:0,databaseId:1,active:true,nominalMs:3600000,cardCode:0,fatigueFactor:.6},{team:0,databaseId:23,active:false,nominalMs:0,cardCode:0},{team:0,databaseId:24,active:false,nominalMs:120000,cardCode:0},{team:0,databaseId:25,active:false,nominalMs:0,cardCode:0}];
 a.ingest(p);assert.equal(a.advice(0).changes[0].in,'Fresh');assert.equal(a.advice(0).changes.length,1);
});
test('counter regression discards old history, no opponent shape without telemetry',()=>{
 const a=create();a.ingest(packet(1,25,[0,0],[3,3],[30,30]));const p=packet(2,35,[0,0],[0,0],[1,1]);delete p.frame.players[0].formationTarget;a.ingest(p);
 assert.equal(a.advice(0).window,null);assert.equal(a.advice(1).rivalShape,null);
});
