'use strict';
const fs=require('node:fs'),path=require('node:path');
const {demo,convert}=require('./fixture-adapter.cjs');
const out=process.argv[2];
if(!out)throw Error('Output directory required');
fs.mkdirSync(out,{recursive:true});
const scenarios=[
 ['counter-possession',2026,{press:85,onWin:'counter',passing:'direct'},{press:30,playstyle:'possession',passing:'short'}],
 ['balanced',2027,{press:55,passing:'mixed'},{press:55,passing:'mixed'}],
 ['possession-counter',2028,{press:35,playstyle:'possession',passing:'short'},{press:80,onWin:'counter',passing:'direct'}]
];
for(const [name,seed,tactics,awayTactics] of scenarios){
 const config={...demo(),seed,tactics,awayTactics};
 const manifest=convert(config);
 fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(config,null,2)+'\n');
 console.log(JSON.stringify({name,seed,tactics:manifest.teams.map(t=>t.tactics)}));
}
