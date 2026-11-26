'use strict';
// Rendering only: no simulation or replay time ownership.
(function(root){
 function fitPixels(width,height,budget){
  if(![width,height,budget].every(Number.isFinite)||width<2||height<2||budget<4)throw Error('Invalid pixel budget');
  const factor=Math.min(1,Math.sqrt(budget/(width*height)));
  return [Math.max(2,Math.floor(width*factor)),Math.max(2,Math.floor(height*factor))];
 }
 function pixelBudget(mode,mobile){
  const budgets=mobile?{performance:450000,balanced:800000,quality:1300000}:{performance:1000000,balanced:1800000,quality:3000000};
  if(!(mode in budgets))throw Error('Invalid quality mode');
  return budgets[mode];
 }
 function create(){
  let dirty=true,until=0,skipped=0,draws=0,ring=[],index=0;
  function invalidate(now=0,settle=0){dirty=true;until=Math.max(until,now+Math.max(0,settle));}
  function shouldDraw(now,active,hidden){
   if(hidden){skipped++;return false;}
   if(active||dirty||now<until)return true;
   skipped++;return false;
  }
  function drawn(){dirty=false;draws++;}
  function record(ms){if(!Number.isFinite(ms)||ms<0)return;if(ring.length<120)ring.push(ms);else{ring[index]=ms;index=(index+1)%120;}}
  function stats(){
   const sorted=[...ring].sort((a,b)=>a-b);
   return {draws,skipped,samples:ring.length,meanMs:ring.length?ring.reduce((a,b)=>a+b,0)/ring.length:0,p95Ms:sorted.length?sorted[Math.ceil(.95*sorted.length)-1]:0};
  }
  return {invalidate,shouldDraw,drawn,record,stats};
 }
 const api={fitPixels,pixelBudget,create};root.TribunReplayPerformance=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
