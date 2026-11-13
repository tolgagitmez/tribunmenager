'use strict';
// One launch boundary for squad, tactics and direct match-page entry points.
(function(root){
const C=root.TribunClubData;
const clone=value=>JSON.parse(JSON.stringify(value));
const CONTEXT='tribun-match-launch-context-v1';
let memoryContext=null,contextSequence=0;
function leagueToken(){try{return root.localStorage.getItem('tribun-league-token')||'';}catch{return '';}}
function identityContext(){
 const transfers=root.TribunTransfers,hasSession=!!transfers?.hasSession();
 return {leagueToken:leagueToken(),hasSession,profileId:hasSession?(transfers.sessionProfileId?.()||transfers.cached?.().transferProfileId||null):null};
}
function readContext(){try{return JSON.parse(root.sessionStorage.getItem(CONTEXT)||'null')||memoryContext;}catch{return memoryContext;}}
function bindContext(){
 const context={...identityContext(),id:root.crypto?.randomUUID?.()||Date.now().toString(36)+'-'+(++contextSequence)};
 memoryContext=context;
 // The credential stays in private tab storage. Only the opaque ID is included
 // in the match snapshot or its URL fallback.
 try{root.sessionStorage.setItem(CONTEXT,JSON.stringify(context));}catch{}
 return context.id;
}
function demo(cfg,reason,opponent){
 const players=C.createRoster().map(p=>({...p,name:'Deneme '+p.name,dataKind:'demo'}));
 cfg.awayPlayers=players;cfg.awayFormation=opponent?.formation||cfg.awayFormation||'4-2-3-1';
 cfg.awayStarters=C.reorder(C.starters,cfg.awayFormation,players);
 cfg.awayTactics=opponent?.tactics||cfg.awayTactics;
 cfg.awayName=opponent?.name||'Deneme Rakibi';cfg.opponentSource='demo';
 cfg.rosterNotice=reason==='missing-roster'?'Rakibin kayıtlı kadrosu bulunmuyor; deneme kadrosu kullanılıyor.':reason==='league-unavailable'?'Lig kadrosuna ulaşılamadı; deneme rakibiyle yerel maç.':'Deneme rakibiyle yerel maç.';
 return cfg;
}
async function fixtureSnapshot(token){
 const controller=new root.AbortController(),timer=root.setTimeout(()=>controller.abort(),12000);
 try{
  const response=await root.fetch('/api/league/local-match',{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:controller.signal});
  if(!response.ok)throw Error('Fikstür kadrosu alınamadı.');
  const value=await response.json();
  if(value?.version!==1||!value.fixture||!value.opponent||!value.ownTeam)throw Error('Fikstür kadrosu geçersiz.');
  return value;
 }finally{root.clearTimeout(timer);}
}
function prepared(cfg){
 if(cfg?.matchSetup?.version!==1||!Array.isArray(cfg.players)||!Array.isArray(cfg.awayPlayers)||cfg.awayPlayers.length<11)return false;
 const saved=readContext(),current=identityContext();
 return !!saved&&saved.id===cfg.matchSetup.contextId&&saved.leagueToken===current.leagueToken&&saved.hasSession===current.hasSession&&saved.profileId===current.profileId;
}
async function prepare(input={}){
 const cfg=clone(input),transfers=root.TribunTransfers;
 if(prepared(cfg))return cfg;
 if(cfg.matchSetup?.version===1){
  // A new account/league page entry is a new launch. An existing game's restart
  // continues using its already captured snapshot inside the presentation.
  const current=transfers?.cached?.()||{};
  if(Array.isArray(current.players)){cfg.players=clone(current.players);cfg.starters=clone(current.starters||C.starters);cfg.transferProfileId=current.transferProfileId;cfg.transferRevision=current.transferRevision;cfg.special=current.special;}
  if(cfg.opponentSource!=='provided-roster')for(const key of ['awayPlayers','awayStarters','awayFormation','awayTactics','awayName','opponentSource','opponentRevision','rosterNotice'])delete cfg[key];
  if(cfg.fixture)delete cfg.homeName;
  delete cfg.fixture;delete cfg.matchSetup;
 }
 cfg.formation=C.formations[cfg.formation]?cfg.formation:'4-3-3';
 if(transfers?.hasSession()){
  const view=await transfers.sync(),current=transfers.cached();
  if(!view?.players)throw Error('Güncel kadro alınamadı.');
  const newerCache=current.transferProfileId===view.profileId&&Number(current.transferRevision)>Number(view.revision)&&Array.isArray(current.players);
  const revision=newerCache?current.transferRevision:view.revision;
  const same=cfg.transferProfileId===view.profileId&&Number(cfg.transferRevision)===Number(revision);
  cfg.players=C.loadRoster({players:newerCache?current.players:view.players});
  cfg.starters=C.repairStarters(same?cfg.starters:current.starters,cfg.players,cfg.formation);
  cfg.special=same?(cfg.special||current.special):(current.special||cfg.special);
  cfg.transferProfileId=view.profileId;cfg.transferRevision=revision;
 }else{
  cfg.players=C.loadRoster(cfg);cfg.starters=C.repairStarters(cfg.starters||C.starters,cfg.players,cfg.formation);
 }
 const token=leagueToken();
 if(token){
  let snapshot;
  try{snapshot=await fixtureSnapshot(token);}catch{demo(cfg,'league-unavailable');}
  if(snapshot){
   if(snapshot.competitionRules)cfg.rules={...cfg.rules,...clone(snapshot.competitionRules)};
   cfg.fixture=clone(snapshot.fixture);cfg.fixture.snapshotAt=snapshot.snapshotAt;
   cfg.homeName=snapshot.ownTeam.name;
   const opponent=snapshot.opponent;
   if(opponent.source==='linked-roster'&&Array.isArray(opponent.players)&&opponent.players.length>=11&&Array.isArray(opponent.starters)&&opponent.starters.length===11){
    cfg.awayPlayers=clone(opponent.players);cfg.awayStarters=opponent.starters.slice();
    cfg.awayFormation=C.formations[opponent.formation]?opponent.formation:'4-3-3';
    cfg.awayTactics=clone(opponent.tactics||{});cfg.awayName=opponent.name;
    cfg.opponentSource='linked-roster';cfg.opponentRevision=opponent.revision;
    cfg.rosterNotice='Fikstür rakibinin kayıtlı kadrosuyla yerel maç; günlük lig sonucu değişmez.';
   }else demo(cfg,'missing-roster',opponent);
  }
 }else if(Array.isArray(cfg.awayPlayers)&&cfg.awayPlayers.length>=11){
  cfg.opponentSource=cfg.opponentSource||'provided-roster';cfg.awayName=cfg.awayName||'Rakip';
  cfg.rosterNotice=cfg.rosterNotice||'Seçilen iki kadroyla yerel maç.';
 }else demo(cfg,'no-league');
 cfg.homeName=cfg.homeName||'Moreirense SK';
 cfg.matchSetup={version:1,ownRevision:cfg.transferRevision??null,opponentSource:cfg.opponentSource,contextId:bindContext()};
 return cfg;
}
function launch(cfg){
 let stored=false;
 try{root.sessionStorage.setItem('tribun-match-config',JSON.stringify(cfg));stored=true;}catch{}
 root.location.href=stored?'match.html':'match.html#'+encodeURIComponent(JSON.stringify(cfg));
}
root.TribunMatchConfig={prepare,prepared,launch};
})(typeof window!=='undefined'?window:globalThis);
