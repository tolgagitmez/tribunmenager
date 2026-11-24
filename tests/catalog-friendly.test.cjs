'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),F=require('../catalog-friendly.js'),{Match}=require('../football-sim');
function snap(t){return {schema:1,source:'api-football',teamId:t,teamUid:'api-football:team:'+t,name:'Fictional '+t,fetchedAt:'2026-11-24T00:00:00Z',players:Array.from({length:22},(_,i)=>({providerId:t*100+i,uid:'api-football:player:'+(t*100+i),name:'Synthetic '+i,pos:i<2?'GK':i<9?'DEF':i<16?'MID':'ATT',number:i+1,age:25}))}}
test('two catalog squads, all formations, role-correct selection and stable identities',()=>{
 const a=F.load(snap(1)),b=F.load(snap(2),'synthetic-varied');
 for(const f of Object.keys(require('../player-model.js').slots)){const c=F.build(a,b,{formation:f,awayFormation:f});assert.equal(c.starters.length,11);assert.equal(new Set(c.starters).size,11);assert.deepEqual(F.validate(c),c);}
 const c=F.build(a,b,{tactics:{press:83,tempo:45},awayTactics:{press:25}});
 const m=new Match(c);assert.equal(m.t[0].press,83);assert.equal(m.t[1].press,25);
 assert.equal(m.players.filter(p=>p.active&&!p.referee).length,22);assert(m.players.some(p=>p.rosterUid==='api-football:player:100'));
 for(let i=0;i<600;i++)m.step(1/60);assert(m.players.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.z)));
});
test('reject duplicated starters, wrong roles, insufficient roster, shared identities and injected context',()=>{
 const a=F.load(snap(1)),b=F.load(snap(2));
 const c=F.build(a,b);assert.throws(()=>F.build(a,a),/çakışan/);
 assert.throws(()=>F.build(a,b,{starters:Array(11).fill(0)}),/İlk 11/);
 const wrong=[...c.starters];[wrong[0],wrong[10]]=[wrong[10],wrong[0]];assert.throws(()=>F.build(a,b,{starters:wrong}),/mevki/);
 const raw=snap(2);raw.players[0].uid=snap(1).players[0].uid;assert.throws(()=>F.load(raw));
 const polluted={...c,fixture:{},transferProfileId:'bad',leagueToken:'bad',managerKicks:false};assert.deepEqual(F.validate(polluted),c);
});
test('single use session storage, no URL payload, no persistent saves',()=>{
 const data=new Map(),env={sessionStorage:{setItem:(k,v)=>data.set(k,v),getItem:k=>data.get(k),removeItem:k=>data.delete(k)},location:{href:''},get localStorage(){throw Error('persistent storage forbidden')}};
 const c=F.build(F.load(snap(1)),F.load(snap(2)));
 F.launch(c,env);assert.equal(env.location.href,'match.html?catalog=1');assert.deepEqual(F.consume(env),c);assert.equal(data.size,0);assert.throws(()=>F.consume(env));
});
