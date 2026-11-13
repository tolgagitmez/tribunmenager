'use strict';
/* Field dimensions are inside measurements. Goal frame radii are model values. */
(function(root){
const dimensions=Object.freeze({halfLength:52,halfWidth:34,goalHalfWidth:3.66,goalHeight:2.44,postRadius:.06,ballRadius:.11});
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const point=(a,b,t)=>({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t,z:a.z+(b.z-a.z)*t});
function firstWholeBallExit(previous,next,radius=dimensions.ballRadius){
 const candidates=[];
 for(const [axis,half,kind] of [['x',dimensions.halfLength,'goal-line'],['z',dimensions.halfWidth,'touchline']])for(const sign of [-1,1]){
  const limit=half+radius,a=previous[axis]*sign,b=next[axis]*sign;
  // A ball still overlapping the painted plane remains in play. Equality is
  // the instant of tangency; a crossing requires travel beyond that instant.
  if(b<=limit+1e-9)continue;
  if(b<=a&&a<=limit)continue;
  const t=a>=limit?0:clamp((limit-a)/(b-a),0,1);
  candidates.push({kind,axis,sign,t,point:point(previous,next,t)});
 }
 candidates.sort((a,b)=>a.t-b.t||(a.kind==='goal-line'?-1:1));
 return candidates[0]||null;
}
function goalMouth(p,radius=dimensions.ballRadius){return Math.abs(p.z)+radius<dimensions.goalHalfWidth-1e-9&&p.y-radius>=-1e-7&&p.y+radius<dimensions.goalHeight-1e-9;}
function roots(a,b,c){if(a<1e-18)return [];const d=b*b-4*a*c;if(d<0)return [];const s=Math.sqrt(Math.max(0,d));return [(-b-s)/(2*a),(-b+s)/(2*a)];}
function frameParts(){
 const {halfLength:x,goalHalfWidth:w,goalHeight:h,postRadius:r}=dimensions,parts=[];
 for(const side of [-1,1]){
  for(const flank of [-1,1])parts.push({name:'post',side,axis:'y',fixed:{x:x*side,z:(w+r)*flank},low:0,high:h+r});
  parts.push({name:'crossbar',side,axis:'z',fixed:{x:x*side,y:h+r},low:-w-r,high:w+r});
 }
 return parts;
}
const parts=frameParts();
function sweepPart(a,b,part,radius){
 const axes=['x','y','z'],radial=axes.filter(k=>k!==part.axis),delta=Object.fromEntries(axes.map(k=>[k,b[k]-a[k]])),R=radius+dimensions.postRadius;
 const hits=[];
 const radialA=radial.map(k=>a[k]-part.fixed[k]),radialD=radial.map(k=>delta[k]);
 const qa=radialD.reduce((s,n)=>s+n*n,0),qb=2*radialA.reduce((s,n,i)=>s+n*radialD[i],0),qc=radialA.reduce((s,n)=>s+n*n,0)-R*R;
 function add(t,center){
  if(t< -1e-9||t>1+1e-9)return;
  t=clamp(t,0,1);const p=point(a,b,t),n={x:p.x-center.x,y:p.y-center.y,z:p.z-center.z},d=Math.hypot(n.x,n.y,n.z);if(d<1e-12)return;
  for(const k of axes)n[k]/=d;
  if(delta.x*n.x+delta.y*n.y+delta.z*n.z>=-1e-10)return;
  hits.push({t,point:p,normal:n,name:part.name,side:part.side});
 }
 if(qc<0&&a[part.axis]>=part.low&&a[part.axis]<=part.high){const center={...part.fixed,[part.axis]:a[part.axis]};add(0,center);}
 for(const t of roots(qa,qb,qc)){
  const along=a[part.axis]+delta[part.axis]*t;if(along<part.low||along>part.high)continue;
  add(t,{...part.fixed,[part.axis]:along});
 }
 // Rounded end caps close the joints and keep very fast diagonal trajectories
 // from tunnelling through the post/crossbar meeting point.
 for(const end of [part.low,part.high]){
  const center={...part.fixed,[part.axis]:end},offset=axes.map(k=>a[k]-center[k]);
  const aa=axes.reduce((s,k)=>s+delta[k]*delta[k],0),bb=2*axes.reduce((s,k,i)=>s+offset[i]*delta[k],0),cc=offset.reduce((s,n)=>s+n*n,0)-R*R;
  for(const t of roots(aa,bb,cc))add(t,center);
 }
 hits.sort((a,b)=>a.t-b.t);return hits[0]||null;
}
function sweepFrame(previous,next,radius=dimensions.ballRadius){
 const hits=parts.map(part=>sweepPart(previous,next,part,radius)).filter(Boolean);hits.sort((a,b)=>a.t-b.t);return hits[0]||null;
}
function reflected(velocity,normal,restitution=.72){
 const along=velocity.x*normal.x+velocity.y*normal.y+velocity.z*normal.z;
 if(along>=0)return {...velocity};
 return {x:velocity.x-(1+restitution)*along*normal.x,y:velocity.y-(1+restitution)*along*normal.y,z:velocity.z-(1+restitution)*along*normal.z};
}
const api={dimensions,firstWholeBallExit,goalMouth,sweepFrame,reflected};root.TribunPitchLaws=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
