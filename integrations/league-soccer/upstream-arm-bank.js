'use strict';
(function(root){
 function parse(doc){
  if(doc?.schema!==1||doc.source!=='upstream-raw-retarget'||!doc.clips||Object.keys(doc.clips).sort().join(',')!=='idle,run')throw Error('Geçersiz animasyon paketi');
  const result={};
  for(const name of ['idle','run']){
   const clip=doc.clips[name],samples=clip?.samples;
   if(!Number.isFinite(clip?.duration)||clip.duration<=0||clip.duration>10||!Array.isArray(samples)||samples.length<2||samples.length>601)throw Error('Geçersiz klip süresi');
   const rows=samples.map(row=>{
    if(!Array.isArray(row)||row.length!==2)throw Error('Geçersiz kol kanalı');
    return Object.freeze(row.map(v=>{
     if(!Array.isArray(v)||v.length!==3||!v.every(Number.isFinite)||Math.hypot(...v)>.606)throw Error('Anatomi sınırı dışında kol hedefi');
     return Object.freeze(v.slice());
    }));
   });
   result[name]=Object.freeze({source:doc.source,duration:clip.duration,samples:Object.freeze(rows)});
  }
  return Object.freeze(result);
 }
 const api={parse};root.TribunUpstreamArms=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
