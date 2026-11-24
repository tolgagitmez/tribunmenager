'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('../api-football-ratings.cjs'),M=require('../player-model.js'),{Match}=require('../football-sim');
const {toGameRoster}=require('../api-football-roster.cjs');
const uid=i=>'api-football:player:'+i;
const positions=['GK','DEF','MID','ATT'];
const ids=Array.from({length:300},(_,i)=>i+1);
const mean=a=>a.reduce((x,y)=>x+y,0)/a.length;
function snapshot(team){
 return {schema:1,source:'api-football',teamId:team,teamUid:'api-football:team:'+team,fetchedAt:'2026-11-24T00:00:00Z',
 players:Array.from({length:18},(_,i)=>({providerId:team*100+i,uid:uid(team*100+i),name:'Test '+i,pos:i<2?'GK':i<8?'DEF':i<14?'MID':'ATT',number:i+1,age:24}))};
}
test('neutral remains the default; all varied values explicitly synthetic',()=>{
 const n=R.buildProfile(uid(7),'ATT'),v=R.buildProfile(uid(7),'ATT','synthetic-varied');
 assert.equal(n.rating,80);assert.deepEqual(n.skills,{});
 assert.equal(v.ratingProvenance.observed,false);assert.equal(v.ratingProvenance.confidence,null);
 assert.deepEqual(Object.keys(v.skills).sort(),M.attributes.slice().sort());
 assert(Object.values(v.ratingProvenance.attributes).every(x=>x==='synthetic'));
 assert.throws(()=>R.buildProfile(uid(7),'ATT','real'),/Unknown rating mode/);
});
test('1200 fictional profiles bounded, centered by role, differentiated within each role',()=>{
 for(const pos of positions){
  const rows=ids.map(i=>R.buildProfile(uid(i),pos,'synthetic-varied'));
  assert(rows.every(r=>Object.values(r.skills).every(n=>Number.isInteger(n)&&n>=1&&n<=99)));
  assert(rows.every(r=>r.rating===R.overall(pos,r.skills)&&r.rating>=65&&r.rating<=95));
  assert(Math.abs(mean(rows.map(r=>r.rating))-80)<3,pos+' not centered');
  assert(new Set(rows.map(r=>JSON.stringify(r.skills))).size>280);
  assert(new Set(rows.map(r=>r.rating)).size>=5);
 }
 const g=R.baseline('GK'),d=R.baseline('DEF'),m=R.baseline('MID'),a=R.baseline('ATT');
 assert(g.goalkeeping>a.goalkeeping&&d.tackling>a.tackling&&m.passing>g.passing&&a.shooting>d.shooting);
 assert.throws(()=>R.overall('GK',{goalkeeping:Infinity}),/Invalid skill/);
});
test('unchanged player UID and broad role survive transfer, rename, age and refresh',()=>{
 const s=snapshot(1),a=toGameRoster(s,{ratingMode:'synthetic-varied'});
 const t={...s,teamId:2,teamUid:'api-football:team:2',fetchedAt:'2026-11-25T00:00:00Z',
 players:s.players.map(p=>({...p,name:'Renamed',age:40})).reverse()};
 const b=toGameRoster(t,{ratingMode:'synthetic-varied'});
 for(let i=0;i<a.length;i++){
  assert.equal(a[i].uid,b[i].uid);assert.equal(a[i].rating,b[i].rating);
  for(const k of M.attributes)assert.equal(a[i][k],b[i][k]);
  assert.equal(b[i].preferredFoot,'unknown');assert.deepEqual(b[i].positions,[]);
  assert.equal(b[i].ratingProvenance.observed,false);
 }
});
test('position weighted overall responds to relevant abilities only',()=>{
 const p=R.buildProfile(uid(72),'GK','synthetic-varied'),s={...p.skills};
 s.shooting=99;assert.equal(R.overall('GK',s),p.rating);
 s.goalkeeping=Math.min(99,s.goalkeeping+10);assert(R.overall('GK',s)>p.rating);
});
test('actual Match receives differentiated effective skills and preserves stable roster identities',()=>{
 const a=toGameRoster(snapshot(1),{ratingMode:'synthetic-varied'}),b=toGameRoster(snapshot(2),{ratingMode:'synthetic-varied'});
 // Pick 4 defenders, 3 midfielders, 3 attackers and a keeper by broad role.
 const xi=p=>[...p.filter(x=>x.pos==='ATT').slice(0,3),...p.filter(x=>x.pos==='MID').slice(0,3),...p.filter(x=>x.pos==='DEF').slice(0,4),...p.filter(x=>x.pos==='GK').slice(0,1)].map(x=>x.id);
 const m=new Match({seed:91,players:a,awayPlayers:b,starters:xi(a),awayStarters:xi(b),individualAI:true});
 const home=m.players.filter(p=>p.team===0&&p.active&&!p.referee);
 assert.equal(home.length,11);
 for(const p of home){
  const raw=a.find(x=>x.uid===p.rosterUid);
  assert(raw);const expected=M.forSlot(raw,M.slotFor('4-3-3',p.index));
  assert.equal(p.skill,expected.skill);
  assert.equal(p.passing,expected.passing);assert.equal(p.pace,expected.pace);
 }
 const mids=home.filter(p=>p.role==='MID');assert(new Set(mids.map(p=>p.passing)).size>1);
 for(let i=0;i<600;i++)m.step(1/60);
 assert(m.players.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.z)));
});
