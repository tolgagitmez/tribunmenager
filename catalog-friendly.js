'use strict';
(function(root){
const Model=typeof module!=='undefined'&&module.exports?require('./player-model.js'):root.TribunPlayerModel;
const Roster=typeof module!=='undefined'&&module.exports?require('./api-football-roster.js'):root.TribunApiRoster;
const Tactics=typeof module!=='undefined'&&module.exports?require('./tactics.js'):root.TribunTactics;
const STORE='tribun-catalog-friendly-v1';
const roles=['GK','DEF','MID','ATT'];
function name(s){return typeof s==='string'&&s.trim()&&s.length<=150&&!/[\x00-\x1f]/.test(s)}
function load(snapshot,mode='neutral'){
 if(!name(snapshot?.name)||!Array.isArray(snapshot.players)||snapshot.players.length>150||
    snapshot.players.some(p=>!name(p?.name)))throw Error('Kadro dosyası geçersiz.');
 const players=Roster.toGameRoster(snapshot,{ratingMode:mode});
 return {teamUid:snapshot.teamUid,name:snapshot.name,fetchedAt:snapshot.fetchedAt,players};
}
function selectXI(players,formation){
 const slots=Model.slots[formation];if(!slots)throw Error('Geçersiz diziliş.');
 const used=new Set();
 return slots.map(position=>{
  const role=Model.groups.GK.includes(position)?'GK':roles.find(k=>Model.groups[k].includes(position));
  const pool=players.filter(p=>p.pos===role&&!used.has(p.id)).sort((a,b)=>Model.quality(b,position)-Model.quality(a,position)||a.id-b.id);
  if(!pool.length)throw Error('Bu diziliş için yeterli '+role+' oyuncusu yok.');
  used.add(pool[0].id);return pool[0].id;
 });
}
function validateSide(side,formation,ids){
 if(!side||!name(side.name)||!/^api-football:team:[1-9][0-9]*$/.test(side.teamUid)||!Array.isArray(side.players)||side.players.length<11||side.players.length>150||
 !Number.isFinite(Date.parse(side.fetchedAt)))throw Error('Geçersiz takım.');
 const seen=new Set();
 for(let i=0;i<side.players.length;i++){
  const p=side.players[i];
  if(p?.id!==i||!name(p.name)||!Number.isSafeInteger(p.providerId)||p.providerId<1||p.uid!=='api-football:player:'+p.providerId||seen.has(p.uid)||p.teamUid!==side.teamUid||
  !roles.includes(p.pos)||p.preferredFoot!=='unknown'||p.subposition!==null||p.ratingProvenance?.observed!==false||
  !Number.isInteger(p.rating)||p.rating<1||p.rating>99||!Model.attributes.every(k=>Number.isFinite(p[k])&&p[k]>=1&&p[k]<=99))throw Error('Geçersiz futbolcu profili.');
  seen.add(p.uid);
 }
 const slots=Model.slots[formation];if(!slots||!Array.isArray(ids)||ids.length!==11||new Set(ids).size!==11)throw Error('İlk 11 geçersiz.');
 for(let i=0;i<11;i++){const p=side.players[ids[i]];if(!Number.isInteger(ids[i])||!p||!Model.groups[p.pos].includes(slots[i]))throw Error('İlk 11 mevki uyumsuz.');}
}
function build(home,away,options={}){
 const formation=options.formation||'4-3-3',awayFormation=options.awayFormation||'4-3-3';
 const starters=options.starters||selectXI(home.players,formation),awayStarters=options.awayStarters||selectXI(away.players,awayFormation);
 validateSide(home,formation,starters);validateSide(away,awayFormation,awayStarters);
 const uids=new Set(home.players.map(p=>p.uid));
 if(home.teamUid===away.teamUid||away.players.some(p=>uids.has(p.uid)))throw Error('Aynı takım veya çakışan futbolcu kimliği. Kadroları güncelle.');
 const clone=v=>JSON.parse(JSON.stringify(v));
 return {catalogFriendly:true,version:1,homeName:home.name,awayName:away.name,homeTeamUid:home.teamUid,awayTeamUid:away.teamUid,
 homeFetchedAt:home.fetchedAt,awayFetchedAt:away.fetchedAt,players:clone(home.players),awayPlayers:clone(away.players),
 starters:[...starters],awayStarters:[...awayStarters],formation,awayFormation,tactics:Tactics.normalize(options.tactics),awayTactics:Tactics.normalize(options.awayTactics),
 matchMinutes:5,individualAI:true,opponentSource:'catalog-friendly',
 rosterNotice:'Yerel katalog hazırlık maçı · yetenekler sentetik · lig ve transfer kayıtları etkilenmez.'};
}
function validate(cfg){
 if(cfg?.catalogFriendly!==true||cfg.version!==1)throw Error('Katalog maç kaydı geçersiz.');
 return build({teamUid:cfg.homeTeamUid,name:cfg.homeName,fetchedAt:cfg.homeFetchedAt,players:cfg.players},
 {teamUid:cfg.awayTeamUid,name:cfg.awayName,fetchedAt:cfg.awayFetchedAt,players:cfg.awayPlayers},cfg);
}
function launch(cfg,env=root){
 const clean=validate(cfg);
 env.sessionStorage.setItem(STORE,JSON.stringify(clean)); // no URL payload or localStorage
 env.location.href='match.html?catalog=1';
}
function consume(env=root){
 const raw=env.sessionStorage.getItem(STORE);
 env.sessionStorage.removeItem(STORE); // single-use; restart uses in-memory game
 if(!raw)throw Error('Kadro seçimi bulunamadı. Hazırlık merkezine dön.');
 return validate(JSON.parse(raw));
}
const api={load,selectXI,build,validate,launch,consume,STORE};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.TribunCatalogFriendly=api;
})(typeof window!=='undefined'?window:globalThis);
