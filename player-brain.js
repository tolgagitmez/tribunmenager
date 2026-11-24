'use strict';
/* Deterministic, local-information player tendencies. Never reads global opponents,
   changes ball physics or draws RNG: Match remains the authority for feasibility. */
(function(root){
const clamp=(x,min,max)=>Math.max(min,Math.min(max,x));
const stat=(p,key,fallback=75)=>Number.isFinite(p?.[key])?clamp(p[key],0,100):fallback;
const advance=(p,point,forward)=>Number.isFinite(point?.x)?(point.x-p.x)*forward:0;
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
function passBias(p,{kind='pass',forwardGain=0,pressure=12,risk=0,space=5,arrivalRisk=0}={}){
 const vision=stat(p,'vision'),passing=stat(p,'passing'),composure=stat(p,'composure');
 const skill=.52*vision+.48*passing,progress=clamp(forwardGain/24,0,1),exposure=clamp((5-pressure)/5,0,1);
 const dependable=clamp((skill-74)/24,-.85,1),calm=clamp((composure-70)/30,-.6,1);
 const danger=clamp(risk,0,1)*.7+clamp(arrivalRisk,0,1)*.3;
 if(kind==='through'){
  // Reward the *read*, never erase an offside, interception or arrival check.
  return clamp((dependable*4.1+calm*.8)*progress*(.55+.45*clamp(space/7,0,1))
   -Math.max(0,exposure-.45)*(1-calm)*2-Math.max(0,danger-.45)*3,-4,5);
 }
 return clamp(dependable*2.0*progress+calm*.45*progress-danger*Math.max(0,2.1-passing/55)
  -exposure*Math.max(0,74-composure)*.035,-2.5,2.8);
}
function canThread(p,{forwardGain=0,aligned=false,pressure=10}={}){
 return (p?.role==='MID'||p?.role==='ATT')&&stat(p,'vision')>=86&&stat(p,'passing')>=82
  &&stat(p,'composure')>=72&&forwardGain>3.5&&aligned&&pressure>2.4;
}
function carryBias(p,{forwardGain=0,clearance=0,turn=0,point=null}={}){
 const control=.48*stat(p,'dribbling')+.29*stat(p,'agility')+.23*stat(p,'acceleration');
 const attacking=['LW','RW','LM','RM','AM','CF','ST'].includes(p?.position)||p?.role==='ATT';
 const forward=clamp(forwardGain/5.5,0,1),space=clamp((clearance-.8)/2.8,0,1);
 const foot=p?.footPreference;
 const naturalCut=point&&Math.abs(point.z)<Math.abs(p.z)-.8
  &&(foot==='both'||foot==='right'&&p.z<0||foot==='left'&&p.z>0);
 const bias=(control-75)*.15*forward*space*(attacking?1:.65);
 return clamp(bias+(naturalCut&&attacking?.9:0)-turn*(100-stat(p,'agility'))*.008,-2.5,4.5);
}
function shouldDrive(p,carry,pass,{forward=1,pressure=10,carryTime=0,goalDistance=50}={}){
 if(!carry?.point||!Number.isFinite(carry.clearance)||p?.role==='GK')return false;
 if(p?.role==='DEF'&&!['LWB','RWB','LB','RB'].includes(p.position))return false;
 const control=.46*stat(p,'dribbling')+.30*stat(p,'agility')+.24*stat(p,'acceleration');
 const gain=advance(p,carry.point,forward),bestGain=pass?.point?advance(p,pass.point,forward):0;
 if(control<83||stat(p,'dribbling')<81||(Number.isFinite(p.energy)?p.energy:1)<.45)return false;
 if(pressure<2.4||pressure>9.5||carry.clearance<2.1||gain<2.6||goalDistance<13||carryTime>1.35)return false;
 if(pass?.kind==='through'&&pass.risk<.55)return false;
 // Do not overlook a clearly available, useful and physically safe pass.
 if(pass&&pass.risk<.35&&pass.arrivalRisk<.55&&pass.space>2.5&&bestGain>5&&pass.score>6)return false;
 return true;
}
function canFeint(p,defender,{pressure=10}={}){
 if(!defender||p?.role==='GK'||pressure<1.25||pressure>3.35)return false;
 if(stat(p,'dribbling')<82||stat(p,'agility')<78||(Number.isFinite(p.energy)?p.energy:1)<.43)return false;
 const technique=.60*stat(p,'dribbling')+.40*stat(p,'agility');
 const defensiveRead=.65*stat(defender,'tackling')+.35*stat(defender,'composure');
 return technique-defensiveRead>=-13;
}
function canHoldUp(p,defender,pass,{forward=1,pressure=10}={}){
 if(!defender||p?.role!=='ATT'||!['ST','CF'].includes(p.position)&&p.archetype!=='targetForward')return false;
 if(stat(p,'strength')<80||stat(p,'balance')<76||stat(p,'composure')<71||(Number.isFinite(p.energy)?p.energy:1)<.38)return false;
 if(pressure<1.15||pressure>3.25)return false;
 // Body points towards midfield while a real defender protects the goal side.
 if(Math.cos(p.face)*forward>-.20||(defender.x-p.x)*forward<-.7)return false;
 if(pass?.risk<.35&&pass?.arrivalRisk<.55&&pass?.space>2.5&&advance(p,pass.point,forward)>5)return false;
 return true;
}
// An onside staging point, not a permission to cross before release.
function runMargin(p,forward){
 const v=Math.max(0,(p.vx||0)*forward),brake=clamp(9+(stat(p,'agility')-75)*.04,7.5,10.5);
 return clamp(.95+v*v/(2*brake)+v*.18,.95,4.7);
}
function segmentDistance(q,a,b){
 const dx=b.x-a.x,dz=b.z-a.z,len=dx*dx+dz*dz;
 const t=len?clamp(((q.x-a.x)*dx+(q.z-a.z)*dz)/len,0,1):0;
 return Math.hypot(q.x-a.x-dx*t,q.z-a.z-dz*t);
}
function offBallOption(p,owner,{forward=1,line,opponents=[]}={}){
 if(!owner||!Number.isFinite(line)||p.id===owner.id||!['ATT','MID'].includes(p.role)||p.position==='DM'||(p.energy??1)<.43)return null;
 const read=.45*stat(p,'vision')+.30*stat(p,'composure')+.25*stat(p,'acceleration');
 if(read<80||stat(p,'pace')<80||distance(p,owner)<5||distance(p,owner)>31)return null;
 const depth=p.x*forward,legal=line-runMargin(p,forward);
 if(line-depth>12||depth>line-.4||legal-depth<1.2||owner.x*forward<-12||owner.x*forward>31)return null;
 // The runner's own observation, not an omniscient peek at a defender's plans.
 const visible=opponents.filter(d=>d.active!==false&&(d.confidence??1)>.45&&(d.age??0)<.6);
 if(!visible.length)return null;
 const marker=visible.filter(d=>d.role!=='GK'&&distance(p,d)<6.5&&d.x*forward>=depth-.8).sort((a,b)=>distance(p,a)-distance(p,b))[0];
 const x=forward*Math.min(legal,depth+6.5,owner.x*forward+23),gain=(x-p.x)*forward;
 if(gain<1.2)return null;
 let best=null;
 for(const dz of [-6,-3.5,3.5,6]){
  const point={x,z:clamp(p.z+dz,-27,27)};
  const room=Math.min(12,...visible.map(d=>distance(point,{x:d.x+(d.vx||0)*.28,z:d.z+(d.vz||0)*.28})));
  const lane=Math.min(10,...visible.map(d=>segmentDistance(d,p,point)));
  if(room<2.6||lane<1.25||Math.abs(point.z-p.z)<2.5)continue;
  const behind=marker&&Number.isFinite(marker.face)&&Math.cos(Math.atan2(point.z-marker.z,point.x-marker.x)-marker.face)<-.30;
  const kind=behind?'blind-side':'diagonal';
  const score=room*.82+gain*.18+lane*.18+(read-80)*.09+(behind?2.3:0)-Math.abs(dz)*.10;
  if(!best||score>best.score)best={kind,point,score,markerId:marker?.id??null};
 }
 return best;
}
function decoyOption(p,owner,runner,{forward=1,line,opponents=[]}={}){
 if(!p||!owner||!runner?.point||p.id===owner.id||p.id===runner.id||p.role!=='ATT'||(p.energy??1)<.5||stat(p,'vision')<80||stat(p,'composure')<76)return null;
 if(distance(p,runner.point)<5||distance(p,owner)>28)return null;
 // Choose an actual observed blocker who is close enough to follow this
 // decoy. Never directly change the defender or assume it will follow.
 const marker=opponents.filter(d=>d.role!=='GK'&&d.active!==false&&(d.confidence??1)>.55&&(d.age??0)<.5&&distance(d,p)<4.0&&segmentDistance(d,owner,runner.point)<3.0).sort((a,b)=>distance(a,p)-distance(b,p))[0];
 if(!marker||!Number.isFinite(line))return null;
 const side=p.z>=runner.point.z?1:-1,point={x:forward*Math.min(p.x*forward+1.2,line-runMargin(p,forward)),z:clamp(p.z+side*6.0,-28,28)};
 if(distance(point,runner.point)<6||distance(point,p)<3.5||segmentDistance(point,owner,runner.point)<4)return null;
 const space=Math.min(12,...opponents.filter(d=>d.id!==marker.id).map(d=>distance(point,d)));
 if(space<3)return null;
 return {id:p.id,point,markerId:marker.id,markerOrigin:{x:marker.x,z:marker.z},runnerId:runner.id,origin:{x:p.x,z:p.z},score:space+stat(p,'vision')*.02};
}
function decoyOpened(decoy,marker,runner,owner,actor){
 if(!decoy||!marker||!runner||!owner||!actor||marker.id!==decoy.markerId||(marker.confidence??1)<.55||(marker.age??0)>.45)return false;
 const moved=distance(marker,decoy.markerOrigin),follow=distance(marker,actor),actorMoved=distance(actor,decoy.origin);
 return moved>1.5&&actorMoved>1.8&&follow<4.5&&segmentDistance(marker,owner,runner)>3.2&&segmentDistance(decoy.markerOrigin,owner,runner)<3;
}
function runPassBias(p,{kind,risk=1,arrivalRisk=1,space=0}={}){
 if(!['blind-side','diagonal','decoy-opening'].includes(kind)||risk>.38||arrivalRisk>.65||space<3||stat(p,'vision')<80)return 0;
 return clamp((stat(p,'vision')-78)*.085+(kind==='decoy-opening'?.6:.35),0,2.5);
}
// Local defensive choices. Contact geometry and referee remain authoritative.
function defensiveRead(p){
 return .38*stat(p,'tackling')+.34*stat(p,'composure')+.18*stat(p,'vision')+.10*stat(p,'agility');
}
function jockeyOption(p,carrier,ball,{forward=1,cover=null,receiver=null}={}){
 if(!carrier||!ball||p.role==='GK'||!['DEF','MID'].includes(p.role)||defensiveRead(p)<79||(p.energy??1)<.35||
  (carrier.confidence??1)<.55||(carrier.age??0)>.5||distance(p,ball)>7||distance(p,ball)<1.6)return null;
 const goalSide=(p.x-ball.x)*forward<-.3;
 if(!goalSide||!Number.isFinite(carrier.face))return null;
 const knownFoot=carrier.footPreference==='left'||carrier.footPreference==='right'?carrier.footPreference:null;
 const weakness=knownFoot&&Number.isFinite(carrier.weakFoot)?clamp((85-carrier.weakFoot)/35,0,1):0;
 const fx=Math.cos(carrier.face),fz=Math.sin(carrier.face);
 // Right foot = positive local lateral in the match coordinate convention.
 // Stand on the strong-foot side, leaving the other side as the escape.
 const strong=knownFoot==='right'?1:-1,offset=weakness*.85;
 const ahead={x:ball.x-forward*.8-fz*strong*offset,z:ball.z+fx*strong*offset};
 if(receiver&&distance(receiver,ball)>3){
  const dx=receiver.x-ball.x,dz=receiver.z-ball.z,len=Math.hypot(dx,dz);
  if(dx*forward<0){ahead.x+=dx/len*.35;ahead.z+=dz/len*.35;}
 }
 // Never offer a path through the central goal corridor to force a foot.
 const central=Math.abs(ball.z)<12,nearGoal=ball.x*forward<-32;
 if(central||nearGoal)ahead.z=ball.z+clamp(ahead.z-ball.z,-.35,.35);
 if(!cover||distance(cover,ball)>12)ahead.z=ball.z+clamp(ahead.z-ball.z,-.45,.45);
 ahead.x=forward*Math.min(ahead.x*forward,ball.x*forward-.45);
 const gap=distance(p,ball);
 return {point:{x:clamp(ahead.x,-51,51),z:clamp(ahead.z,-31.5,31.5)},pace:gap<3.5?.68:.87,
  kind:weakness>.2&&!central&&!nearGoal&&cover&&distance(cover,ball)<=12?'weak-foot':'jockey'};
}
function screenOption(p,carrier,receiver,base,{forward=1}={}){
 if(!carrier||!receiver||!base||defensiveRead(p)<80||(p.energy??1)<.35||p.role==='GK'||
  (carrier.confidence??1)<.55||(receiver.confidence??1)<.55||(receiver.age??0)>.5)return null;
 const dx=receiver.x-carrier.x,dz=receiver.z-carrier.z,range=Math.hypot(dx,dz);
 if(range<5||range>24||dx*forward>=-.6||distance(p,base)>10)return null;
 const t=clamp(((p.x-carrier.x)*dx+(p.z-carrier.z)*dz)/(range*range),.2,.65);
 const point={x:carrier.x+dx*t,z:carrier.z+dz*t};
 if(distance(point,base)>3.4||distance(point,carrier)<3||point.x*forward>carrier.x*forward-1.2)return null;
 return point;
}
function tackleDecision(p,carrier,ball,{aggression=.5,emergency=false,cover=false,gap,shield=false,fromBehind=false}={}){
 if(!p||!carrier||!ball||p.role==='GK'||defensiveRead(p)<77)return {kind:'standing',bonus:0};
 const dx=ball.x-p.x,dz=ball.z-p.z,d=Number.isFinite(gap)?gap:Math.hypot(dx,dz),exposure=distance(carrier,ball);
 const closing=((p.vx||0)-(ball.vx||0))*dx/Math.max(.01,d)+((p.vz||0)-(ball.vz||0))*dz/Math.max(.01,d);
 const relative=Math.hypot((p.vx||0)-(carrier.vx||0),(p.vz||0)-(carrier.vz||0));
 const timing=clamp((defensiveRead(p)-77)*.004,0,.085);
 // Defer marginal challenges only while the carrier still has control and
 // no immediate shot is threatened. A heavy touch remains an opportunity.
 if(!emergency&&(shield||fromBehind)&&exposure<.85&&d>.66&&aggression<.78)return {kind:'wait',retry:.16,bonus:0};
 const slide=stat(p,'tackling')>=86&&stat(p,'agility')>=76&&stat(p,'composure')>=78&&
  (p.energy??1)>.5&&!(p.yellow>0)&&!shield&&!fromBehind&&ball.y<.22&&
  d>=.88&&d<=1.15&&exposure>=.95&&closing>=1.7&&relative<5.8&&
  aggression>=.34&&aggression<=.78&&(emergency||cover);
 return {kind:slide?'slide':'standing',bonus:timing+(slide?.035:0)};
}
const api={passBias,canThread,carryBias,shouldDrive,canFeint,canHoldUp,runMargin,offBallOption,decoyOption,decoyOpened,runPassBias,defensiveRead,jockeyOption,screenOption,tackleDecision};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.TribunPlayerBrain=api;
})(typeof window!=='undefined'?window:globalThis);
