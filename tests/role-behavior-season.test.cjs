'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const Model=require('../player-model.js'),{Match}=require('../football-sim.js');
function raw(position,id,preferredFoot='right'){
 const map={CB:'DEF',LB:'DEF',RB:'DEF',DM:'MID',AM:'MID',CM:'MID'};
 const base={id,name:position+' '+id,pos:map[position],subposition:position,
  positions:[position],preferredFoot,rating:80,fitness:100,form:100,
  passing:79,vision:79,tackling:79,pace:79,acceleration:79,dribbling:79,shooting:79};
 return base;
}
test('equally rated CB, LB, DM and AM retain the same overall but different pitch role habits',()=>{
 const positions=['CB','LB','DM','AM'],slot=p=>({role:['CB','LB'].includes(p)?'DEF':'MID',position:p});
 const rows=positions.map((name,i)=>Model.forSlot(raw(name,i,name==='LB'?'left':'right'),slot(name)));
 assert.deepEqual(rows.map(p=>p.baseRating),[80,80,80,80]);
 assert.deepEqual(rows.map(p=>p.skill),[80,80,80,80]);
 assert.equal(rows[0].roleFit,1);assert.equal(rows[1].roleFit,1);
 assert(rows[1].roleHabits.overlap>rows[0].roleHabits.overlap);
 assert(rows[2].roleHabits.hold>rows[3].roleHabits.hold);
 assert(rows[2].roleHabits.intercept>rows[3].roleHabits.intercept);
 assert(rows[3].roleHabits.forward>rows[2].roleHabits.forward);
 assert(rows[2].roleHabits.shortPass>rows[3].roleHabits.shortPass);
});
test('specific position familiarity and wrong-foot flank preference reduce fit even in the same broad sector',()=>{
 const lb=raw('LB',11,'left'),cb=raw('CB',12),dm=raw('DM',13),am=raw('AM',14);
 assert.equal(Model.fit(lb,'LB'),1);
 assert(Model.fit(lb,'CB')<1&&Model.fit(lb,'CB')>.80);
 assert(Model.fit(cb,'LB')<1);
 assert(Model.fit(dm,'AM')<Model.fit(dm,'DM'));
 assert(Model.fit(am,'DM')<Model.fit(am,'AM'));
 assert(Model.fit({...lb,preferredFoot:'right'},'LB')<Model.fit(lb,'LB'));
 assert.equal(Model.fit({...lb,preferredFoot:'both'},'LB'),1);
 assert.equal(Model.fit({...lb,preferredFoot:undefined},'LB'),1,'unknown foot must not be guessed as wrong');
});
test('real Match defensive and offensive instructions distinguish DM/AM and fullback/centre-back',()=>{
 const team=Model.demoTeam(0,'4-2-3-1');const ids=team.map(p=>p.id);
 for(const [i,p]of [[2,'AM'],[4,'DM'],[6,'LB'],[7,'CB']]){
  team[i]={...raw(p,i,p==='LB'?'left':'right'),id:i};
 }
 const m=new Match({seed:14,formation:'4-2-3-1',players:team,starters:ids});
 m.restart=null;m.kick=null;m.goalPause=null;m.flight=null;
 m.lastTeam=0;m.owner=m.players[0];m.ball={x:4,z:-10,y:.11,vx:0,vz:0,vy:0};
 m.plan();
 const players=Object.fromEntries([[2,'AM'],[4,'DM'],[6,'LB'],[7,'CB']].map(([i,pos])=>[pos,m.players[i]]));
 assert.equal(m.teamRole(players.DM),'anchor');
 assert.equal(m.teamRole(players.AM),'playmaker');
 assert.equal(m.teamRole(players.LB),'fullback');
 assert.equal(m.teamRole(players.CB),'centre-back');
 const dm=m.targets.get(players.DM),am=m.targets.get(players.AM),lb=m.targets.get(players.LB),cb=m.targets.get(players.CB);
 assert(dm&&am&&lb&&cb,'tactics must produce real targets');
 assert(am.x>dm.x,'AM attacks between lines; DM protects zone: '+JSON.stringify({dm,am}));
 assert(lb.x>cb.x,'fullback supports wide build-out while CB holds: '+JSON.stringify({lb,cb}));
 // The two equal-rating players actually attempt different movements, not just labels.
 players.DM.x=players.AM.x=-10;players.DM.z=players.AM.z=0;
 const before=[players.DM.x,players.AM.x];
 for(let i=0;i<75;i++){m.move(players.DM,dm,1/60);m.move(players.AM,am,1/60);}
 assert(players.AM.x-players.DM.x>1.0,'real pitch movement must diverge');
 assert(before.every(n=>n===-10));
});
test('the same stored slot ID keeps original identity while bench sub earns separate playing minutes',()=>{
 const players=Model.demoTeam(0,'4-3-3');players.push(raw('AM',99));
 const m=new Match({seed:9,players,starters:players.slice(0,11).map(p=>p.id),rules:{minPlayers:1,periodSeconds:30,halftimeSeconds:0,addedTime:false}});
 for(let i=0;i<42;i++)m.step(1/60);
 const old=m.players[0].rosterId;
 const prior=m.appearanceReport().find(a=>a.team===0&&a.rosterId===old);
 assert(prior&&prior.seconds>0);
 assert.equal(m.substitute(0,99).ok,true);
 for(let i=0;i<42;i++)m.step(1/60);
 const rows=m.appearanceReport();
 assert(rows.find(a=>a.team===0&&a.rosterId===old)?.seconds>0);
 assert(rows.find(a=>a.team===0&&a.rosterId===99)?.seconds>0);
 assert.equal(m.players[0].rosterId,99);
 assert.equal(rows.filter(a=>a.team===0&&[old,99].includes(a.rosterId)).length,2);
});
