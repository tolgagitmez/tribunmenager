'use strict';
// A precomputed native recording is played on one 300-second schedule.
// Match generation remains native; this module never fabricates frames or scores.
(function(root){
 const DURATION_MS=300000, clamp=(n,a,b)=>Math.min(b,Math.max(a,n));
 function requireFinite(n){if(!Number.isFinite(n))throw Error('Invalid broadcast time');}
 function create(frames){
  if(!Array.isArray(frames)||frames.length<2||frames.at(-1).done!==true||frames.at(-1).matchMs<5400000)throw Error('300 saniyelik yayın için tamamlanmış 90 dakikalık maç kaydı gerekir.');
  const start=frames[0].elapsedMs,end=frames.at(-1).elapsedMs;
  if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||end<=start||frames.some((f,i)=>!Number.isSafeInteger(f.elapsedMs)||i&&f.elapsedMs<frames[i-1].elapsedMs||i<frames.length-1&&f.done))throw Error('Geçersiz yayın kaydı.');
  function at(elapsed){
   requireFinite(elapsed);
   const broadcastMs=clamp(elapsed,0,DURATION_MS);
   const nativeMs=broadcastMs===DURATION_MS?end:start+Math.min(end-start-1,Math.floor((end-start)*broadcastMs/DURATION_MS));
   let lo=0,hi=frames.length;
   while(lo<hi){const mid=(lo+hi)>>1;if(frames[mid].elapsedMs<=nativeMs)lo=mid+1;else hi=mid;}
   // Final frame (including same-timestamp full-time records) is not revealed early.
   const index=broadcastMs===DURATION_MS?frames.length-1:Math.min(frames.length-2,Math.max(0,lo-1));
   return {broadcastMs,nativeMs,nativeOffsetMs:nativeMs-start,index,remainingMs:DURATION_MS-broadcastMs,phase:elapsed<0?'scheduled':elapsed>=DURATION_MS?'finished':'playing'};
  }
  return {at,durationMs:DURATION_MS};
 }
 const api={create,DURATION_MS};root.TribunNativeBroadcast=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
