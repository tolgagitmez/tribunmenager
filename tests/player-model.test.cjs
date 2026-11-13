'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const M=require('../player-model.js'), C=require('../club-data.js');

test('browser profile data exactly matches the canonical JSON used by Python and Node',()=>{
 const context={};vm.runInNewContext(fs.readFileSync(require.resolve('../player-model-profiles.js'),'utf8'),context);
 assert.deepEqual(JSON.parse(JSON.stringify(context.TribunPlayerProfiles)),M.profiles);
 vm.runInNewContext(fs.readFileSync(require.resolve('../player-model.js'),'utf8'),context);
 assert.equal(context.TribunPlayerModel.quality({pos:'ATT',rating:80,fitness:70,form:60},'MID'),M.quality({pos:'ATT',rating:80,fitness:70,form:60},'MID'));
});

test('quality retains the squad screen contract for all generic roles, form and fitness',()=>{
 for(const pos of ['GK','DEF','MID','ATT'])for(const slot of ['GK','DEF','MID','ATT'])for(const fitness of [0,50,95,100])for(const form of [0,80,100]){
  const fit=pos===slot?1:pos==='GK'||slot==='GK'?.45:pos==='MID'&&slot==='ATT'||pos==='ATT'&&slot==='MID'?.87:pos==='DEF'&&slot==='MID'||pos==='MID'&&slot==='DEF'?.82:.66;
  const p={pos,rating:83,fitness,form};
  assert.equal(M.quality(p,slot),Math.round(83*fit*(.83+.17*fitness/100)*(.91+.09*form/100)));
  assert.equal(C.fit(p,slot),fit);
 }
});

test('form, position and fitness have distinct, inspectable behavior effects',()=>{
 const p={pos:'ATT',rating:80,form:100,fitness:100,archetype:'poacher'};
 const fresh=M.forSlot(p,'ATT'),tired=M.forSlot({...p,fitness:25},'ATT'),off=M.forSlot(p,'DEF'),poor=M.forSlot({...p,form:0},'ATT');
 assert.ok(tired.pace<fresh.pace);assert.ok(tired.acceleration<fresh.acceleration);
 assert.equal(tired.passing,fresh.passing);assert.equal(off.pace,fresh.pace);
 assert.ok(off.passing<fresh.passing);assert.ok(poor.shooting<fresh.shooting);
 assert.equal(off.strength,fresh.strength);assert.equal(poor.endurance,fresh.endurance);
 assert.equal(fresh.model.factors.position,1);assert.equal(off.model.factors.position,.66);
});

test('equal ratings preserve authored football identities independently of array ID',()=>{
 const examples=[['poacher','ATT'],['stopper','DEF'],['playmaker','MID']].map(([archetype,pos])=>M.forSlot({archetype,pos,rating:80,form:100,fitness:100},pos));
 assert.deepEqual(examples.map(p=>p.skill),[80,80,80]);
 assert.ok(examples[0].pace>examples[1].pace);assert.ok(examples[1].strength>examples[0].strength);assert.ok(examples[2].vision>examples[0].vision);
 const a=M.normalize({id:1,pos:'ATT',rating:80}),b=M.normalize({id:928,pos:'ATT',rating:80});
 for(const key of [...M.attributes,'preferredFoot','archetype'])assert.equal(a[key],b[key]);
 assert.equal(a.preferredFoot,'unknown');assert.equal(M.forSlot(a,'ATT').model.preferredFootSource,'unknown');
});

test('explicit foot, technical and physical observations override default profiles',()=>{
 const p={pos:'MID',preferredFoot:'left',weakFoot:32,passing:67,pace:96,strength:91,vision:99,form:100,fitness:100};
 const field=M.forSlot(p,'MID');assert.equal(field.preferredFoot,0);assert.equal(field.weakFoot,32);assert.equal(field.passing,67);assert.equal(field.strength,91);assert.equal(field.vision,99);
 assert.equal(M.forSlot({...p,preferredFoot:'both'},'MID').weakFoot,99);
 assert.equal(M.forSlot({...p,preferredFoot:'right'},'MID').preferredFoot,1);
});

test('legacy missing identities remain inferred, never filled from a seed player at the same index',()=>{
 const saved={players:Array.from({length:11},(_,id)=>({id,name:'Imported '+id,pos:'MID',rating:70}))};
 const players=C.loadRoster(saved);assert.equal(players[0].preferredFoot,undefined);assert.equal(players[0].archetype,undefined);assert.equal(players[0].passing,undefined);
 const field=M.forSlot(players[0],'MID');assert.ok(field.model.inferredAttributes.includes('passing'));assert.equal(field.model.preferredFootSource,'unknown');
 assert.ok(C.createRoster().every(p=>p.preferredFoot&&p.archetype&&p.dataKind==='demo'));
});

test('normalization handles malformed optional legacy values without mutating source',()=>{
 const raw={pos:'DEF',rating:NaN,fitness:null,form:'',pace:Infinity,preferredFoot:'bad',positions:['CB','CB','bad']},before={...raw};
 const p=M.normalize(raw);assert.equal(p.rating,80);assert.equal(p.fitness,95);assert.equal(p.form,80);assert.equal(p.pace,M.profiles.stopper.pace);assert.deepEqual(p.positions,['CB']);assert.deepEqual(raw,before);
 assert.equal(M.normalize(null).pos,'MID');
});

test('every supported formation has eleven mapped roles and explicit demo identities',()=>{
 for(const formation of Object.keys(C.formations)){
  const players=M.demoTeam(1,formation);assert.equal(players.length,11);assert.equal(new Set(players.map(p=>p.id)).size,11);
  players.forEach((p,i)=>{const slot=M.slotFor(formation,i);assert.equal(slot.role,C.formations[formation][i][0]);assert.equal(M.fit(p,slot),1);assert.equal(p.dataKind,'demo');assert.equal(p.subposition,slot.position);});
 }
});

test('normalizing a normalized record retains inference until its default value is edited',()=>{
 const first=M.normalize({pos:'MID',preferredFoot:'both'}),second=M.normalize(first);
 assert.deepEqual(second,first);assert.deepEqual(M.forSlot(first,'MID').model.inferredAttributes,first.profileProvenance.inferredAttributes);
 const edited=M.normalize({...first,passing:67});assert(!edited.profileProvenance.inferredAttributes.includes('passing'));assert(edited.profileProvenance.inferredAttributes.includes('pace'));
 const explicit=M.normalize({...first,archetype:'ballWinner'});assert.equal(explicit.profileProvenance.archetypeSource,'provided');
});
