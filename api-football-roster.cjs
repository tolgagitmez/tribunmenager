'use strict';
// Identity is factual; gameplay ratings are explicitly inferred, not provider statistics.
// Stable provider UIDs survive refreshes; dense IDs are per-roster simulation indices.
const Model=require('./player-model.js');
const Ratings=require('./api-football-ratings.cjs');
function toGameRoster(snapshot,{ratingMode='neutral'}={}){
 if(snapshot?.schema!==1||snapshot.source!=='api-football'||!Number.isSafeInteger(snapshot.teamId)||snapshot.teamId<1||
    snapshot.teamUid!=='api-football:team:'+snapshot.teamId||!Array.isArray(snapshot.players)||typeof snapshot.fetchedAt!=='string'||!Number.isFinite(Date.parse(snapshot.fetchedAt)))throw Error('Invalid catalog snapshot');
 const seen=new Set(),players=[];
 for(const p of snapshot.players){
  if(!p||!Number.isSafeInteger(p.providerId)||p.providerId<1||p.uid!=='api-football:player:'+p.providerId||seen.has(p.uid)||typeof p.name!=='string'||!p.name.trim())throw Error('Invalid or duplicate player identity');
  seen.add(p.uid);
  if(!['GK','DEF','MID','ATT'].includes(p.pos))continue; // unknown position remains in catalog, never invented
  players.push(p);
 }
 if(players.length<11||!players.some(p=>p.pos==='GK'))throw Error('Incomplete playable squad');
 if(!['neutral','synthetic-varied'].includes(ratingMode))throw Error('Unknown rating mode');
 return players.sort((a,b)=>a.providerId-b.providerId).map((p,id)=>{
  const profile=Ratings.buildProfile(p.uid,p.pos,ratingMode);
  return ({
   ...Model.normalize({id,uid:p.uid,providerId:p.providerId,name:p.name,pos:p.pos,
    number:Number.isInteger(p.number)&&p.number>=1&&p.number<=99?p.number:id+1,
    age:Number.isInteger(p.age)?p.age:null,preferredFoot:'unknown',rating:profile.rating,fitness:95,form:80,...profile.skills,
    dataKind:'provider-identity-synthetic-skills',teamUid:snapshot.teamUid,source:'api-football',
    ratingSource:profile.ratingSource,skillSource:profile.skillSource,ratingProvenance:profile.ratingProvenance,fitnessSource:'game-initialization',formSource:'game-initialization',
    numberSource:Number.isInteger(p.number)&&p.number>=1&&p.number<=99?'provided':'game-assigned',
    fetchedAt:snapshot.fetchedAt,face:0,xp:0}),
   // no precise position, dominant foot, measured speed or observed ability asserted
   subposition:null,positions:[],
   // Independent explicit provenance survives normalize(), which treats
   // supplied numerical attributes as provided values in its legacy contract.
   ratingProvenance:profile.ratingProvenance
  });
 });
}
module.exports={toGameRoster};
