'use strict';
(function(root){
const createRoster=()=>[
 ['Mert Yıldız','GK',92,96,88,1,10],['Emre Kaya','DEF',85,93,83,2,9],['Baran Çelik','DEF',90,90,91,4,7],['Diego Rojas','DEF',88,87,84,5,8],['Can Aydın','DEF',84,96,80,3,6],['João Mendes','MID',91,91,91,6,4],['Umut Kara','MID',86,88,85,10,5],['Arda Akın','MID',88,94,90,8,3],['Lucas Costa','ATT',89,89,87,11,2],['Emir Demir','ATT',96,93,97,9,0],['Efe Yılmaz','ATT',92,88,92,7,1],
 ['Ozan Arslan','GK',78,95,85,12,10],['Martin Moreno','DEF',82,95,81,14,8],['Eray Emre','DEF',79,90,82,15,6],['Rafael Santos','MID',81,89,84,16,5],['Deniz Çetin','MID',80,94,80,17,3],['Ade Okafor','ATT',83,87,87,18,2],['Barış Aslan','ATT',77,95,82,19,1]
].map((r,i)=>({id:i,name:r[0],pos:r[1],rating:r[2],fitness:r[3],form:r[4],number:r[5],face:r[6],xp:0,passing:60+(i*9)%37,shooting:55+(i*13)%42,tackling:50+(i*11)%42,dribbling:Math.min(97,(r[1]==='ATT'?82:r[1]==='MID'?76:r[1]==='DEF'?60:40)+(i*7)%15),pace:Math.min(97,(r[1]==='ATT'?82:r[1]==='MID'?76:r[1]==='DEF'?72:52)+(i*5)%14),agility:Math.min(97,(r[1]==='ATT'?83:r[1]==='MID'?78:65)+(i*3)%14),heading:Math.min(97,(r[1]==='ATT'?82:r[1]==='DEF'?83:r[1]==='MID'?66:50)+(i*5)%13),crossing:Math.min(97,(r[1]==='ATT'?78:r[1]==='MID'?72:r[1]==='DEF'?67:40)+(i*9)%16)}));
const FORM={
 '4-3-3':[['ATT',22,15],['ATT',50,13],['ATT',78,15],['MID',25,40],['MID',50,43],['MID',75,40],['DEF',16,70],['DEF',39,71],['DEF',61,71],['DEF',84,70],['GK',50,89]],
 '4-2-3-1':[['ATT',50,12],['MID',19,32],['MID',50,31],['MID',81,32],['MID',36,50],['MID',64,50],['DEF',16,72],['DEF',39,73],['DEF',61,73],['DEF',84,72],['GK',50,90]],
 '4-4-2':[['ATT',37,17],['ATT',63,17],['MID',15,40],['MID',38,45],['MID',62,45],['MID',85,40],['DEF',16,72],['DEF',39,73],['DEF',61,73],['DEF',84,72],['GK',50,90]],
 '3-5-2':[['ATT',38,16],['ATT',62,16],['MID',15,36],['MID',32,48],['MID',50,39],['MID',68,48],['MID',85,36],['DEF',27,72],['DEF',50,76],['DEF',73,72],['GK',50,90]],
 '5-3-2':[['ATT',38,16],['ATT',62,16],['MID',25,42],['MID',50,46],['MID',75,42],['DEF',12,70],['DEF',30,73],['DEF',50,75],['DEF',70,73],['DEF',88,70],['GK',50,90]],
 '4-5-1':[['ATT',50,14],['MID',15,37],['MID',31,46],['MID',50,38],['MID',69,46],['MID',85,37],['DEF',16,73],['DEF',39,74],['DEF',61,74],['DEF',84,73],['GK',50,90]]
};

const fit=(p,slot)=>p.pos===slot?1:p.pos==='GK'||slot==='GK'?.45:((p.pos==='MID'&&slot==='ATT')||(p.pos==='ATT'&&slot==='MID'))?.87:((p.pos==='DEF'&&slot==='MID')||(p.pos==='MID'&&slot==='DEF'))?.82:.66;
const reorder=(ids,formation,players)=>{const pool=ids.slice(),answer=[];for(const slot of FORM[formation]){pool.sort((a,b)=>(fit(players[b],slot[0])*150+players[b].rating*.11)-(fit(players[a],slot[0])*150+players[a].rating*.11));answer.push(pool.shift());}return answer;};
function loadRoster(saved){const base=createRoster();return (Array.isArray(saved?.players)&&saved.players.length>=11?saved.players:base).map((p,i)=>({...base[i],...p,id:i}));}
function repairStarters(ids,players,formation){
 const slots=FORM[formation]||FORM['4-3-3'],owned=players.filter(p=>p&&p.owned!==false),used=new Set(),answer=[];
 const old=Array.isArray(ids)?ids:[];
 for(let i=0;i<11;i++){
  let id=old[i];
  if(!Number.isInteger(id)||!players[id]||players[id].owned===false||used.has(id)){
   const remaining=owned.filter(p=>!used.has(p.id)),unselected=remaining.filter(p=>!old.includes(p.id)),pool=unselected.length?unselected:remaining;
   pool.sort((a,b)=>(fit(b,slots[i][0])*150+b.rating*.11)-(fit(a,slots[i][0])*150+a.rating*.11));id=pool[0]?.id;
  }
  if(id!==undefined){answer.push(id);used.add(id);}
 }
 return answer;
}
const api={createRoster,loadRoster,repairStarters,formations:FORM,fit,reorder,starters:[8,9,10,7,5,6,4,2,3,1,0],key:'tribun-manager-pro09'};root.TribunClubData=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
