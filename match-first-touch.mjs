// Presentation pose for a ground reception. All positions are metres in
// world space. The match stays the source of the player's yaw and contact.
const ankleHeight=.13;
const bootLength=.215;
const ballClearance=.127;
const maxShift=.08;
const maxCrouch=.22;
const maxToeTurn=1.36;
const torsoKeys=['pelvis','torsoBase','torsoMid','torsoUpper','neck','head','headTop'];
const clamp=(n,min,max)=>Math.min(max,Math.max(min,n));
const wrap=angle=>Math.atan2(Math.sin(angle),Math.cos(angle));
const add=(a,b)=>a.map((v,i)=>v+b[i]);
const subtract=(a,b)=>a.map((v,i)=>v-b[i]);
const scale=(a,n)=>a.map(v=>v*n);
const mix=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
const dot=(a,b)=>a.reduce((r,v,i)=>r+v*b[i],0);
const unit=a=>scale(a,1/(Math.hypot(...a)||1));
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];

export function firstTouchPose(Rig,pose,{foot,ball,weight,support}={}){
 if((foot!==0&&foot!==1)||!ball||![ball.x,ball.y,ball.z,weight].every(Number.isFinite)||
  ball.y>.12||weight<=0||!pose?.legs)return pose;
 const amount=clamp(weight,0,1),leg=pose.legs[foot],other=pose.legs[1-foot];
 const bearing=[ball.x-leg.hip[0],0,ball.z-leg.hip[2]],radial=unit(bearing);
 const outward=foot?1:-1;
 const toeHeading=pose.face+clamp(wrap(Math.atan2(bearing[2],bearing[0])-pose.face+outward*.14),-maxToeTurn,maxToeTurn);
 const ankleAtContact=[ball.x-bootLength*Math.cos(toeHeading)-ballClearance*radial[0],ankleHeight,
  ball.z-bootLength*Math.sin(toeHeading)-ballClearance*radial[2]];

 // Bend the support knee and move the upper body a little toward the ball.
 // This makes room for the lateral step without stretching the reaching leg.
 const lateral=clamp((Math.hypot(...bearing)-.32)*.20,0,maxShift);
 const horizontal=scale(radial,lateral),offsetHip=add(leg.hip,horizontal);
 const {thigh,shin}=Rig.ANATOMY,{hip,knee}=Rig.LIMITS;
 const reach=Math.sqrt(thigh*thigh+shin*shin+2*thigh*shin*Math.cos(knee.min));
 const horizontalReach=Math.hypot(offsetHip[0]-ankleAtContact[0],offsetHip[2]-ankleAtContact[2]);
 const verticalReach=Math.sqrt(Math.max(0,reach*reach-horizontalReach*horizontalReach));
 const drop=clamp(offsetHip[1]-ankleHeight-verticalReach+.026,0,maxCrouch);
 const shift=scale(add(horizontal,[0,-drop,0]),amount);
 const forward=[Math.cos(pose.face),0,Math.sin(pose.face)];
 const up=unit(subtract(pose.torsoBase,pose.pelvis));
 const front=unit(subtract(forward,scale(up,dot(forward,up)))),right=cross(front,up);

 function solve(base,index,ankle,toe,stance){
  const start=add(base.hip,shift);
  const ik=Rig.solveLimb(start,ankle,thigh,shin,forward,knee.max,knee.min);
  const upper=subtract(ik.joint,start),along=dot(upper,front),down=-dot(upper,up);
  const flex=Math.atan2(along,down),abduct=Math.atan2(dot(upper,right)*(index?1:-1),Math.hypot(along,down));
  if((stance&&ik.error>1e-5)||ik.end[1]<Math.min(base.ankle[1],ankleHeight)-.015||
   flex<hip.flexMin||flex>hip.flexMax||abduct<hip.abductMin||abduct>hip.abductMax)return null;
  return {...base,hip:start,knee:ik.joint,ankle:ik.end,toe:add(ik.end,toe),stance,flex,abduct,
   bend:ik.bend,target:ankle,targetError:ik.error,footLift:ik.end[1]-ankleHeight};
 }

 const currentYaw=Math.atan2(leg.toe[2]-leg.ankle[2],leg.toe[0]-leg.ankle[0]);
 const yaw=currentYaw+wrap(toeHeading-currentYaw)*amount;
 const receiving=solve(leg,foot,mix(leg.ankle,ankleAtContact,amount),[.2*Math.cos(yaw),-.075,.2*Math.sin(yaw)],false);
 const anchored=support&&solve(other,1-foot,support.ankle,subtract(support.toe,support.ankle),true);
 const planting=anchored??solve(other,1-foot,other.ankle,subtract(other.toe,other.ankle),other.stance);
 if(!receiving||!planting)return pose;
 const result={...pose,legs:foot?[planting,receiving]:[receiving,planting]};
 for(const key of torsoKeys)result[key]=add(pose[key],shift);
 result.arms=pose.arms.map(arm=>Object.fromEntries(Object.entries(arm).map(([key,value])=>[
  key,Array.isArray(value)&&value.length===3?add(value,shift):value
 ])));
 return result;
}
