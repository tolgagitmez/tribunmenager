'use strict';
const fs=require('node:fs');
const {demo,convert}=require('./fixture-adapter.cjs');
const Model=require('../../player-model.js');
const formations=['4-3-3','4-2-3-1','4-4-2','3-5-2','5-3-2','4-5-1'];
const styles=['balanced','counter','possession'];
const passing=['mixed','short','direct'];
function make(options={}){
 const {seed=2026,homeFormation='4-3-3',awayFormation='4-2-3-1',homeStyle='balanced',awayStyle='balanced',homePress=55,awayPress=55,homePassing='mixed',awayPassing='mixed'}=options;
 if(!Number.isSafeInteger(seed)||seed<0||seed>0xffffffff)throw Error('Invalid seed');
 if(![homeFormation,awayFormation].every(f=>formations.includes(f)))throw Error('Invalid formation');
 if(![homeStyle,awayStyle].every(s=>styles.includes(s)))throw Error('Invalid style');
 if(![homePassing,awayPassing].every(s=>passing.includes(s)))throw Error('Invalid passing');
 if(![homePress,awayPress].every(n=>Number.isInteger(n)&&n>=0&&n<=100))throw Error('Invalid pressure');
 const config={...demo(),seed,formation:homeFormation,awayFormation};
 const makeRoster=(team,formation)=>Model.demoTeam(team,formation).map((p,i)=>({...p,id:i,uid:'beta-'+team+'-'+i,name:(team?'Deplasman':'Ev sahibi')+' '+(i+1)}));
 config.players=makeRoster(0,homeFormation);config.awayPlayers=makeRoster(1,awayFormation);
 config.starters=config.players.map(p=>p.id);config.awayStarters=config.awayPlayers.map(p=>p.id);
 const tactics=(style,press,pass)=>({press,passing:pass,playstyle:style==='possession'?'possession':style==='counter'?'counter':'balanced',onWin:style==='counter'?'counter':'normal'});
 config.tactics=tactics(homeStyle,homePress,homePassing);config.awayTactics=tactics(awayStyle,awayPress,awayPassing);
 const manifest=convert(config);
 return {config,manifest};
}
if(require.main===module){
 const data=make(JSON.parse(process.argv[2]||'{}'));
 fs.writeFileSync(process.argv[3],JSON.stringify(data.config,null,2)+'\n',{flag:'wx'});
}
module.exports={make,formations,styles,passing};
