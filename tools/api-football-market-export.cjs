'use strict';
// Local-only pipe adapter. No network, no published data; all output is consumed
// by the trusted Python import command, not an Actions artifact.
const fs=require('node:fs'),{toGameRoster}=require('../api-football-roster.cjs');
function marketRows(snapshots,ratingMode='neutral'){
 if(!Array.isArray(snapshots)||!snapshots.length)throw Error('No snapshots');
 const seen=new Set(),players=[];let skipped=0;
 for(const s of snapshots){
  for(const p of toGameRoster(s,{ratingMode})){
   if(seen.has(p.uid))throw Error('Duplicate provider player across squads; refresh conflicting teams together');
   seen.add(p.uid);
   if(!Number.isInteger(p.age)||p.age<16||p.age>50){skipped++;continue}
   players.push({...p,providerId:'api-football',externalId:String(p.providerId),
    club:s.name,updatedAt:s.fetchedAt,source:'api-football'});
  }
 }
 if(!players.length)throw Error('No eligible market players');
 return {version:1,players,skippedUnknownAge:skipped};
}
module.exports={marketRows};
if(require.main===module){
 try{
  const input=JSON.parse(fs.readFileSync(0,'utf8'));
  process.stdout.write(JSON.stringify(marketRows(input.snapshots,input.ratingMode)));
 }catch{process.stderr.write('Market conversion failed. No raw provider data logged.\n');process.exitCode=1;}
}
