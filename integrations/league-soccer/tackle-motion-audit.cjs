'use strict';
const fs=require('node:fs'),R=require('./native-replay.js');
const frames=R.parse(fs.readFileSync(process.argv[2],'utf8'));
if(!frames.every(f=>Array.isArray(f.nativeFouls)))throw Error('Native referee event trace missing');
const counts={standingBallContacts:0,slidingBallContacts:0,tackleTrips:0,recordedFouls:0};
for(const f of frames){
 for(const e of f.nativeContacts||[]){if(e.kind==='standing-tackle')counts.standingBallContacts++;if(e.kind==='sliding-tackle')counts.slidingBallContacts++;}
 for(const d of f.nativeDuels||[])if(d.kind==='tackle-trip')counts.tackleTrips++;
 counts.recordedFouls+=f.nativeFouls.length;
}
console.log(JSON.stringify({schema:1,authoritative:false,counts,note:'Separate source event counts; not successful steals, foul-to-touch causality or visual quality.'},null,2));
