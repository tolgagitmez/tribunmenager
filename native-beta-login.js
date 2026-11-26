'use strict';
document.querySelector('#login').addEventListener('submit',async e=>{
 e.preventDefault();const status=document.querySelector('#status'),input=document.querySelector('#token'),token=input.value.trim();
 if(!['127.0.0.1','localhost'].includes(location.hostname)){status.textContent='Yalnızca yerel sunucu destekleniyor.';return;}
 try{
  const res=await fetch('/api/league/status',{headers:{Authorization:'Bearer '+token},cache:'no-store',redirect:'error'});
  if(!res.ok)throw Error();
  const state=await res.json();if(state.matchBackend!=='native-only')throw Error();
  localStorage.setItem('tribun-league-token',token);input.value='';location.replace('league.html');
 }catch{status.textContent='Native lig anahtarı doğrulanamadı.';}
});
