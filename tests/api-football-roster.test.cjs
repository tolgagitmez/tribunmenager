'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {toGameRoster}=require('../api-football-roster.cjs');
const {Match}=require('../football-sim');
function snapshot(team){
 return {schema:1,source:'api-football',teamId:team,teamUid:'api-football:team:'+team,fetchedAt:'2026-11-24T00:00:00Z',
 players:Array.from({length:12},(_,i)=>({providerId:team*100+i,uid:'api-football:player:'+(team*100+i),name:'Synthetic '+team+' '+i,
 pos:i===0?'GK':i<5?'DEF':i<9?'MID':'ATT',number:i+1,rating:null,preferredFoot:'unknown'}))};
}
test('stable provider UID, dense local indices, synthetic provenance and unknown foot',()=>{
 const s=snapshot(1),a=toGameRoster(s);s.players.reverse();assert.deepEqual(toGameRoster(s),a);
 assert.equal(a[0].uid,'api-football:player:100');assert.equal(a[0].preferredFoot,'unknown');
 assert.equal(a[0].ratingSource,'synthetic-neutral');assert.equal(a[0].subposition,null);
 assert(a.every((p,i)=>p.id===i&&p.profileProvenance.inferredAttributes.length>0));
});
test('reject duplicate identities and skip unknown roles without guessing',()=>{
 const s=snapshot(1);s.players[11].pos=null;assert.equal(toGameRoster(s).length,11);
 s.players[11].providerId=s.players[0].providerId;s.players[11].uid=s.players[0].uid;
 assert.throws(()=>toGameRoster(s),/duplicate/);
});
test('synthetic identity snapshots enter actual match engine without editing source data',()=>{
 const s=snapshot(1),before=JSON.stringify(s),a=toGameRoster(s),b=toGameRoster(snapshot(2));
 const m=new Match({seed:91,players:a,awayPlayers:b,starters:a.slice(0,11).map(p=>p.id),awayStarters:b.slice(0,11).map(p=>p.id),individualAI:true});
 for(let i=0;i<600;i++)m.step(1/60);
 assert.equal(m.players.filter(p=>p.active&&!p.referee).length,22);
 assert(m.players.some(p=>p.rosterUid==='api-football:player:100'));
 assert(m.players.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.z)));
 assert.equal(JSON.stringify(s),before);
});
