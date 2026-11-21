'use strict';
/* Canonical 1.88 m licensed human skeleton. Metres, Y up.
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
const dot=(a,b)=>a.reduce((s,n,i)=>s+n*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const D=Math.PI/180;
// These dimensions also define the licensed mesh bind pose. A pose never scales a bone.
const ANATOMY=Object.freeze({height:1.88,pelvisHeight:1.03,hipWidth:.26,shoulderWidth:.44,
 pelvis:.085,spine:.18,chest:.205,neck:.13,head:.25,thigh:.475,shin:.431,
 upperArm:.315,forearm:.29,hand:.17,palm:.115,foot:Math.hypot(.20,.075)});
const LIMITS=Object.freeze({knee:Object.freeze({min:.045,max:150*D}),elbow:Object.freeze({min:.06,max:150*D}),
 hip:Object.freeze({flexMin:-35*D,flexMax:125*D,abductMin:-35*D,abductMax:65*D}),
 shoulder:Object.freeze({flexMin:-70*D,flexMax:175*D,abductMin:-35*D,abductMax:90*D}),
 torso:Object.freeze({flexMin:-12*D,flexMax:55*D,rollMax:12*D}),presentationReach:.28});
// Project the endpoint onto the anatomical reach annulus, then solve the hinge.
// Both returned bones keep their length even for coincident or distant targets.
function solveLimb(start,target,upper,lower,pole=[1,0,0],maxFlex=150*D,minFlex=.045){
 if(!(upper>0&&lower>0)||![...start,...target,...pole,upper,lower,maxFlex,minFlex].every(Number.isFinite))throw Error('finite IK inputs and positive bone lengths required');
 const diff=sub(target,start),requested=len(diff),axis=requested>1e-9?mul(diff,1/requested):[0,-1,0];
 const reach=b=>Math.sqrt(Math.max(0,upper*upper+lower*lower+2*upper*lower*Math.cos(b)));
 const distance=clamp(requested,reach(maxFlex),reach(minFlex)),end=add(start,mul(axis,distance));
 const along=(upper*upper-lower*lower+distance*distance)/(2*distance),height=Math.sqrt(Math.max(0,upper*upper-along*along));
 let perp=sub(pole,mul(axis,dot(pole,axis)));
 if(len(perp)<1e-8){const fallback=Math.abs(axis[2])<.9?[0,0,1]:[0,1,0];perp=sub(fallback,mul(axis,dot(fallback,axis)));}
 const joint=add(add(start,mul(axis,along)),mul(unit(perp),height));
 const bend=Math.acos(clamp((distance*distance-upper*upper-lower*lower)/(2*upper*lower),-1,1));
 return {joint,end,bend,limited:Math.abs(distance-requested)>1e-7,error:len(sub(end,target))};
}
function solveKnee(hip,foot,upper=ANATOMY.thigh,lower=ANATOMY.shin,forward=[1,0,0]){return solveLimb(hip,foot,upper,lower,forward,LIMITS.knee.max,LIMITS.knee.min).joint;}
function rotateBetween(v,from,to){
 const c=clamp(dot(from,to),-1,1),axis=cross(from,to),sn=len(axis);
 if(sn<1e-9){if(c>0)return v.slice();const a=unit(cross(from,Math.abs(from[0])<.8?[1,0,0]:[0,0,1]));return sub(mul(a,2*dot(a,v)),v);}
 const a=mul(axis,1/sn);return add(add(mul(v,c),mul(cross(a,v),sn)),mul(a,dot(a,v)*(1-c)));
}
// Shoulder/hip angles are measured in the torso frame, so a diving body keeps
// the same joint limits as an upright body. Rotate the entire solved limb when
// its root exceeds the permitted range; never lengthen the distal segment.
function boundedLimb(start,target,upper,lower,pole,hinge,root,frame,side){
 const ik=solveLimb(start,target,upper,lower,pole,hinge.max,hinge.min);
 const angles=v=>({flex:Math.atan2(dot(v,frame.forward),-dot(v,frame.up)),abduct:Math.atan2(dot(v,frame.right)*side,Math.hypot(dot(v,frame.forward),dot(v,frame.up)))});
 const boundedFlex=v=>{if(v<root.flexMin)return root.flexMin-v<v+Math.PI*2-root.flexMax?root.flexMin:root.flexMax;if(v>root.flexMax)return v-root.flexMax<root.flexMin+Math.PI*2-v?root.flexMax:root.flexMin;return v;};
 const penalty=a=>angle(a.flex,boundedFlex(a.flex))**2+(a.abduct-clamp(a.abduct,root.abductMin,root.abductMax))**2;
 let v=unit(sub(ik.joint,start)),rootAngles=angles(v);
 // The hinge plane is free around the target axis. Select a legal elbow/knee
 // plane before sacrificing endpoint contact to a root-angle projection.
 if(penalty(rootAngles)>1e-12){
  const axis=unit(sub(ik.end,start)),along=dot(sub(ik.joint,start),axis),circle=sub(sub(ik.joint,start),mul(axis,along)),radius=len(circle),basis=unit(circle),other=cross(axis,basis);
  let bestScore=penalty(rootAngles),bestV=v,bestA=rootAngles;
  for(let j=1;j<32;j++){
   const t=j*Math.PI*2/32,candidate=unit(add(mul(axis,along),mul(add(mul(basis,Math.cos(t)),mul(other,Math.sin(t))),radius))),candidateAngles=angles(candidate);
   const score=penalty(candidateAngles)+1e-8*(1-Math.cos(t));
   if(score<bestScore){bestScore=score;bestV=candidate;bestA=candidateAngles;}
  }
  v=bestV;rootAngles=bestA;ik.joint=add(start,mul(v,upper));
 }
 const {flex,abduct}=rootAngles;
 const f=boundedFlex(flex),a=clamp(abduct,root.abductMin,root.abductMax);
 if(Math.abs(f-flex)>1e-8||Math.abs(a-abduct)>1e-8){
  const limited=add(add(mul(frame.forward,Math.sin(f)*Math.cos(a)),mul(frame.up,-Math.cos(f)*Math.cos(a))),mul(frame.right,side*Math.sin(a)));
  ik.joint=add(start,mul(limited,upper));ik.end=add(start,rotateBetween(sub(ik.end,start),v,limited));ik.limited=true;
 }
 ik.flex=f;ik.abduct=a;ik.error=len(sub(ik.end,target));return ik;
}
// Contact point is shared by the rig and ball simulation. Boot tip is at +.695m.
function kickContact(p){return world(p,.88,(p.kickFoot===0?-1:1)*.18,BALL_RADIUS);}
function kickAnkle(p){return world(p,.44,(p.kickFoot===0?-1:1)*.18,GROUND);}
function getState(p){let st=rigs.get(p);if(!st){st={phase:0,prevX:p.x,prevZ:p.z,lastFace:p.face||0,prevSpeed:0,turn:0,lean:0,activity:0,actionWeight:0,scanYaw:0,lastAction:'idle',feet:[0,1].map(i=>({pos:world(p,.03,(i?1:-1)*.15,GROUND),stance:true,face:p.face||0,start:null,adjust:0})),pose:null};rigs.set(p,st);}return st;}
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
 const stride=mix(1.0,2.2,smooth(speed/6))*(1-defensive*.22),duty=clamp(mix(.55,.20,smooth(speed/6))+defensive*.04,.20,.60);
 st.phase+=(travel/stride)+(speed<.3?Math.abs(yaw)*.12:0);
 const act=p.action||'idle',special=['pass','shoot','tackle','dive','catch','catch-ready','celebrate','protest','receive','throw','header'].includes(act)&&p.actionClock>0;
 // Gaze affects the drawn head only. It never turns the physical body or
 // changes contact anchors. Keep draw queries read-only by easing on update.
 const hasScan=Number.isFinite(p.perception?.headYaw),scanTarget=hasScan?clamp(p.perception.headYaw,-.8,.8):0;
 st.scanYaw=mix(st.scanYaw,scanTarget,1-Math.exp(-dt*(scanTarget?20:14)));
 if(Math.abs(st.scanYaw)<1e-6)st.scanYaw=0;
 st.actionWeight=mix(st.actionWeight,special?1:0,1-Math.exp(-dt*(special?24:12)));
 const action=st.actionWeight,kicking=(act==='pass'||act==='shoot')&&p.actionClock>0;
 const timed=kicking&&p.contactTime>0;
 const contact=timed?clamp((p.actionElapsed||0)/p.contactTime,0,1):smooth(1-clamp((p.actionClock||0)/.55,0,1));
 const after=timed?clamp(((p.actionElapsed||0)-p.contactTime)/Math.max(.05,(p.actionDuration||p.contactTime+FOLLOW)-p.contactTime),0,1):0;
 const kick= kicking?action*Math.sin(contact*Math.PI*.5)*(1-smooth(after)):0;
 const tackle=act==='tackle'?action:0,diving=act==='dive'?action:0,celebrating=act==='celebrate'?action:0,protest=act==='protest'?action:0;
 const bounce=st.activity*(.008+.014*sprint)*Math.sin(st.phase*4*Math.PI);
 const gather=gatherDrop(p),strike=kicking?Math.max(kick,smooth(contact/.9)*(1-smooth(after))):0;
 const hipHeight=ANATOMY.pelvisHeight+bounce-st.activity*.06-tackle*.16-gather-strike*.14;
 const feint=p.feintClock>0?Math.sin(p.feintClock/.35*Math.PI)*(p.feintSign??((p.personality??.6)>.5?1:-1))*.09:0;
 const headerU=act==='header'&&p.actionClock>0?clamp((p.actionElapsed||0)/Math.max(.1,p.actionDuration||.5),0,1):0,headerWave=Math.sin(Math.PI*headerU);
 const headerBend=p.headerHeight?clamp((1.77-p.headerHeight)*headerWave,0,.8):0;
 const pitch=clamp(st.lean*2+strike*.16+tackle*.48+headerBend,LIMITS.torso.flexMin,LIMITS.torso.flexMax),roll=clamp(st.turn*.25+feint,LIMITS.torso.rollMax*-1,LIMITS.torso.rollMax);
 const facing=[Math.cos(p.face||0),0,Math.sin(p.face||0)],right=[-facing[2],0,facing[0]];
 const up=unit(add(add(mul(facing,Math.sin(pitch)),[0,Math.cos(pitch)*Math.cos(roll),0]),mul(right,Math.sin(roll))));
 const bodyForward=unit(sub(facing,mul(up,dot(facing,up)))),bodyRight=unit(cross(bodyForward,up)),bodyFrame={forward:bodyForward,up,right:bodyRight};
 const pelvis=world(p,strike*.04,0,hipHeight),torsoBase=add(pelvis,mul(up,ANATOMY.pelvis));
 const torsoMid=add(torsoBase,mul(up,ANATOMY.spine)),torsoUpper=add(torsoMid,mul(up,ANATOMY.chest));
 const neck=add(torsoUpper,mul(up,ANATOMY.neck)),headTop=add(neck,mul(up,ANATOMY.head)),head=blend(neck,headTop,.5);
 const legs=[],arms=[];
 if(kicking&&!['pass','shoot'].includes(st.lastAction)){st.support=st.feet[p.kickFoot===0?1:0].pos.slice();st.movingSupport=false;}
 for(let i=0;i<2;i++){
  const side=i?1:-1,f=st.feet[i],hip=add(pelvis,mul(bodyRight,side*ANATOMY.hipWidth/2));
  const arc=((st.phase+i*.5)%1+1)%1,locomoting=speed>.15||travel>.001;
  const neutral=world(p,.03,side*.15,GROUND),touch=[neutral[0]+moveX*stride*duty*.5,GROUND,neutral[2]+moveZ*stride*duty*.5];
  let stance=locomoting?arc<duty:true;
  const tooFar=Math.hypot(f.pos[0]-neutral[0],f.pos[2]-neutral[2])>.36||Math.abs(angle(p.face||0,f.face))>.65;
  // Brake and pivot by taking a short replanting step, never by dragging a planted foot.
  if(!kicking&&!f.adjust&&(!locomoting&&tooFar||locomoting&&f.stance&&len(sub(f.pos,hip))>.88)){
   if(!st.feet[1-i].adjust){f.adjust=.0001;f.adjustDuration=locomoting?.08:.22;f.start=f.pos.slice();f.adjustTarget=(locomoting?touch:neutral).slice();f.stance=false;}
  }
  if(f.adjust){
   const adjustDuration=f.adjustDuration||.22;f.adjust=Math.min(adjustDuration,f.adjust+dt);const u=smooth(f.adjust/adjustDuration);
   f.pos=blend(f.start,f.adjustTarget,u);f.pos[1]+=Math.sin(u*Math.PI)*.13;stance=false;
   if(f.adjust>=adjustDuration){f.adjust=0;f.stance=true;f.face=p.face;stance=true;}
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
  const requestedFoot=foot.slice(),legIK=boundedLimb(hip,foot,ANATOMY.thigh,ANATOMY.shin,facing,LIMITS.knee,LIMITS.hip,bodyFrame,side);
  foot=legIK.end;if(legIK.error>1e-5)stance=false;
  const toe=add(foot,[Math.cos(footFace)*.20,-.075,Math.sin(footFace)*.20]);
  legs.push({hip,knee:legIK.joint,ankle:foot,toe,stance,footLift:foot[1]-GROUND,bend:legIK.bend,flex:legIK.flex,abduct:legIK.abduct,target:requestedFoot,targetError:legIK.error});
  const shoulder=add(torsoUpper,mul(bodyRight,side*ANATOMY.shoulderWidth/2));
  const swing=-Math.sin(st.phase*2*Math.PI+i*Math.PI)*st.activity*(.22+.12*sprint);
  let wrist=world(p,swing+kick*(i===1?-.35:.24),side*(.255+kick*.10),.94+bounce+celebrating*.93+protest*.30-tackle*.17-gather);
  if(act==='throw'&&p.actionClock>0){const u=smooth((p.actionElapsed||0)/Math.max(.1,p.contactTime||.55));wrist=blend(wrist,world(p,mix(-.06,.4,u),side*.12,1.95),action);}
  arms.push({shoulder,target:wrist});
 }
 let result={pelvis,neck,head,headTop,torsoBase,torsoMid,torsoUpper,legs,arms,activity:st.activity,sprint,kick,tackle,diving,celebrating,protest,face:p.face,action:act,weight:action,turn:st.turn};
 if(hasScan||st.scanYaw){result.headYaw=st.scanYaw;result.headFace=(p.face||0)+st.scanYaw;}
 let frame=bodyFrame,contactTargets=null;
 const bodyKeys=['pelvis','neck','head','headTop','torsoBase','torsoMid','torsoUpper'];
 if(diving>.001){
  const d=getDive(p),origin=d.transform([0,0,0]),vector=v=>sub(d.transform(v),origin);
  for(const key of bodyKeys)result[key]=d.transform(result[key]);
  for(const leg of legs){for(const key of ['hip','knee','ankle','toe','target'])leg[key]=d.transform(leg[key]);leg.stance=false;}
  for(const arm of arms){arm.shoulder=d.transform(arm.shoulder);arm.target=d.transform(arm.target);}
  frame={forward:vector(bodyFrame.forward),up:vector(bodyFrame.up),right:vector(bodyFrame.right)};
  contactTargets=d.wrists;result.diving=d.reach;
 }else if(['catch','catch-ready'].includes(act)&&p.actionClock>0){contactTargets=catchHands(p);}
 // Legacy saveHands points are physical palm contacts. The drawn wrist sits
 // behind that point; presentation-only root correction keeps short human
 // arms near a far contact without writing any simulation coordinates.
 let shift=[0,0,0];
 if(contactTargets){
  const maxReach=Math.sqrt(ANATOMY.upperArm**2+ANATOMY.forearm**2+2*ANATOMY.upperArm*ANATOMY.forearm*Math.cos(LIMITS.elbow.min))+ANATOMY.palm;
  for(let iteration=0;iteration<12;iteration++){
   let correction=[0,0,0];
   for(let i=0;i<2;i++){
    const shoulder=add(arms[i].shoulder,shift),target=contactTargets[i],delta=sub(target,shoulder),distance=len(delta);
    if(distance>maxReach)correction=add(correction,mul(unit(delta),(distance-maxReach)*.65));
    else {
     const wrist=sub(target,mul(unit(delta),ANATOMY.palm)),pole=add(mul(frame.forward,-.65),mul(frame.right,(i?1:-1)*.5));
     const ik=boundedLimb(shoulder,wrist,ANATOMY.upperArm,ANATOMY.forearm,pole,LIMITS.elbow,LIMITS.shoulder,frame,i?1:-1),palm=add(ik.end,mul(unit(sub(target,ik.end)),ANATOMY.palm));
     correction=add(correction,mul(sub(target,palm),.5));
    }
   }
   shift=add(shift,correction);if(len(shift)>LIMITS.presentationReach)shift=mul(unit(shift),LIMITS.presentationReach);
   if(len(correction)<1e-7)break;
  }
  for(const key of bodyKeys)result[key]=add(result[key],shift);
  for(const arm of arms)arm.shoulder=add(arm.shoulder,shift);
  if(diving>.001){for(const leg of legs)for(const key of ['hip','knee','ankle','toe','target'])leg[key]=add(leg[key],shift);}
  else for(let i=0;i<2;i++){
   const leg=legs[i],oldAnkle=leg.ankle,oldToe=leg.toe;leg.hip=add(leg.hip,shift);
   const ik=boundedLimb(leg.hip,leg.target,ANATOMY.thigh,ANATOMY.shin,frame.forward,LIMITS.knee,LIMITS.hip,frame,i?1:-1);
   leg.knee=ik.joint;leg.ankle=ik.end;leg.toe=add(ik.end,sub(oldToe,oldAnkle));leg.bend=ik.bend;leg.flex=ik.flex;leg.abduct=ik.abduct;leg.targetError=ik.error;if(ik.error>1e-5)leg.stance=false;
  }
 }
 for(let i=0;i<2;i++){
  const arm=arms[i],side=i?1:-1,palm=contactTargets&&contactTargets[i];
  const wristTarget=palm?sub(palm,mul(unit(sub(palm,arm.shoulder)),ANATOMY.palm)):arm.target;
  const pole=add(mul(frame.forward,-.65),mul(frame.right,side*.5));
  const ik=boundedLimb(arm.shoulder,wristTarget,ANATOMY.upperArm,ANATOMY.forearm,pole,LIMITS.elbow,LIMITS.shoulder,frame,side);
  const handDirection=palm?unit(sub(palm,ik.end)):unit(sub(ik.end,ik.joint));
  arms[i]={shoulder:arm.shoulder,elbow:ik.joint,wrist:ik.end,hand:add(ik.end,mul(handDirection,ANATOMY.hand)),palm:add(ik.end,mul(handDirection,ANATOMY.palm)),bend:ik.bend,flex:ik.flex,abduct:ik.abduct,target:wristTarget,targetError:ik.error};
  if(palm){arms[i].contactTarget=palm.slice();arms[i].contactError=len(sub(arms[i].palm,palm));}
 }
 result.presentationOffset=shift;result.contactError=contactTargets?Math.max(...arms.map(a=>a.contactError)):0;
 if(headerWave>0){
  const jump=headerWave*(p.headerHeight?clamp((p.headerHeight-1.77)/.905,0,.33):.23);
  for(const key of bodyKeys)result[key][1]+=jump;
  for(const leg of legs){for(const key of ['hip','knee','ankle','toe','target'])leg[key][1]+=jump;leg.stance=false;}
  for(const arm of arms)for(const key of ['shoulder','elbow','wrist','hand','palm','target'])arm[key][1]+=jump;
 }
 st.prevX=p.x;st.prevZ=p.z;st.lastFace=p.face||0;st.prevSpeed=speed;st.lastAction=act;st.pose=result;
 return result;
}
// The builder and GPU renderer share these exact immutable segment endpoints.
// No caller may invent shoulder offsets or independently retarget torso bones.
const frameCache=new WeakMap();
function boneFrames(pose){
 if(frameCache.has(pose))return frameCache.get(pose);
 const segment=(a,b)=>Object.freeze([Object.freeze(a.slice()),Object.freeze(b.slice())]);
 const frames={pelvis:segment(pose.pelvis,pose.torsoBase),spine:segment(pose.torsoBase,pose.torsoMid),chest:segment(pose.torsoMid,pose.torsoUpper),neck:segment(pose.torsoUpper,pose.neck),head:segment(pose.neck,pose.headTop)};
 for(let i=0;i<2;i++){
  const side=i?'R':'L',a=pose.arms[i],l=pose.legs[i];
  Object.assign(frames,{['clavicle.'+side]:segment(pose.torsoUpper,a.shoulder),['upper_arm.'+side]:segment(a.shoulder,a.elbow),['forearm.'+side]:segment(a.elbow,a.wrist),['hand.'+side]:segment(a.wrist,a.hand),['thigh.'+side]:segment(l.hip,l.knee),['shin.'+side]:segment(l.knee,l.ankle),['foot.'+side]:segment(l.ankle,l.toe)});
 }
 Object.freeze(frames);frameCache.set(pose,frames);return frames;
}
function reset(p){rigs.delete(p);}
const API={pose,update:pose,getPose:p=>getState(p).pose||pose(p,0),reset,solveKnee,solveLimb,boneFrames,ANATOMY,LIMITS,kickContact,kickAnkle,getDive,catchHands,saveHands,BALL_RADIUS};
if(typeof module!=='undefined'&&module.exports)module.exports=API;
global.TribunHumanoidRig=API;
})(typeof window!=='undefined'?window:globalThis);
