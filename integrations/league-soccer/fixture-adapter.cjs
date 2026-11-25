'use strict';
const fs = require('node:fs');
const Model = require('../../player-model.js');
const Tactics = require('../../tactics.js');
const {formations} = require('../../football-sim.js');
const nativeStats = Object.freeze({
  "physical_balance": "balance",
  "physical_reaction": "reactions",
  "physical_acceleration": "acceleration",
  "physical_velocity": "pace",
  "physical_stamina": "endurance",
  "physical_agility": "agility",
  "physical_shotpower": "strength",
  "technical_standingtackle": "tackling",
  "technical_slidingtackle": "tackling",
  "technical_ballcontrol": "dribbling",
  "technical_dribble": "dribbling",
  "technical_shortpass": "passing",
  "technical_highpass": "crossing",
  "technical_header": "heading",
  "technical_shot": "shooting",
  "technical_volley": "shooting",
  "mental_calmness": "composure",
  "mental_workrate": "endurance",
  "mental_resilience": "composure",
  "mental_defensivepositioning": "tackling",
  "mental_offensivepositioning": "vision",
  "mental_vision": "vision"
});
const nativeRole = {GK:'GK',CB:'CB',LB:'LB',RB:'RB',LWB:'LB',RWB:'RB',DM:'DM',CM:'CM',AM:'AM',LM:'LM',RM:'RM',ST:'CF',CF:'CF',LW:'CF',RW:'CF'};
const clamp = (n,a,b)=>Math.max(a,Math.min(b,n));
const requireValue = (value,message)=>{if(!value)throw new Error(message)};
const unsupported = ['tempo','aggression','mentality','marking','offside','line','fullbacks','crossing','shooting','onLoss'];
function convert(config) {
 requireValue(config && typeof config==='object','Missing frozen fixture');
 requireValue(config.matchMinutes===5,'Expected five-minute fixture');
 requireValue(Number.isInteger(config.seed)&&config.seed>=0&&config.seed<=0xffffffff,'Invalid fixture seed');
 const teams = [0,1].map(team=>{
  const formation=team?config.awayFormation:config.formation;
  const roster=team?config.awayPlayers:config.players;
  const starters=team?config.awayStarters:config.starters;
  const rawTactics=team?config.awayTactics:config.tactics;
  requireValue(Object.hasOwn(formations,formation)&&Object.hasOwn(Model.slots,formation),'Unsupported formation');
  requireValue(Array.isArray(roster)&&Array.isArray(starters)&&starters.length===11&&new Set(starters).size===11,'Invalid starting eleven');
  requireValue(new Set(roster.map(p=>p.id)).size===roster.length,'Duplicate roster IDs');
  const t=Tactics.normalize(rawTactics);
  const players=starters.map((id,slot)=>{
   const source=roster.find(p=>p.id===id);
   requireValue(source&&source.owned!==false,'Unavailable starter '+id);
   requireValue(typeof id==='string'||Number.isSafeInteger(id),'Invalid roster identity');
   requireValue(typeof source.name==='string'&&source.name.trim(),'Invalid player name');
   const pos=Model.slotFor(formation,slot),f=formations[formation][slot],effective=Model.forSlot(source,pos);
   const stats=Object.fromEntries(Object.entries(nativeStats).map(([key,attr])=>[key,clamp(effective[attr]/100,.01,1)]));
   return {nativeId:team*11+slot+1,rosterId:id,slot,position:pos.position,role:nativeRole[pos.position],x:f[1]/52.5,y:-f[2]/34,name:source.name.replace(/[\u0000-\u001f\u007f]/g,' ').slice(0,120),rating:clamp(effective.skill/100,.01,1),stats};
  });
  // Preserve exact selected slot identities; native GK-first order is explicit.
  players.sort((a,b)=>Number(b.role==='GK')-Number(a.role==='GK')||a.x-b.x||a.slot-b.slot);
  return {team,formation,players,tactics:{team_pressure:t.press/100,counter_attack:t.onWin==='counter'||t.playstyle==='counter'?.9:t.playstyle==='possession'?.2:.5,support_distance:t.passing==='short'?.2:t.passing==='direct'?.8:t.width==='wide'?.75:t.width==='narrow'?.25:.5},unsupported};
 });
 return {schema:1,seed:config.seed,matchMinutes:5,teams};
}
function serialize(manifest){
 const lines=['TRIBUN1'];
 for(const team of manifest.teams){
  const t=team.tactics;
  lines.push([team.team,t.team_pressure,t.counter_attack,t.support_distance].join(' '));
  for(const p of team.players){
   lines.push([p.nativeId,p.role,p.x,p.y,p.rating,JSON.stringify(p.name),...Object.keys(nativeStats).map(k=>p.stats[k])].join(' '));
  }
 }
 return lines.join('\n')+'\n';
}
function demo(){
 const f=['4-3-3','4-2-3-1'],r=f.map((formation,team)=>Model.demoTeam(team,formation).map((p,i)=>({...p,id:'pilot-'+team+'-'+i,name:'Tribun '+team+' / '+i,shooting:team===0?92:55})));
 return {seed:2026,matchMinutes:5,formation:f[0],awayFormation:f[1],players:r[0],awayPlayers:r[1],starters:r[0].map(p=>p.id),awayStarters:r[1].map(p=>p.id),tactics:{press:85,onWin:'counter',passing:'direct'},awayTactics:{press:30,playstyle:'possession',passing:'short'}};
}
if(require.main===module){
 const [input,output]=process.argv.slice(2);
 requireValue(input&&output,'Usage: node fixture-adapter.cjs <config.json|--demo> <native-fixture.txt>');
 const manifest=convert(input==='--demo'?demo():JSON.parse(fs.readFileSync(input,'utf8')));
 fs.writeFileSync(output,serialize(manifest));
 fs.writeFileSync(output+'.json',JSON.stringify(manifest,null,2)+'\n');
}
module.exports={convert,serialize,demo,nativeStats};
