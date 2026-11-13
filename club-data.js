'use strict';
(function(root){
const Model=root.TribunPlayerModel||(typeof require==='function'?require('./player-model.js'):null);
// Fictional seed players have authored profiles; array order only assigns roster IDs.
const seed=[
 ['Mert Yıldız','GK',92,96,88,1,10,'goalkeeper','GK','right'],
 ['Emre Kaya','DEF',85,93,83,2,9,'fullback','RB','right'],
 ['Baran Çelik','DEF',90,90,91,4,7,'stopper','CB','right'],
 ['Diego Rojas','DEF',88,87,84,5,8,'stopper','CB','left'],
 ['Can Aydın','DEF',84,96,80,3,6,'fullback','LB','left'],
 ['João Mendes','MID',91,91,91,6,4,'ballWinner','DM','right'],
 ['Umut Kara','MID',86,88,85,10,5,'playmaker','AM','left'],
 ['Arda Akın','MID',88,94,90,8,3,'playmaker','CM','both'],
 ['Lucas Costa','ATT',89,89,87,11,2,'winger','LW','left'],
 ['Emir Demir','ATT',96,93,97,9,0,'poacher','ST','right'],
 ['Efe Yılmaz','ATT',92,88,92,7,1,'winger','RW','right'],
 ['Ozan Arslan','GK',78,95,85,12,10,'goalkeeper','GK','left'],
 ['Martin Moreno','DEF',82,95,81,14,8,'stopper','CB','right'],
 ['Eray Emre','DEF',79,90,82,15,6,'fullback','LB','left'],
 ['Rafael Santos','MID',81,89,84,16,5,'ballWinner','DM','right'],
 ['Deniz Çetin','MID',80,94,80,17,3,'playmaker','CM','right'],
 ['Ade Okafor','ATT',83,87,87,18,2,'targetForward','ST','right'],
 ['Barış Aslan','ATT',77,95,82,19,1,'winger','RW','left']
];
const createRoster=()=>seed.map((r,i)=>({id:i,name:r[0],pos:r[1],rating:r[2],fitness:r[3],form:r[4],number:r[5],face:r[6],archetype:r[7],subposition:r[8],positions:[r[8]],preferredFoot:r[9],...Model.profiles[r[7]],weakFoot:r[9]==='both'?99:Model.profiles[r[7]].weakFoot,xp:0,dataKind:'demo'}));
const FORM={
 '4-3-3':[['ATT',22,15],['ATT',50,13],['ATT',78,15],['MID',25,40],['MID',50,43],['MID',75,40],['DEF',16,70],['DEF',39,71],['DEF',61,71],['DEF',84,70],['GK',50,89]],
 '4-2-3-1':[['ATT',50,12],['MID',19,32],['MID',50,31],['MID',81,32],['MID',36,50],['MID',64,50],['DEF',16,72],['DEF',39,73],['DEF',61,73],['DEF',84,72],['GK',50,90]],
 '4-4-2':[['ATT',37,17],['ATT',63,17],['MID',15,40],['MID',38,45],['MID',62,45],['MID',85,40],['DEF',16,72],['DEF',39,73],['DEF',61,73],['DEF',84,72],['GK',50,90]],
 '3-5-2':[['ATT',38,16],['ATT',62,16],['MID',15,36],['MID',32,48],['MID',50,39],['MID',68,48],['MID',85,36],['DEF',27,72],['DEF',50,76],['DEF',73,72],['GK',50,90]],
 '5-3-2':[['ATT',38,16],['ATT',62,16],['MID',25,42],['MID',50,46],['MID',75,42],['DEF',12,70],['DEF',30,73],['DEF',50,75],['DEF',70,73],['DEF',88,70],['GK',50,90]],
 '4-5-1':[['ATT',50,14],['MID',15,37],['MID',31,46],['MID',50,38],['MID',69,46],['MID',85,37],['DEF',16,73],['DEF',39,74],['DEF',61,74],['DEF',84,73],['GK',50,90]]
};

const fit=(p,slot)=>Model.fit(p,slot);
const reorder=(ids,formation,players)=>{const pool=ids.slice(),answer=[];for(const slot of FORM[formation]){pool.sort((a,b)=>(fit(players[b],slot[0])*150+players[b].rating*.11)-(fit(players[a],slot[0])*150+players[a].rating*.11));answer.push(pool.shift());}return answer;};
function loadRoster(saved){
 const rows=Array.isArray(saved?.players)&&saved.players.length>=11?saved.players:createRoster();
 // Never fill an imported player's missing identity from the seed player at the same index.
 return rows.map((p,i)=>({...p,id:i,fitness:Model.normalize(p).fitness,form:Model.normalize(p).form,xp:p.xp??0,face:p.face??0,number:p.number??i+1}));
}
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
