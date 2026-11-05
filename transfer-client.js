'use strict';
// A local cache is for roster presentation only. The server owns every balance,
// offer, price, deadline, sale and ledger entry; no client credit method exists.
(function(root){
const KEY='tribun-manager-pro09',SESSION='tribun-transfer-session-v1';
let token='',profileId='',pending=0;
try{const s=JSON.parse(localStorage.getItem(SESSION)||'null');token=s?.token||'';profileId=s?.profileId||'';}catch{}
function cached(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')||{};}catch{return {};}}
function current(input){const stored=cached();return Number(stored.transferRevision||0)>Number(input?.transferRevision||0)?{...input,...stored}:input||stored;}
function apply(view){
 const old=cached(),same=old.transferProfileId===view.profileId;
 if(same&&Number(old.transferRevision||0)>view.revision)return old;
 const players=view.players.map((p,i)=>({...p,id:i}));
 let starters=Array.isArray(old.starters)?old.starters: view.starters;
 starters=root.TribunClubData.repairStarters(starters,players,old.formation||'4-3-3');
 const special={...old.special};for(const k of ['captain','penalty','free','corner'])if(!starters.includes(special[k]))special[k]=starters.find(id=>players[id].pos!=='GK')??starters[0];
 const data={...old,players,starters,special,trainingDate:view.trainingDate,trainingUsed:view.trainingUsed,transferProfileId:view.profileId,transferRevision:view.revision};
 try{localStorage.setItem(KEY,JSON.stringify(data));}catch{throw Error('Kadro kaydedilemedi. Tarayıcı depolama iznini kontrol et.');}
 root.dispatchEvent(new CustomEvent('tribun:roster',{detail:data}));return data;
}
async function request(path,body){
 if(!/^https?:$/.test(location.protocol))throw Error('Transfer merkezi için oyunu BASLAT.bat veya BASLAT.sh ile aç.');
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);pending++;
 try{
  const response=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},...(body?{body:JSON.stringify(body)}:{}),cache:'no-store',signal:controller.signal});
  let data;try{data=await response.json();}catch{throw Error('Transfer sunucusundan geçerli yanıt alınamadı.');}
  if(!response.ok)throw Error(data.error||'Transfer işlemi tamamlanamadı.');return data;
 }catch(e){if(e.name==='AbortError')throw Error('Transfer bağlantısı zaman aşımına uğradı. Aynı işlemi güvenle yeniden deneyebilirsin.');throw e;}
 finally{clearTimeout(timer);pending--;}
}
function requestId(){return root.crypto?.randomUUID?.()||Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);}
async function connect(){
 if(!token){
  const data=await request('/api/transfers/profile',{legacy:cached()});token=data.token;profileId=data.profileId;
  try{localStorage.setItem(SESSION,JSON.stringify({token,profileId}));}catch{token='';throw Error('Transfer oturumu kaydedilemedi. Tarayıcı depolamasını etkinleştir.');}
  apply(data);return data;
 }
 return sync();
}
async function sync(){if(!token)return null;const data=await request('/api/transfers/state');apply(data);return data;}
async function command(action,payload={},id=requestId()){if(!token)throw Error('Önce transfer merkezine bağlan.');const data=await request('/api/transfers/command',{requestId:id,action,payload});apply(data);return data;}
async function linkLeague(leagueToken){if(!token)return;const data=await sync(),starters=cached().starters;if(JSON.stringify(starters)!==JSON.stringify(data.starters))await command('lineup',{starters});return command('link-league',{leagueToken});}
root.TribunTransfers={cached,current,apply,connect,sync,command,linkLeague,requestId,hasSession:()=>!!token,busy:()=>pending>0};
root.addEventListener('storage',e=>{if(e.key===KEY)root.dispatchEvent(new CustomEvent('tribun:roster',{detail:cached()}));});
})(window);
