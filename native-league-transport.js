'use strict';
(function(root){
 function route(name,round){
  if(!Number.isInteger(round)||round<0||round>9)throw Error('Geçersiz maç günü.');
  if(name==='tactics.json')return '/api/league/native-av/tactics?round='+round;
  if(!/^(status\.json|live\.m3u8|init\.mp4|segment-[0-9]{5}\.m4s)$/.test(name))throw Error('Geçersiz yayın dosyası.');
  return '/api/league/native-av/media?round='+round+'&file='+encodeURIComponent(name);
 }
 if(typeof module!=='undefined'&&module.exports){module.exports={route};return;}
 const value=new URLSearchParams(location.search).get('round'),round=/^[0-9]$/.test(value||'')?Number(value):null;
 root.TRIBUN_LEAGUE_AV={round,async request(name,options={}){
  let token;try{token=localStorage.getItem('tribun-league-token');}catch{}
  if(!token)throw Error('Lig oturumu gerekli.');
  return fetch(route(name,round),{...options,cache:'no-store',headers:{...options.headers,Authorization:'Bearer '+token},credentials:'same-origin',redirect:'error'});
 }};
})(typeof window!=='undefined'?window:globalThis);
