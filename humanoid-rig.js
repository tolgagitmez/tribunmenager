'use strict';
/* Original procedural humanoid. Metres, Y up. No external models or clips.
   update() belongs to the fixed simulation; getPose() is a read-only draw operation. */
(function(global){
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),mix=(a,b,t)=>a+(b-a)*t;
const smooth=v=>{v=clamp(v,0,1);return v*v*(3-2*v)};
const add=(a,b)=>a.map((v,i)=>v+b[i]),sub=(a,b)=>a.map((v,i)=>v-b[i]);
const mul=(a,k)=>a.map(v=>v*k),len=a=>Math.hypot(...a),unit=a=>mul(a,1/(len(a)||1));
const blend=(a,b,t)=>a.map((v,i)=>mix(v,b[i],t));
const angle=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
const world=(p,f,s,y)=>[p.x+f*Math.cos(p.face)-s*Math.sin(p.face),y,p.z+f*Math.sin(p.face)+s*Math.cos(p.face)];
const rigs=new WeakMap(),GROUND=.13,BALL_RADIUS=.11,FOLLOW=.30;
function solveKnee(hip,foot,upper=.47,lower=.47,forward=[1,0,0]){
 const diff=sub(foot,hip),distance=clamp(len(diff),.001,upper+lower-.002),axis=unit(diff);
 const along=(upper*upper-lower*lower+distance*distance)/(2*distance);
 const height=Math.sqrt(Math.max(0,upper*upper-along*along));
 let perp=sub(forward,mul(axis,forward.reduce((sum,n,i)=>sum+n*axis[i],0)));
 if(len(perp)<.001){const fallback=Math.abs(axis[2])<.9?[0,0,1]:[0,1,0];perp=sub(fallback,mul(axis,fallback.reduce((s,n,i)=>s+n*axis[i],0)));}
 return add(add(hip,mul(axis,along)),mul(unit(perp),height));
}
// Contact point is shared by the rig and ball simulation. Boot tip is at +.695m.
function kickContact(p){return world(p,.88,(p.kickFoot===0?-1:1)*.18,BALL_RADIUS);}
function kickAnkle(p){return world(p,.44,(p.kickFoot===0?-1:1)*.18,GROUND);}
function getState(p){let st=rigs.get(p);if(!st){st={phase:0,prevX:p.x,prevZ:p.z,lastFace:p.face||0,prevSpeed:0,turn:0,lean:0,activity:0,actionWeight:0,lastAction:'idle',feet:[0,1].map(i=>({pos:world(p,.03,(i?1:-1)*.19,GROUND),stance:true,face:p.face||0,start:null,adjust:0})),pose:null};rigs.set(p,st);}return st;}
function getDive(p){
 const t=p.actionElapsed||0,contact=Math.max(.10,p.diveContactTime||.34),duration=p.actionDuration||.95;
 const extension=smooth(t/contact),recover=smooth((t-contact-.12)/Math.max(.15,duration-contact-.12));
 const side=p.diveSide||1,target=p.saveTarget||{x:p.x,y:1,z:p.z+side*1.6},high=clamp((target.y-1.45)/.85,0,1);
 // High saves push upwards and keep the torso more upright. Rolling the
 // shoulders down for every height made reachable upper shots impossible.
 const reach=extension*(1-recover),theta=side*(1.08-high*.65)*reach;
 const pivot=[p.x,.87,p.z],c=Math.cos(theta),s=Math.sin(theta),launch=Math.min(.45+contact*4.0,clamp(Math.abs(target.z-p.z)*.42,.50,1.25));
 const lift=high*.40*Math.min(1,contact/.30);
 const transform=a=>[a[0]+(p.diveForward||0)*reach,pivot[1]+(a[1]-pivot[1])*c-(a[2]-pivot[2])*s+(-.20+lift)*reach,pivot[2]+(a[1]-pivot[1])*s+(a[2]-pivot[2])*c+side*launch*reach];
 const shoulders=[-1,1].map(v=>transform(world(p,-.02,v*.32,1.47)));
 const wrists=shoulders.map((sh,i)=>{
  const neutral=transform(world(p,.12,(i?1:-1)*.43,1.05));
  const desired=blend(neutral,[target.x+(i?1:-1)*.08,target.y+(i?1:-1)*.06,target.z],reach);
  const delta=sub(desired,sh),d=len(delta);return d>.72?add(sh,mul(delta,.72/d)):desired;
 });
 return {transform,shoulders,wrists,reach,recovery:recover};
}
function gatherDrop(p){
 if(!['catch','catch-ready'].includes(p.action)||!(p.actionClock>0))return 0;
 const height=p.catchPoint?.y??1.1,t=clamp((p.actionElapsed||0)/.22,0,1);
 const progress=p.action==='catch'?smooth(mix(p.gatherStart??1,1,smooth((p.actionElapsed||0)/.12))):smooth(t);
 return clamp((.95-height)/.84,0,1)*.56*progress;
}
function catchHands(p){
 const point=p.catchPoint||{x:p.x+.25*Math.cos(p.face),y:1.1,z:p.z+.25*Math.sin(p.face)};
 return [-1,1].map(side=>{const shoulder=world(p,.015,side*.32,1.47-gatherDrop(p)),target=[point.x-side*Math.sin(p.face)*.07,point.y,point.z+side*Math.cos(p.face)*.07],delta=sub(target,shoulder),d=len(delta);return d>.66?add(shoulder,mul(delta,.66/d)):target;});
}
function saveHands(p){return ['catch','catch-ready'].includes(p.action)?catchHands(p):getDive(p).wrists;}
function pose(p,dt=1/60){
 const st=getState(p);dt=clamp(Number(dt)||0,0,.1);
 if(dt===0&&st.pose)return st.pose;
 const speed=clamp(Number(p.speed)||0,0,9),dx=p.x-st.prevX,dz=p.z-st.prevZ,travel=Math.hypot(dx,dz);
 const yaw=angle(p.face||0,st.lastFace),teleport=travel>1.5;
 if(teleport){rigs.delete(p);return pose(p,0);}
 const alpha=1-Math.exp(-dt*12),sprint=smooth((speed-2)/4.5);
 st.activity=mix(st.activity,smooth(speed/2),alpha);
 st.turn=mix(st.turn,clamp(yaw/Math.max(dt,.001),-4,4)*.085,alpha);
 st.lean=mix(st.lean,clamp((speed-st.prevSpeed)/Math.max(dt,.001),-10,8)*.008,alpha);
 // The body may face the ball while the player shuffles or retreats. Swing
 // feet along actual travel, with shorter defensive steps, rather than
 // sending every footfall forwards in the direction of the chest.
 const fx=Math.cos(p.face||0),fz=Math.sin(p.face||0),moveX=travel>.0001?dx/travel:fx,moveZ=travel>.0001?dz/travel:fz;
 const forwardTravel=moveX*fx+moveZ*fz,lateralTravel=Math.abs(-moveX*fz+moveZ*fx),defensive=Math.max(lateralTravel,Math.max(0,-forwardTravel));
 const stride=mix(1.2,3.0,smooth(speed/6))*(1-defensive*.22),duty=clamp(mix(.61,.34,smooth(speed/6))+defensive*.06,.34,.7);
 st.phase+=(travel/stride)+(speed<.3?Math.abs(yaw)*.12:0);
 const act=p.action||'idle',special=['pass','shoot','tackle','dive','catch','catch-ready','celebrate','protest','receive','throw','header'].includes(act)&&p.actionClock>0;
 st.actionWeight=mix(st.actionWeight,special?1:0,1-Math.exp(-dt*(special?24:12)));
 const action=st.actionWeight,kicking=(act==='pass'||act==='shoot')&&p.actionClock>0;
 const timed=kicking&&p.contactTime>0;
 const contact=timed?clamp((p.actionElapsed||0)/p.contactTime,0,1):smooth(1-clamp((p.actionClock||0)/.55,0,1));
 const after=timed?clamp(((p.actionElapsed||0)-p.contactTime)/Math.max(.05,(p.actionDuration||p.contactTime+FOLLOW)-p.contactTime),0,1):0;
 const kick= kicking?action*Math.sin(contact*Math.PI*.5)*(1-smooth(after)):0;
 const tackle=act==='tackle'?action:0,diving=act==='dive'?action:0,celebrating=act==='celebrate'?action:0,protest=act==='protest'?action:0;
 const bounce=st.activity*(.012+.025*sprint)*Math.sin(st.phase*4*Math.PI);
 const gather=gatherDrop(p),hipHeight=.87+bounce-tackle*.16-gather;
 const feint=p.feintClock>0?Math.sin(p.feintClock/.35*Math.PI)*(p.feintSign??((p.personality??.6)>.5?1:-1))*.09:0;
 const pelvis=world(p,-.04,0,hipHeight),torsoBase=world(p,-.05,0,1.08+bounce-tackle*.18-gather);
 const torsoUpper=world(p,.02+st.lean+kick*.08,st.turn*.1+feint,1.47+bounce-tackle*.24-gather);
 const neck=world(p,.025+st.lean+kick*.07,st.turn*.12+feint*.7,1.59+bounce-tackle*.24-gather);
 const head=world(p,.025+st.lean+kick*.10,st.turn*.15+feint*.5,1.77+bounce-tackle*.25-gather);
 const facing=[Math.cos(p.face||0),0,Math.sin(p.face||0)];
 const legs=[],arms=[];
 if(kicking&&!['pass','shoot'].includes(st.lastAction)){st.support=st.feet[p.kickFoot===0?1:0].pos.slice();st.movingSupport=false;}
 for(let i=0;i<2;i++){
  const side=i?1:-1,f=st.feet[i],hip=world(p,-.04,side*.153,hipHeight);
  const arc=((st.phase+i*.5)%1+1)%1,locomoting=speed>.15||travel>.001;
  const neutral=world(p,.03,side*.19,GROUND),touch=[neutral[0]+moveX*stride*duty*.5,GROUND,neutral[2]+moveZ*stride*duty*.5];
  let stance=locomoting?arc<duty:true;
  const tooFar=Math.hypot(f.pos[0]-neutral[0],f.pos[2]-neutral[2])>.36||Math.abs(angle(p.face||0,f.face))>.65;
  // Brake and pivot by taking a short replanting step, never by dragging a planted foot.
  if(!kicking&&!f.adjust&&(!locomoting&&tooFar||f.stance&&len(sub(f.pos,hip))>.925)){
   if(!st.feet[1-i].adjust){f.adjust=.0001;f.start=f.pos.slice();f.adjustTarget=(locomoting?touch:neutral).slice();f.stance=false;}
  }
  if(f.adjust){
   f.adjust=Math.min(.22,f.adjust+dt);const u=smooth(f.adjust/.22);
   f.pos=blend(f.start,f.adjustTarget,u);f.pos[1]+=Math.sin(u*Math.PI)*.13;stance=false;
   if(f.adjust>=.22){f.adjust=0;f.stance=true;f.face=p.face;stance=true;}
  }else if(stance){
   if(!f.stance){f.pos[1]=GROUND;f.face=p.face;}
   f.stance=true;f.start=null;
  }else{
   const cycleU=clamp((arc-duty)/(1-duty),0,1);
   if(f.stance||!f.start){f.start=f.pos.slice();f.swingStart=cycleU;f.swingTime=0;}
   f.swingTime=(f.swingTime||0)+dt;
   const u=smooth(Math.min(clamp((cycleU-(f.swingStart||0))/Math.max(.01,1-(f.swingStart||0)),0,1),f.swingTime/.16));f.pos=blend(f.start,touch,u);f.pos[1]=GROUND+Math.sin(u*Math.PI)*(.13+.12*sprint);f.face+=angle(p.face||0,f.face)*alpha;f.stance=false;
  }
  let foot=f.pos.slice(),footFace=f.face;
  if(kicking){
   if(i===(p.kickFoot===0?0:1)){
    let target;
    if(contact<.43)target=world(p,mix(.03,-.30,smooth(contact/.43)),side*.18,mix(GROUND,.34,smooth(contact/.43)));
    else target=blend(world(p,-.30,side*.18,.34),kickAnkle(p),smooth((contact-.43)/.57));
    if(after>0){const peak=world(p,.64,side*.18,.36);target=after<.4?blend(kickAnkle(p),peak,smooth(after/.4)):blend(peak,neutral,smooth((after-.4)/.6));}
    // At contact use the exact IK target shared with the ball, without blend lag.
    foot=blend(foot,target,contact>.9?1:action);stance=false;
   }else if(p.kickMoving&&(contact<.72||after>.18)){
    // Keep stepping through a running strike; plant only around the contact window.
    st.movingSupport=false;
   }else {
    if(p.kickMoving&&!st.movingSupport){st.support=foot.slice();st.support[1]=GROUND;st.movingSupport=true;}
    foot=(st.support||neutral).slice();stance=true;
   }
   footFace=p.face;f.pos=foot.slice();f.stance=stance;f.face=footFace;
  }
  if(!kicking&&act!=='receive'&&p.footTouch>0&&p.touchPosition&&i===p.dribbleFoot){const w=Math.sin(clamp(p.footTouch/.14,0,1)*Math.PI/2)*.72;const target=[p.touchPosition.x-facing[0]*.24,GROUND,p.touchPosition.z-facing[2]*.24];foot=blend(foot,target,w);footFace=p.face;stance=false;}
  if(tackle>.01){foot=blend(foot,world(p,.50+side*.12,side*.33,.12),tackle);stance=false;}
  if(act==='receive'&&i===(p.kickFoot===0?0:1)){const cushion=Math.sin(Math.PI*clamp((p.actionElapsed||0)/Math.max(.01,p.actionDuration||.25),0,1));foot=blend(foot,world(p,.26,side*.18,.17),cushion*.65);stance=false;}
  const reach=sub(foot,hip),distance=len(reach);
  if(distance>.935){foot=add(hip,mul(reach,.935/distance));stance=false;}
  const knee=solveKnee(hip,foot,.47,.47,facing),toe=add(foot,[Math.cos(footFace)*.20,0,Math.sin(footFace)*.20]);
  legs.push({hip,knee,ankle:foot,toe,stance,footLift:foot[1]-GROUND});
  const shoulder=world(p,.015+st.lean,side*.32,1.47+bounce-tackle*.23-gather);
  const swing=-Math.sin(st.phase*2*Math.PI+i*Math.PI)*st.activity*(.22+.12*sprint);
  let wrist=world(p,swing+kick*(i===1?-.35:.24),side*(.43+kick*.12),1.03+bounce+celebrating*.93+protest*.30-tackle*.17);
  if(act==='throw'&&p.actionClock>0){const u=smooth((p.actionElapsed||0)/Math.max(.1,p.contactTime||.55));wrist=blend(wrist,world(p,mix(-.06,.4,u),side*.12,1.95),action);}
  if(['catch','catch-ready'].includes(act)&&p.actionClock>0)wrist=blend(wrist,catchHands(p)[i],action);
  const elbow=solveKnee(shoulder,wrist,.33,.34,world({x:0,z:0,face:p.face},-.1,side,.1));
  arms.push({shoulder,elbow,wrist});
 }
 let result={pelvis,neck,head,torsoBase,torsoUpper,legs,arms,activity:st.activity,sprint,kick,tackle,diving,celebrating,protest,face:p.face,action:act,weight:action,turn:st.turn};
 if(diving>.001){
  const d=getDive(p);
  for(const key of ['pelvis','neck','head','torsoBase','torsoUpper'])result[key]=d.transform(result[key]);
  for(const leg of legs){for(const key of ['hip','knee','ankle','toe'])leg[key]=d.transform(leg[key]);leg.stance=false;}
  for(let i=0;i<2;i++){arms[i]={shoulder:d.shoulders[i],wrist:d.wrists[i],elbow:solveKnee(d.shoulders[i],d.wrists[i],.36,.36,[-1,.15,0])};}
  result.diving=d.reach;
 }
 if(act==='header'&&p.actionClock>0){const u=clamp((p.actionElapsed||0)/Math.max(.1,p.actionDuration||.5),0,1),wave=Math.sin(Math.PI*u),jump=wave*(p.headerHeight?clamp((p.headerHeight-1.77)/.905,0,.33):.23);const bend=p.headerHeight?Math.min(0,p.headerHeight-1.77)*wave/.905:0;result.head[1]+=bend;result.neck[1]+=bend*.7;result.torsoUpper[1]+=bend*.45;for(const key of ['pelvis','neck','head','torsoBase','torsoUpper'])result[key][1]+=jump;for(const l of legs){for(const key of ['hip','knee','ankle','toe'])l[key][1]+=jump;l.stance=false;}for(const a of arms)for(const key of ['shoulder','elbow','wrist'])a[key][1]+=jump;}
 st.prevX=p.x;st.prevZ=p.z;st.lastFace=p.face||0;st.prevSpeed=speed;st.lastAction=act;st.pose=result;
 return result;
}
function reset(p){rigs.delete(p);}
const API={pose,update:pose,getPose:p=>getState(p).pose||pose(p,0),reset,solveKnee,kickContact,kickAnkle,saveHands,BALL_RADIUS};
if(typeof module!=='undefined'&&module.exports)module.exports=API;
global.TribunHumanoidRig=API;
})(typeof window!=='undefined'?window:globalThis);
