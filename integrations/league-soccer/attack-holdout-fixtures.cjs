'use strict';
// New seeds and swapped tactical intensity; never reuse training fixture IDs.
const fs=require('node:fs'),path=require('node:path');
const {demo,convert}=require('./fixture-adapter.cjs');
const out=process.argv[2];
if(!out)throw Error('Output directory required');
fs.mkdirSync(out,{recursive:true});
const scenarios=[
 ['holdout-high-press',91001,{press:75,passing:'short',tempo:75},{press:70,passing:'direct',onWin:'counter'}],
 ['holdout-low-block',91002,{press:35,passing:'mixed',tempo:45},{press:50,passing:'short',playstyle:'possession'}],
 ['holdout-direct',91003,{press:60,passing:'direct',onWin:'counter'},{press:40,passing:'mixed',tempo:60}]
];
for(const [name,seed,tactics,awayTactics] of scenarios){
 const config={...demo(),seed,tactics,awayTactics};
 const manifest=convert(config);
 fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(config,null,2)+'\n');
 console.log(JSON.stringify({name,seed,tactics:manifest.teams.map(t=>t.tactics)}));
}
