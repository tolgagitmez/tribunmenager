'use strict';
const fs=require('node:fs'),F=require('../catalog-friendly.js');
try{
 const {snapshots,mode}=JSON.parse(fs.readFileSync(0,'utf8'));
 if(!Array.isArray(snapshots)||snapshots.length!==6)throw Error('six teams required');
 const teams=new Set(),players=new Set(),names=new Set();
 const out=snapshots.map(s=>{
  const t=F.load(s,mode);
  if(teams.has(t.teamUid)||names.has(t.name.toLocaleLowerCase('tr-TR')))throw Error('duplicate team');
  teams.add(t.teamUid);names.add(t.name.toLocaleLowerCase('tr-TR'));
  for(const p of t.players){if(players.has(p.uid))throw Error('duplicate player');players.add(p.uid);}
  for(const [role,min] of Object.entries({GK:2,DEF:6,MID:6,ATT:4}))if(t.players.filter(p=>p.pos===role).length<min)throw Error('insufficient rotation');
  const starters=F.selectXI(t.players,'4-3-3');
  // Every supported formation is playable at season creation.
  for(const formation of Object.keys(require('../player-model.js').slots))F.selectXI(t.players,formation);
  return {...t,starters};
 });
 process.stdout.write(JSON.stringify(out));
}catch{process.stderr.write('Catalog league validation failed.\n');process.exitCode=1;}
