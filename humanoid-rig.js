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
// Per-player uniform proportions. Keep the canonical rig immutable.
const anatomyFor=p=>{
 const scale=Number.isFinite(p.nativeAnatomy?.scale)?clamp(p.nativeAnatomy.scale,1.45/1.88,2.15/1.88):1;
 return scale===1?ANATOMY:Object.fromEntries(Object.entries(ANATOMY).map(([k,v])=>[k,v*scale]));
};
const bodyScaleFor=p=>anatomyFor(p).height/ANATOMY.height;
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
function getState(p){let st=rigs.get(p);if(!st){st={phase:0,prevX:p.x,prevZ:p.z,lastFace:p.face||0,prevSpeed:0,turn:0,lean:0,activity:0,actionWeight:0,scanYaw:0,shieldWeight:0,lastAction:'idle',feet:[0,1].map(i=>({pos:world(p,.03,(i?1:-1)*.15*bodyScaleFor(p),GROUND*bodyScaleFor(p)),stance:true,face:p.face||0,start:null,adjust:0})),pose:null};rigs.set(p,st);}return st;}
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
// Stage 89: match measured motion features to procedural step templates.
// Features are in body-local metres/second, with brake and turn cues.
// This is a small parameter library, not motion-capture clip matching.
const STEP_PROFILES=Object.freeze([
 {id:'idle',v:0,dir:[0,0],brake:0,turn:0,duration:.24,lead:0,lift:.07,stride:.72,duty:.64},
 {id:'walk',v:1.1,dir:[1,0],brake:0,turn:0,duration:.24,lead:.08,lift:.10,stride:.84,duty:.60},
 {id:'jog',v:2.5,dir:[1,0],brake:0,turn:0,duration:.20,lead:.12,lift:.13,stride:1.15,duty:.51},
 {id:'run',v:4.3,dir:[1,0],brake:0,turn:0,duration:.155,lead:.16,lift:.17,stride:1.55,duty:.43},
 {id:'sprint',v:6.7,dir:[1,0],brake:0,turn:0,duration:.115,lead:.18,lift:.21,stride:2.0,duty:.35},
 {id:'shuffle-left',v:2.8,dir:[0,-1],brake:0,turn:0,duration:.18,lead:.07,lift:.11,stride:.94,duty:.56},
 {id:'shuffle-right',v:2.8,dir:[0,1],brake:0,turn:0,duration:.18,lead:.07,lift:.11,stride:.94,duty:.56},
 {id:'backpedal',v:2.6,dir:[-1,0],brake:0,turn:0,duration:.18,lead:.07,lift:.12,stride:1.0,duty:.55},
 {id:'brake',v:3.4,dir:[1,0],brake:1,turn:0,duration:.13,lead:.035,lift:.12,stride:.80,duty:.62},
 {id:'pivot',v:1.5,dir:[0,0],brake:0,turn:1,duration:.15,lead:.025,lift:.12,stride:.68,duty:.60}
].map(Object.freeze));
// Stage 90: conservative, presentation-only identity tuning. All dimensions
// and actual motion remain those of the native player and canonical rig.
function motionIdentityFactors(traits,profile){
 if(!traits)return null;
 const read=k=>Number.isFinite(traits[k])?clamp(traits[k],0,1):.5;
 const agility=read('agility'),velocity=read('velocity'),acceleration=read('acceleration'),
  balance=read('balance'),freshness=read('freshness');
 const fast=profile==='sprint'||profile==='run',turn=profile==='pivot'||profile==='brake'||profile.startsWith('shuffle')||profile==='backpedal';
 return {
  stride:clamp(1+(fast?(velocity-.5)*.14:(agility-.5)*-.08)-(1-freshness)*.10,.82,1.10),
  duration:clamp(1-(turn?(agility-.5)*.22:(acceleration-.5)*.12)+(1-freshness)*.13,.86,1.22),
  lift:clamp(1+(agility-.5)*.10-(1-freshness)*.16,.80,1.08),
  lead:clamp(1+(fast?(velocity-.5)*.12:(balance-.5)*.10)-(1-freshness)*.08,.85,1.08),
  arm:clamp(1+(velocity-.5)*.10-(1-freshness)*.15,.80,1.08),
  duty:clamp((1-freshness)*.06+(balance-.5)*.025,-.02,.075)
 };
}
function matchNativeStep({forward=0,lateral=0,brake=0,turn=0},prior=null){
 const speed=Math.hypot(forward,lateral),denom=Math.max(.2,speed);
 const b=clamp(brake/6,0,1),t=clamp(turn/4,0,1);
 let best=null,bestCost=Infinity;
 for(const m of STEP_PROFILES){
  const speedCost=((speed-m.v)/2.4)**2;
  const directional=m.dir[0]===0&&m.dir[1]===0?(m.id==='idle'?clamp(speed/2,0,1):.16):
   (1-(forward*m.dir[0]+lateral*m.dir[1])/denom)*clamp(speed,0,1)*1.65;
  const cost=speedCost+directional+2.8*(b-m.brake)**2+2.6*(t-m.turn)**2+(prior&&prior!==m.id?.18:0);
  if(cost<bestCost){best=m;bestCost=cost;}
 }
 return {profile:best,cost:bestCost};
}
// Stage 80: presentation-only foot swing with explicit landing. The
// support anchor is never translated to follow the root during stance.
function nativeStep(p,st,i,hip,neutral,arc,duty,speed,locomoting,dt){
 const anatomy=anatomyFor(p),ground=GROUND*bodyScaleFor(p);
 const f=st.feet[i],other=st.feet[1-i],wanted=locomoting?arc<duty:true;
 const reach=anatomy.thigh+anatomy.shin;
 const vertical=hip[1]-ground,range=Math.sqrt(Math.max(0,reach*reach-vertical*vertical));
 const distance=Math.hypot(f.pos[0]-hip[0],f.pos[2]-hip[2]);
 const vx=Number.isFinite(p.vx)?p.vx:0,vz=Number.isFinite(p.vz)?p.vz:0;
 const cue=p.nativeBodyBalance,brake=cue?.valid?Math.max(0,-(cue.ax*vx+cue.az*vz)/Math.max(.5,speed)):0;
 const turn=cue?.valid?Math.abs(cue.az*vx-cue.ax*vz)/Math.max(.5,speed):0;
 const recovery=clamp(brake/8+turn/10,0,1);
 const match=p.nativeMotionMatch===true?st.motionMatch:null;
 const template=match?.profile;
 const identity=match?.identity;
 const needsPlant=distance>Math.max(.045,range*.78)||Math.abs(angle(p.face||0,f.face))>.50;
 const scheduled=!wanted&&f.nativeWanted!==false;
 f.nativeWanted=wanted;
 if(!f.nativeSwing&&(scheduled||needsPlant)&&
    (speed>3.2||!other.nativeSwing)){
  const duration=template?clamp(template.duration*(identity?.duration??1)*(1-.12*recovery),.085,.26):clamp(mix(.26,.115,smooth(speed/6))*(1-.28*recovery),.085,.26);
  const prior=st.pose?.legs[i]?.ankle;
  f.nativeSwing={elapsed:0,duration,start:(prior||f.pos).slice()};
  if(template){
   // Latch the selected template for this swing. Predict a landing in
   // world space once, then allow only small rate-limited corrections.
   const lead=Math.min(template.lead*(identity?.lead??1),range*.4);
   const dx=vx/Math.max(.5,speed),dz=vz/Math.max(.5,speed);
   f.nativeSwing.profile=template;
   f.nativeSwing.identity=identity?{...identity}:null;
   f.nativeSwing.target=[neutral[0]+vx*duration+dx*lead,ground,neutral[2]+vz*duration+dz*lead];
   f.nativeSwing.face=p.face;
  }
  f.adjust=0;f.start=null;f.stance=false;
 }
 if(f.nativeSwing){
  const s=f.nativeSwing;s.elapsed=Math.min(s.duration,s.elapsed+dt);
  const u=s.elapsed/s.duration,e=smooth(u),remaining=s.duration-s.elapsed;
  // Predict root at landing, but cap local lead by available anatomical reach.
  const lead=Math.min(.18,range*.40)*(1-.65*recovery);
  const dx=vx/Math.max(.5,speed),dz=vz/Math.max(.5,speed);
  const target=[neutral[0]+vx*remaining+dx*lead,ground,neutral[2]+vz*remaining+dz*lead];
  if(s.profile){
   const lead=Math.min(s.profile.lead*(s.identity?.lead??1),range*.4);
   const desired=[neutral[0]+vx*remaining+dx*lead,ground,neutral[2]+vz*remaining+dz*lead];
   // Corrections stop near landing; never snap a planted anchor.
   const change=sub(desired,s.target),d=len(change),cap=dt*1.4*(1-smooth((u-.65)/.35));
   if(d>1e-8)s.target=add(s.target,mul(change,Math.min(1,cap/d)));
   const turn=clamp(angle(p.face||0,s.face),-dt*3,dt*3);s.face+=turn;
   f.pos=blend(s.start,s.target,e);f.pos[1]+=Math.sin(Math.PI*u)*s.profile.lift*(s.identity?.lift??1);
   f.face+=angle(s.face,f.face)*smooth(u);
  }else{
   f.pos=blend(s.start,target,e);f.pos[1]+=Math.sin(Math.PI*u)*mix(.09,.21,smooth(speed/6));
   f.face+=angle(p.face||0,f.face)*smooth(u);
  }
  f.stance=false;
  if(u>=1){f.nativeSwing=null;f.pos[1]=ground;f.stance=true;f.face=p.face;}
 }else{
  f.pos[1]=ground;f.stance=true;f.start=null;
 }
 return f.stance;
}
// Stage 92: shared sampled clip library, upper-arm targets only. All
// targets still enter the same anatomical solver; no palette override.
function sampleClipArms(bank,name,phase){
 const clip=bank?.[name];
 if(!clip||!Array.isArray(clip.samples)||clip.samples.length<2)return null;
 const n=clip.samples.length-1,u=clamp(phase,0,1)*n,i=Math.min(n-1,Math.floor(u));
 return [0,1].map(side=>blend(clip.samples[i][side],clip.samples[i+1][side],u-i));
}
function nativeClipCue(p,phase,primary,duel){
 if(!p.nativeClipLibrary||!p.nativeBlend||p.role==='GK'||duel?.weight>.12)return null;
 let name,progress,weight;
 if(primary){
  if(primary.kind!=='shot'||!primary.strike)return null;
  name='shoot';
  const d=primary.deltaMs;
  progress=clamp((.38+d/1000)/1.3,0,1);
  // Exact ball contact and its near window keep procedural priority.
  weight=.30*primary.weight*smooth((Math.abs(d)-60)/110);
 }else if(p.speed>.45){
  name='run';progress=((phase%1)+1)%1;weight=.45*smooth((p.speed-.45)/1.5);
 }else{name='idle';progress=.5;weight=.25*(1-smooth(p.speed/.45));}
 const arms=sampleClipArms(p.nativeClipLibrary,name,progress);
 return arms&&weight>0?{name,arms,weight}:null;
}
// Stage 93: improve contact proxies, never the simulated ball or player.
const surfaceError=(point,center,radius=BALL_RADIUS)=>Math.abs(len(sub(point,center))-radius);
function sphereSurface(point,center,radius=BALL_RADIUS){
 const d=sub(point,center);return add(center,mul(len(d)>1e-8?unit(d):[1,0,0],radius));
}
function refineNativeContact(result,p,frame,anatomy,scale){
 const report=[],bodyKeys=['pelvis','neck','head','headTop','torsoBase','torsoMid','torsoUpper'];
 const exact=c=>c&&Math.abs(c.deltaMs)<=35&&c.weight>0;
 const center=c=>[c.ball.x,c.ball.y,c.ball.z];
 const addReport=(kind,before,after,correction)=>report.push({kind,before,after,correction});
 const foot=p.nativeContact;
 if(exact(foot)&&[0,1].includes(foot.foot)&&result.legs[foot.foot].nativeContact){
  const i=foot.foot,l=result.legs[i],c=center(foot),before=surfaceError(l.toe,c),w=foot.weight*smooth(1-Math.abs(foot.deltaMs)/35);
  let best=null,error=before;
  const offset=sub(l.toe,l.ankle),yaw=Math.atan2(offset[2],offset[0]);
  // Search a bounded boot yaw and re-solve only the contacting leg.
  // Opposite stance anchor, torso and actual player remain untouched.
  for(const turn of [0,-.18,.18,-.36,.36]){
   const f=yaw+turn*w,toeOffset=[Math.cos(f)*.20*scale,-.075*scale,Math.sin(f)*.20*scale];
   const desired=sphereSurface(l.toe,c),target=blend(l.ankle,sub(desired,toeOffset),w);
   if(len(sub(target,l.ankle))>.16)continue;
   const ik=boundedLimb(l.hip,target,anatomy.thigh,anatomy.shin,frame.forward,LIMITS.knee,LIMITS.hip,frame,i?1:-1);
   const toe=add(ik.end,toeOffset),e=surfaceError(toe,c);
   if(e<error-1e-7&&len(sub(ik.end,l.ankle))<=.16){best={ik,toe,target};error=e;}
  }
  const correction=best?len(sub(best.ik.end,l.ankle)):0;
  if(best){const {ik,toe,target}=best;Object.assign(l,{knee:ik.joint,ankle:ik.end,toe,target,bend:ik.bend,flex:ik.flex,abduct:ik.abduct,targetError:ik.error,footLift:ik.end[1]-GROUND*scale,stance:false,requestedStance:false});}
  addReport('foot',before,error,correction);
 }
 const keeper=p.nativeKeeper;
 if(exact(keeper)&&result.nativeKeeper&&keeper.kind!=='hold'){
  const c=center(keeper),w=keeper.weight*smooth(1-Math.abs(keeper.deltaMs)/35);
  for(let i=0;i<2;i++){
   const a=result.arms[i];if(!a.contactTarget)continue;
   const before=surfaceError(a.palm,c),desired=sphereSurface(a.palm,c),palm=blend(a.palm,desired,w);
   let target=sub(palm,mul(unit(sub(palm,a.shoulder)),anatomy.palm)),best=null,error=before;
   for(let j=0;j<4;j++){
    if(len(sub(target,a.wrist))>.16)break;
    const pole=add(mul(frame.forward,-.65),mul(frame.right,(i?1:-1)*.5));
    const ik=boundedLimb(a.shoulder,target,anatomy.upperArm,anatomy.forearm,pole,LIMITS.elbow,LIMITS.shoulder,frame,i?1:-1);
    const dir=unit(sub(palm,ik.end)),actual=add(ik.end,mul(dir,anatomy.palm)),e=surfaceError(actual,c);
    if(e<error-1e-7&&len(sub(ik.end,a.wrist))<=.16){best={ik,actual,dir,target:target.slice()};error=e;}
    target=add(target,mul(sub(palm,actual),.65));
   }
   const correction=best?len(sub(best.ik.end,a.wrist)):0;
   if(best){const {ik,actual,dir,target}=best;Object.assign(a,{elbow:ik.joint,wrist:ik.end,hand:add(ik.end,mul(dir,anatomy.hand)),palm:actual,target,bend:ik.bend,flex:ik.flex,abduct:ik.abduct,targetError:ik.error,contactTarget:palm,contactError:len(sub(actual,palm))});}
   addReport('palm',before,error,correction);
  }
 }
 const aerial=p.nativeAerial;
 if(exact(aerial)&&result.nativeAerial){
  const c=center(aerial),radius=BALL_RADIUS+.10*scale,before=surfaceError(result.head,c,radius);
  let best=0,error=before;
  // Airborne-only vertical correction. Keep all limbs rigidly translated;
  // no grounded player or stance foot may be lifted for a cosmetic contact.
  if(result.nativeAerial.jump>.02&&result.legs.every(l=>!l.stance)){
   const w=aerial.weight*smooth(1-Math.abs(aerial.deltaMs)/35);
   for(const dy of [-.08,-.04,.04,.08].map(v=>v*w)){
    if(result.nativeAerial.jump+dy<0||result.nativeAerial.jump+dy>.44||result.legs.some(l=>l.toe[1]+dy<0))continue;
    const e=surfaceError(add(result.head,[0,dy,0]),c,radius);
    if(e<error-1e-7){best=dy;error=e;}
   }
   if(best){
    for(const key of bodyKeys)result[key][1]+=best;
    for(const l of result.legs){for(const key of ['hip','knee','ankle','toe','target'])l[key][1]+=best;l.footLift+=best;}
    for(const a of result.arms)for(const key of ['shoulder','elbow','wrist','hand','palm','target'])a[key][1]+=best;
    result.nativeAerial.jump+=best;
   }
  }
  addReport('head',before,error,Math.abs(best));
 }
 if(report.length)result.nativeContactPrecision=report;
 return result;
}
function pose(p,dt=1/60){
 const anatomy=anatomyFor(p),bodyScale=anatomy.height/ANATOMY.height,ground=GROUND*bodyScale;
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
 const act=p.action||'idle',special=['pass','shoot','tackle','dive','catch','catch-ready','celebrate','protest','receive','throw','header'].includes(act)&&p.actionClock>0;
 // Stage 82: procedural strike gesture driven by an accepted contact.
 const recorded=p.nativeContact;
 const gesture=!special&&recorded?.strike&&recorded.weight>0&&[0,1].includes(recorded.foot)?recorded:null;
 const profile=gesture?.strike.shape;
 const gestureSide=gesture?(gesture.foot===0?-1:1):0;
 const gesturePower=gesture?clamp(gesture.strike.power,0,1):0;
 const gestureWeight=gesture?clamp(gesture.weight,0,1):0;
 // Stage 83: only an accepted low-ball control/trap event can drive these poses.
 const control=!special&&!gesture&&recorded?.control&&recorded.weight>0&&[0,1].includes(recorded.foot)?recorded:null;
 const controlShape=control?.control.shape,controlSide=control?(control.foot===0?-1:1):0;
 const controlWeight=control?clamp(control.weight,0,1):0;
 const controlSkill=control?clamp(control.control.skill,0,1):.5;
 const controlPressure=control?clamp(control.control.pressure,0,1):0;
 const controlLateral=control?clamp(control.control.lateral,-1,1):0;
 // Stage 84: directional reaction only to a recorded native collision.
 const duel=!special&&!gesture&&p.nativeDuel&&p.nativeDuel.weight>0?p.nativeDuel:null;
 const duelWeight=duel?clamp(duel.weight*(1-.45*duel.balance),0,1)*(control?.weight>0?.55:1):0;
 const duelForward=duel?clamp(duel.direction.x*fx+duel.direction.z*fz,-1,1):0;
 const duelLateral=duel?clamp(-duel.direction.x*fz+duel.direction.z*fx,-1,1):0;
 const duelDrop=duelWeight*(duel?.kind==='bump'?.035:.105);
 // Contact-specific tackle gesture, and a bounded trip recovery. The
 // pose never moves the simulated root or declares a successful steal.
 const tackleCue=!special&&!gesture&&!control&&recorded?.tackle&&recorded.weight>0?recorded:null;
 const tackleW=tackleCue?clamp(tackleCue.weight,0,1):0;
 const slideW=tackleCue?.tackle.sliding?tackleW:0;
 const fallAge=duel?.fall&&!tackleCue?duel.age:0;
 const fallW=duel?.fall&&!tackleCue?smooth(fallAge/140)*(1-smooth((fallAge-250)/650)):0;
 const fallDrop=fallW*.34;
 // Stage 86: native GK events are independent of the legacy Match actions.
 const keeper=!special&&p.role==='GK'&&p.nativeKeeper?.weight>0?p.nativeKeeper:null;
 const keeperW=keeper?clamp(keeper.weight,0,1):0;
 const keeperLow=keeper?clamp((1.1-keeper.ball.y)/1.1,0,1)*keeperW:0;
 const keeperSide=keeper?clamp(keeper.lateral/1.2,-1,1)*keeperW:0;
 const keeperHigh=keeper?clamp((keeper.ball.y-1.5)/.9,0,1)*keeperW:0;
 // Stage 87: a recorded head contact, never a guessed header from height.
 const aerial=!special&&!gesture&&!control&&!tackleCue&&!keeper&&p.nativeAerial?.weight>0?p.nativeAerial:null;
 const aerialW=aerial?clamp(aerial.weight,0,1):0;
 const aerialJump=aerial?clamp((aerial.ball.y-1.85)*.82,0,.36)*aerialW:0;
 const aerialCrouch=aerial?clamp((1.77-aerial.ball.y)*.30,0,.24)*aerialW:0;
 const aerialLanding=aerial&&aerial.deltaMs>90?Math.sin(Math.PI*clamp((aerial.deltaMs-90)/270,0,1))*.055:0;
 const nativePlant=p.nativeFootPlant===true&&!special&&!(p.footTouch>0)&&!(p.feintClock>0)&&!(p.feintResponseClock>0);
 // Profile selection is replay-local and uses recorded velocity, acceleration
 // and facing change. Contact protection remains in the existing pose layer.
 if(p.nativeMotionMatch===true&&nativePlant){
  const vx=Number.isFinite(p.vx)?p.vx:0,vz=Number.isFinite(p.vz)?p.vz:0;
  const c=p.nativeBodyBalance,brake=c?.valid?Math.max(0,-(c.ax*vx+c.az*vz)/Math.max(.5,speed)):0;
  const turn=Math.abs(yaw)/Math.max(dt,.001);
  st.motionMatch=matchNativeStep({forward:vx*fx+vz*fz,lateral:-vx*fz+vz*fx,brake,turn},st.motionMatch?.profile.id);
  st.motionMatch.identity=motionIdentityFactors(p.nativeMotionIdentity,st.motionMatch.profile.id);
 }else st.motionMatch=null;
 const selected=st.motionMatch?.profile;
 const identity=st.motionMatch?.identity;
 const stride=selected?selected.stride*(identity?.stride??1):(nativePlant?mix(.72,2.05,smooth(speed/7)):mix(1.0,2.2,smooth(speed/6)))*(1-defensive*.22),
 duty=selected?clamp(selected.duty+(identity?.duty??0),.32,.70):nativePlant?clamp(mix(.62,.34,smooth(speed/7))+defensive*.05,.34,.67):clamp(mix(.55,.20,smooth(speed/6))+defensive*.04,.20,.60);
 st.phase+=(travel/stride)+(speed<.3?Math.abs(yaw)*.12:0);
 // These cues read actual Match decisions/touches. They only affect this rig
 // and never move a simulated player, defender or the ball.
 const activeContact=special;
 const feintClock=Number.isFinite(p.feintClock)?clamp(p.feintClock,0,.35):0;
 const feintU=1-feintClock/.35,feintWeight=!activeContact&&feintClock>0?Math.sin(Math.PI*feintU):0;
 const feintSide=(p.feintSign??1)>=0?1:-1;
 // Only an accepted physical touch generates a skill cue. Existing touch
 // anchors, planted-foot IK and kick priority stay authoritative.
 const skillWeight=!activeContact&&p.footTouch>0?Math.sin(clamp(p.footTouch/.14,0,1)*Math.PI/2):0;
 const cutWeight=p.touchMode==='cut'?skillWeight:0,burstWeight=p.touchMode==='burst'?skillWeight:0;
 const cutSide=p.dribbleFoot===0?-1:1;
 const shieldTarget=!activeContact&&p.brainRole==='shield'?1:0;
 st.shieldWeight=mix(st.shieldWeight,shieldTarget,1-Math.exp(-dt*(shieldTarget?18:14)));
 const shieldWeight=clamp(st.shieldWeight,0,1);
 const feintFoot=feintSide>0?1:0;
 const misreadClock=Number.isFinite(p.feintResponseClock)?clamp(p.feintResponseClock,0,.19):0;
 const defenderMisread=!special&&misreadClock>0?Math.sin(Math.PI*.5*clamp(misreadClock/.19,0,1)):0;
 const defenderSide=(p.feintResponseSign??1)>=0?1:-1;
 const wallPassWeight=(act==='pass'||act==='shoot')&&p.actionClock>0&&p.wallPassClock>0&&p.wallPassFoot===p.kickFoot?1:0;
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
 // Opt-in native replay only. Use acceleration in the player's local axes,
 // not frame-to-frame facing alone (a stationary turn is not a running lean).
 const native=p.nativeBodyBalance;
 let nativePitch=0,nativeRoll=0,nativeDrop=0;
 if(native){
  const valid=native.valid===true&&!special&&Number.isFinite(native.ax)&&Number.isFinite(native.az);
  const forward=valid?native.ax*fx+native.az*fz:0;
  const lateral=valid?-native.ax*fz+native.az*fx:0;
  const moving=smooth(speed/2);
  const gain=1-Math.exp(-dt*10);
  st.nativePitch=mix(st.nativePitch||0,valid?clamp(forward*.016+moving*.035,-.10,.17):0,gain);
  st.nativeRoll=mix(st.nativeRoll||0,valid?clamp(lateral*.019,-.15,.15)*moving:0,gain);
  st.nativeDrop=mix(st.nativeDrop||0,valid?clamp(-forward*.005,0,.045)*moving:0,gain);
  if(!special){nativePitch=st.nativePitch;nativeRoll=st.nativeRoll;nativeDrop=st.nativeDrop;}
 }
 let hipHeight=anatomy.pelvisHeight+bounce-st.activity*.06-tackle*.16-gather-strike*.14-shieldWeight*.035-feintWeight*.012-defenderMisread*.015-nativeDrop-(gesture?(.025+.055*gesturePower)*gestureWeight:0)-(control?(controlShape.drop+.025*controlPressure)*controlWeight:0)-duelDrop-.12*tackleW-.20*slideW-fallDrop-.46*keeperLow-aerialCrouch-aerialLanding;
 const feint=feintWeight*feintSide*.12;
 const headerU=act==='header'&&p.actionClock>0?clamp((p.actionElapsed||0)/Math.max(.1,p.actionDuration||.5),0,1):0,headerWave=Math.sin(Math.PI*headerU);
 const headerBend=p.headerHeight?clamp((1.77-p.headerHeight)*headerWave,0,.8):0;
 const shieldSide=p.dribbleFoot===0?1:-1;
 let pitch=clamp((native?nativePitch:st.lean*2)+strike*.16+tackle*.48+headerBend+shieldWeight*.075+wallPassWeight*.045+burstWeight*.045+(gesture?profile.lean*gestureWeight*(.5+.5*gesturePower):0)+(control?(.035+.035*controlPressure)*controlWeight:0)+duelForward*duelWeight*.16+.10*tackleW+.20*fallW+.32*keeperLow-.08*keeperHigh+(aerial?clamp(aerial.forward*.18+(1.77-aerial.ball.y)*.24,-.08,.28)*aerialW:0),LIMITS.torso.flexMin,LIMITS.torso.flexMax),roll=clamp((native?nativeRoll:st.turn*.25)+feint+shieldWeight*shieldSide*.065+defenderMisread*defenderSide*.055 +cutWeight*cutSide*.045-(gesture?gestureSide*.07*gestureWeight:0)+(control?(.06*controlLateral-controlSide*.035*controlPressure)*controlWeight:0)+duelLateral*duelWeight*.19+duelLateral*fallW*.15+keeperSide*.16+(aerial?clamp(aerial.lateral*.15,-.12,.12)*aerialW:0),LIMITS.torso.rollMax*-1,LIMITS.torso.rollMax);
 const facing=[Math.cos(p.face||0),0,Math.sin(p.face||0)],right=[-facing[2],0,facing[0]];
 // Stage 88: filter pose targets in the player's local frame BEFORE IK.
 // Never interpolate already-solved bones or a planted world-space foot.
 const blended=p.nativeBlend===true&&!special;
 if(!blended)st.nativeBlend=null;
 const primary=recorded||aerial||keeper;
 const clipCue=!special?nativeClipCue(p,st.phase,primary,duel):null;
 const protect=primary?clamp(primary.weight,0,1):0;
 const gain=1-Math.exp(-dt*18);
 if(blended){
  const state=st.nativeBlend||(st.nativeBlend={torso:[hipHeight,pitch,roll],feet:[],arms:[]});
  const follow=mix(gain,1,protect*protect);
  state.torso=blend(state.torso,[hipHeight,pitch,roll],follow);
  [hipHeight,pitch,roll]=state.torso;
 }
 const localTarget=v=>{const d=sub(v,[p.x,0,p.z]);return [dot(d,facing),v[1],dot(d,right)];};
 const fromLocal=v=>world(p,v[0],v[2],v[1]);
 const filterTarget=(kind,i,v,bypass)=>{
  if(!blended)return v;
  const s=st.nativeBlend[kind],local=localTarget(v);
  const follow=bypass?1:gain;
  s[i]=s[i]?blend(s[i],local,follow):local;
  return bypass?v:fromLocal(s[i]);
 };
 const up=unit(add(add(mul(facing,Math.sin(pitch)),[0,Math.cos(pitch)*Math.cos(roll),0]),mul(right,Math.sin(roll))));
 const bodyForward=unit(sub(facing,mul(up,dot(facing,up)))),bodyRight=unit(cross(bodyForward,up)),bodyFrame={forward:bodyForward,up,right:bodyRight};
 const pelvis=world(p,strike*.04,0,hipHeight),torsoBase=add(pelvis,mul(up,anatomy.pelvis));
 const torsoMid=add(torsoBase,mul(up,anatomy.spine)),torsoUpper=add(torsoMid,mul(up,anatomy.chest));
 const neck=add(torsoUpper,mul(up,anatomy.neck)),headTop=add(neck,mul(up,anatomy.head)),head=blend(neck,headTop,.5);
 const legs=[],arms=[];
 if(kicking&&!['pass','shoot'].includes(st.lastAction)){st.support=st.feet[p.kickFoot===0?1:0].pos.slice();st.movingSupport=false;}
 for(let i=0;i<2;i++){
  const side=i?1:-1,f=st.feet[i],hip=add(pelvis,mul(bodyRight,side*anatomy.hipWidth/2));
  const arc=((st.phase+i*.5)%1+1)%1,locomoting=speed>.15||travel>.001;
  const neutral=world(p,.03,side*.15*bodyScale,ground),touch=[neutral[0]+moveX*stride*duty*.5,ground,neutral[2]+moveZ*stride*duty*.5];
  let stance=locomoting?arc<duty:true;
  const tooFar=Math.hypot(f.pos[0]-neutral[0],f.pos[2]-neutral[2])>.36||Math.abs(angle(p.face||0,f.face))>.65;
  if(nativePlant){
   stance=nativeStep(p,st,i,hip,neutral,arc,duty,speed,locomoting,dt);
  }else{
   if(f.nativeSwing){f.nativeSwing=null;f.start=null;f.stance=false;}
   f.nativeWanted=undefined;
  // Brake and pivot by taking a short replanting step, never by dragging a planted foot.
  if(!kicking&&!f.adjust&&(!locomoting&&tooFar||locomoting&&f.stance&&len(sub(f.pos,hip))>.88)){
   if(!st.feet[1-i].adjust){f.adjust=.0001;f.adjustDuration=locomoting?.08:.22;f.start=f.pos.slice();f.adjustTarget=(locomoting?touch:neutral).slice();f.stance=false;}
  }
  if(f.adjust){
   const adjustDuration=f.adjustDuration||.22;f.adjust=Math.min(adjustDuration,f.adjust+dt);const u=smooth(f.adjust/adjustDuration);
   f.pos=blend(f.start,f.adjustTarget,u);f.pos[1]+=Math.sin(u*Math.PI)*.13;stance=false;
   if(f.adjust>=adjustDuration){f.adjust=0;f.stance=true;f.face=p.face;stance=true;}
  }else if(stance){
   if(!f.stance){f.pos[1]=ground;f.face=p.face;}
   f.stance=true;f.start=null;
  }else{
   const cycleU=clamp((arc-duty)/(1-duty),0,1);
   if(f.stance||!f.start){f.start=f.pos.slice();f.swingStart=cycleU;f.swingTime=0;}
   f.swingTime=(f.swingTime||0)+dt;
   const u=smooth(Math.min(clamp((cycleU-(f.swingStart||0))/Math.max(.01,1-(f.swingStart||0)),0,1),f.swingTime/.16));f.pos=blend(f.start,touch,u);f.pos[1]=ground+Math.sin(u*Math.PI)*(.13+.12*sprint);f.face+=angle(p.face||0,f.face)*alpha;f.stance=false;
  }
  }
  let foot=f.pos.slice(),footFace=f.face;
  if(kicking){
   if(i===(p.kickFoot===0?0:1)){
    let target;
    if(contact<.43)target=world(p,mix(.03,-.30,smooth(contact/.43)),side*.18,mix(ground,.34,smooth(contact/.43)));
    else target=blend(world(p,-.30,side*.18,.34),kickAnkle(p),smooth((contact-.43)/.57));
    if(after>0){const peak=world(p,.64,side*.18,.36);target=after<.4?blend(kickAnkle(p),peak,smooth(after/.4)):blend(peak,neutral,smooth((after-.4)/.6));}
    // At contact use the exact IK target shared with the ball, without blend lag.
    foot=blend(foot,target,contact>.9?1:action);stance=false;
   }else if(p.kickMoving&&(contact<.72||after>.18)){
    // Keep stepping through a running strike; plant only around the contact window.
    st.movingSupport=false;
   }else {
    if(p.kickMoving&&!st.movingSupport){st.support=foot.slice();st.support[1]=ground;st.movingSupport=true;}
    foot=(st.support||neutral).slice();stance=true;
   }
   footFace=p.face;f.pos=foot.slice();f.stance=stance;f.face=footFace;
  }
  // Only the actual contact foot approaches Match's recorded ball position.
  // The opposite stance foot remains at its physical planted anchor.
  if(!kicking&&act!=='receive'&&p.footTouch>0&&p.touchPosition&&i===p.dribbleFoot){
   const w=Math.sin(clamp(p.footTouch/.14,0,1)*Math.PI/2)*.84;
   const target=[p.touchPosition.x-facing[0]*.24,ground,p.touchPosition.z-facing[2]*.24];
   foot=blend(foot,target,w);footFace=p.face;stance=false;
  }
  // The feint is a fake step, not a second ball impulse. Preserve the
  // unselected support foot and solve the lifted ankle through bounded IK.
  if(!kicking&&feintWeight>.001&&i===feintFoot&&p.footTouch<=0){
   const stepOver=p.feintStyle==='step-over';
   // Swing around the ball-side corridor without adding a second impulse;
   // the support boot stays under the same bounded leg solver.
   const target=stepOver?world(p,.21+.19*Math.sin(feintU*Math.PI),side*mix(.12,.32,smooth(feintU)),ground+.12):world(p,.11,side*.24,ground+.075);
   foot=blend(foot,target,feintWeight*.8);footFace=p.face;stance=false;
  }
  // A deceived defender takes a visible preparatory shuffle in the same
  // direction as the short physical steering response (no fake ball touch).
  if(!kicking&&defenderMisread>.001&&side===defenderSide&&p.footTouch<=0){
   const target=world(p,.08,side*.22,ground+.06);
   foot=blend(foot,target,defenderMisread*.58);footFace=p.face;stance=false;
  }
  if(tackle>.01){foot=blend(foot,world(p,.50+side*.12,side*.33,.12),tackle);stance=false;}
  if(act==='receive'&&i===(p.kickFoot===0?0:1)){const cushion=Math.sin(Math.PI*clamp((p.actionElapsed||0)/Math.max(.01,p.actionDuration||.25),0,1));foot=blend(foot,world(p,.26,side*.18,.17),cushion*.65);stance=false;}
  // Only the recorded, known foot approaches the recorded ball point.
  // Never rotate the simulated actor, move the ball, or override special actions.
  const cue=p.nativeContact;
  const nativeContact=!special&&cue&&cue.foot===i&&cue.weight>0&&
    [cue.ball?.x,cue.ball?.y,cue.ball?.z,cue.impulse?.vx,cue.impulse?.vz,cue.weight].every(Number.isFinite)&&
    cue.ball.y>=0&&cue.ball.y<=.35&&Math.hypot(cue.ball.x-p.x,cue.ball.z-p.z)<=1.15;
  if(gesture&&i!==gesture.foot){
   // Keep existing planted support. Do not teleport an airborne foot.
   if(stance&&Math.abs(foot[1]-ground)<.001){
    f.nativeSwing=null;f.adjust=0;
   }
  }
  if(nativeContact){
   const v=Math.hypot(cue.impulse.vx,cue.impulse.vz);
   const nx=v>.1?cue.impulse.vx/v:facing[0],nz=v>.1?cue.impulse.vz/v:facing[2];
   footFace=p.face;
   // Toe is .20m ahead and .075m below ankle in the canonical rig.
   const target=[cue.ball.x-nx*BALL_RADIUS-facing[0]*.20*bodyScale,Math.max(ground,cue.ball.y+.075*bodyScale),cue.ball.z-nz*BALL_RADIUS-facing[2]*.20*bodyScale];
   if(gesture){
    const delta=cue.deltaMs,pre=delta<0;
    const progress=pre?clamp(-delta/profile.pre,0,1):clamp(delta/profile.post,0,1);
    // A continuous bell-shaped excursion is zero at contact and endpoints.
    const swingAmount=Math.sin(Math.PI*progress)*(.55+.45*gesturePower);
    const offset=(pre?-profile.back:profile.follow)*swingAmount;
    footFace=p.face-gestureSide*profile.turn*gestureWeight;
    const anchor=[cue.ball.x-nx*BALL_RADIUS-Math.cos(footFace)*.20*bodyScale,Math.max(ground,cue.ball.y+.075*bodyScale),cue.ball.z-nz*BALL_RADIUS-Math.sin(footFace)*.20*bodyScale];
    // After the exact contact, follow the kick direction rather than chase
    // the moving ball; the anchor is the recorded pre-impact position.
    const swingTarget=[anchor[0]+nx*offset,anchor[1]+profile.lift*swingAmount,anchor[2]+nz*offset];
    foot=blend(foot,swingTarget,gestureWeight);stance=false;
   }else if(tackleCue){
    const phase=clamp(Math.abs(cue.deltaMs)/(cue.deltaMs<0?150:180),0,1);
    const pulse=Math.sin(Math.PI*phase);
    const extension=(cue.deltaMs<0?-.10:.18)*(slideW>0?1.4:1)*pulse;
    foot=blend(foot,[target[0]+nx*extension,target[1]+.045*pulse,target[2]+nz*extension],tackleW);stance=false;
   }else if(control){
    const delta=cue.deltaMs,pre=delta<0;
    const phase=clamp(Math.abs(delta)/(pre?controlShape.pre:controlShape.post),0,1);
    const pulse=Math.sin(Math.PI*phase);
    // Stylized foot angle only; the engine does not report the boot surface.
    footFace=p.face-controlSide*controlShape.turn*controlWeight*(.5+.5*Math.abs(controlLateral));
    const anchor=[cue.ball.x-nx*BALL_RADIUS-Math.cos(footFace)*.20*bodyScale,Math.max(ground,cue.ball.y+.075*bodyScale),cue.ball.z-nz*BALL_RADIUS-Math.sin(footFace)*.20*bodyScale];
    let dx=nx,dz=nz;
    if(control.control.profile==='cushion'&&control.control.incoming){
     const incoming=control.control.incoming,len=Math.hypot(incoming.vx,incoming.vz);
     if(len>.1){dx=incoming.vx/len;dz=incoming.vz/len;}
    }
    const amplitude=pulse*(1-.25*controlSkill);
    const reach=pre?-controlShape.reach:controlShape.recover;
    const desired=[anchor[0]+dx*reach*amplitude,anchor[1]+controlShape.lift*pulse,anchor[2]+dz*reach*amplitude];
    foot=blend(foot,desired,controlWeight);stance=false;
   }else{foot=blend(foot,target,clamp(cue.weight,0,1));stance=false;}
  }
  if(fallW>0&&!nativeContact){
   const recovery=world(p,.08+(i?1:-1)*duelForward*.14,side*(.15+.13*fallW),ground);
   foot=blend(foot,recovery,fallW*.7);stance=false;
  }
  // The contact foot and planted foot remain authoritative. Only a free
  // swing target is filtered, and the existing anatomical solver follows.
  foot=filterTarget('feet',i,foot,stance||nativeContact||aerialW>0);
  const requestedStance=stance,requestedFoot=foot.slice(),legIK=boundedLimb(hip,foot,anatomy.thigh,anatomy.shin,facing,LIMITS.knee,LIMITS.hip,bodyFrame,side);
  foot=legIK.end;if(legIK.error>1e-5)stance=false;
  const toe=add(foot,[Math.cos(footFace)*.20*bodyScale,-.075*bodyScale,Math.sin(footFace)*.20*bodyScale]);
  legs.push({hip,knee:legIK.joint,ankle:foot,toe,stance,requestedStance,nativeContact:!!nativeContact,...(p.nativeMotionMatch===true?{stepProfile:f.nativeSwing?.profile?.id??null}:{}),footLift:foot[1]-ground,bend:legIK.bend,flex:legIK.flex,abduct:legIK.abduct,target:requestedFoot,targetError:legIK.error});
  const shoulder=add(torsoUpper,mul(bodyRight,side*anatomy.shoulderWidth/2));
  const swing=-Math.sin(st.phase*2*Math.PI+i*Math.PI)*st.activity*(.22+.12*sprint)*(identity?.arm??1);
  let wrist=world(p,swing+kick*(i===1?-.35:.24),side*(.255+kick*.10),.94+bounce+celebrating*.93+protest*.30-tackle*.17-gather);
  if(gesture){
   const counter=side===gestureSide?-.55:1;
   const target=world(p,counter*profile.arm*(.6+.4*gesturePower),side*(.27+profile.arm*.35),1.06+profile.arm*.22);
   wrist=blend(wrist,target,gestureWeight*.8);
  }
  if(control){
   const guard=controlPressure*.13;
   const target=world(p,side===controlSide?-.06:.10,side*(.27+controlShape.arm*.2+guard),1.02+guard);
   wrist=blend(wrist,target,controlWeight*(.45+.30*controlPressure));
  }
  if(tackleW>0||fallW>0){
   const target=world(p,.12+fallW*.22,side*(.29+slideW*.08),Math.max(.45,1.02-fallW*.45-slideW*.20));
   wrist=blend(wrist,target,Math.max(tackleW*.65,fallW*.8));
  }
  if(aerial){
   const target=world(p,-.10,side*(aerial.contested?.39:.31),1.22);
   wrist=blend(wrist,target,aerialW*.78);
  }
  if(keeper){
   // The unknown limb case is a stylized ready pose, not a claimed glove hit.
   const guard=world(p,.24,side*.28,1.10-.25*keeperLow+.25*keeperHigh);
   wrist=blend(wrist,guard,keeperW*.75);
  }
  if(duelWeight>0){
   // Tuck elbows near an opponent; extend the opposite arm for balance.
   const away=side*duelLateral>0;
   const target=world(p,.08+duelForward*.12,side*(away?.34:.20),1.05+(away?.15:.02));
   wrist=blend(wrist,target,duelWeight*(duel.possession?.9:.75));
  }
  if(cutWeight>.001||burstWeight>.001){
   const target=world(p,cutWeight>0?(side===cutSide?-.14:.18):-.18,side*.29,1.02);
   wrist=blend(wrist,target,Math.max(cutWeight*.5,burstWeight*.4));
  }
  if(feintWeight>.001){
   // Shoulder counter-rotation makes the defender-facing fake visible.
   const target=world(p,side===feintSide?-.10:.18,side*.26,1.02);
   wrist=blend(wrist,target,feintWeight*.75);
  }
  if(defenderMisread>.001){
   const target=world(p,side===defenderSide?-.08:.18,side*.22,1.08);
   wrist=blend(wrist,target,defenderMisread*.55);
  }
  if(wallPassWeight>.001){
   // The existing kick time/contact anchors remain authoritative; only
   // counterbalance the non-kicking arm during a verified one-touch return.
   const kickingSide=p.kickFoot===0?-1:1;
   if(side!==kickingSide)wrist=blend(wrist,world(p,-.16,side*.26,1.21),wallPassWeight*.68);
  }
  if(shieldWeight>.001){
   // Protect the ball-side channel with bent elbows; target remains within
   // the same licensed skeleton's shoulder/elbow/forearm constraints.
   const target=world(p,side===shieldSide?.24:.10,side*.19,1.09);
   wrist=blend(wrist,target,shieldWeight*.92);
  }
  if(act==='throw'&&p.actionClock>0){const u=smooth((p.actionElapsed||0)/Math.max(.1,p.contactTime||.55));wrist=blend(wrist,world(p,mix(-.06,.4,u),side*.12,1.95),action);}
  if(clipCue){
   const [f,u,s]=clipCue.arms[i];
   const desired=add(shoulder,add(add(mul(bodyForward,f*bodyScale),mul(up,u*bodyScale)),mul(bodyRight,s*bodyScale)));
   wrist=blend(wrist,desired,clipCue.weight);
  }
  wrist=filterTarget('arms',i,wrist,!!keeper&&keeperW>.75);
  arms.push({shoulder,target:wrist});
 }
 let result={pelvis,neck,head,headTop,torsoBase,torsoMid,torsoUpper,legs,arms,activity:st.activity,sprint,kick,tackle,diving,celebrating,protest,face:p.face,action:act,weight:action,turn:st.turn,feintWeight,shieldWeight,defenderMisread,wallPassWeight,cutWeight,burstWeight};
 if(gesture)result.nativeStrike={profile:gesture.strike.profile,foot:gesture.foot,deltaMs:gesture.deltaMs,power:gesturePower,weight:gestureWeight};
 if(control)result.nativeControl={profile:control.control.profile,foot:control.foot,deltaMs:control.deltaMs,skill:controlSkill,pressure:controlPressure,weight:controlWeight,contextRecorded:control.control.contextRecorded};
 if(duel)result.nativeDuel={kind:duel.kind,opponentId:duel.opponentId,age:duel.age,weight:duelWeight,drop:duelDrop,forward:duelForward,lateral:duelLateral,tripType:duel.tripType};
 if(tackleCue)result.nativeTackle={kind:tackleCue.kind,foot:tackleCue.foot,weight:tackleW,sliding:tackleCue.tackle.sliding};
 if(duel?.fall)result.nativeRecovery={age:fallAge,weight:fallW,drop:fallDrop};
 if(keeper)result.nativeKeeper={kind:keeper.kind,profile:keeper.profile,hand:keeper.hand,weight:keeperW,held:keeper.held,targets:0,meanPalmError:null};
 if(aerial)result.nativeAerial={profile:aerial.profile,kind:aerial.kind,weight:aerialW,jump:aerialJump,landing:aerialLanding,contested:aerial.contested,headError:null};
 if(st.motionMatch)result.nativeMotionMatch={profile:st.motionMatch.profile.id,cost:st.motionMatch.cost,steps:st.feet.map(f=>f.nativeSwing?.profile?.id??null)};
 if(clipCue)result.nativeClip={name:clipCue.name,weight:clipCue.weight,source:'project-blender-baked'};
 if(p.nativeAnatomy)result.nativeAnatomy={height:p.nativeAnatomy.height,scale:bodyScale,preferredFoot:p.nativeAnatomy.preferredFoot};
 if(identity)result.nativeMotionIdentity={...identity,strideMetres:stride,stanceRatio:duty,freshness:p.nativeMotionIdentity.freshness};
 if(blended)result.nativeBlend={gain,contactProtection:protect,primary:recorded?.kind||aerial?.kind||keeper?.kind||null,hipHeight,pitch,roll};
 if(native)result.nativeBalance={pitch:nativePitch,roll:nativeRoll,drop:nativeDrop};
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
  const maxReach=Math.sqrt(anatomy.upperArm**2+anatomy.forearm**2+2*anatomy.upperArm*anatomy.forearm*Math.cos(LIMITS.elbow.min))+anatomy.palm;
  for(let iteration=0;iteration<12;iteration++){
   let correction=[0,0,0];
   for(let i=0;i<2;i++){
    const shoulder=add(arms[i].shoulder,shift),target=contactTargets[i],delta=sub(target,shoulder),distance=len(delta);
    if(distance>maxReach)correction=add(correction,mul(unit(delta),(distance-maxReach)*.65));
    else {
     const wrist=sub(target,mul(unit(delta),anatomy.palm)),pole=add(mul(frame.forward,-.65),mul(frame.right,(i?1:-1)*.5));
     const ik=boundedLimb(shoulder,wrist,anatomy.upperArm,anatomy.forearm,pole,LIMITS.elbow,LIMITS.shoulder,frame,i?1:-1),palm=add(ik.end,mul(unit(sub(target,ik.end)),anatomy.palm));
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
   const ik=boundedLimb(leg.hip,leg.target,anatomy.thigh,anatomy.shin,frame.forward,LIMITS.knee,LIMITS.hip,frame,i?1:-1);
   leg.knee=ik.joint;leg.ankle=ik.end;leg.toe=add(ik.end,sub(oldToe,oldAnkle));leg.bend=ik.bend;leg.flex=ik.flex;leg.abduct=ik.abduct;leg.targetError=ik.error;if(ik.error>1e-5)leg.stance=false;
  }
 }
 // For the native replay, resolve each known hand independently. Catch/hold
 // uses two stylized palms; unknown parry hand only receives a ready pose.
 let nativePalmErrors=[];
 for(let i=0;i<2;i++){
  const arm=arms[i],side=i?1:-1;
  let palm=contactTargets&&contactTargets[i];
  if(keeper&&(keeper.kind!=='parry'||keeper.hand===i)){
   const half=keeper.kind==='parry'?0:BALL_RADIUS*.72;
   const goal=[keeper.ball.x-right[0]*side*half,keeper.ball.y,keeper.ball.z-right[2]*side*half];
   // Offset to the incoming-facing ball surface, not the center.
   const direction=unit(sub(goal,arm.shoulder));
   const target=sub(goal,mul(direction,BALL_RADIUS*.75));
   const current=add(arm.target,mul(unit(sub(arm.target,arm.shoulder)),anatomy.palm));
   palm=blend(current,target,keeperW);
  }
  const wristTarget=palm?sub(palm,mul(unit(sub(palm,arm.shoulder)),anatomy.palm)):arm.target;
  const pole=add(mul(frame.forward,-.65),mul(frame.right,side*.5));
  const ik=boundedLimb(arm.shoulder,wristTarget,anatomy.upperArm,anatomy.forearm,pole,LIMITS.elbow,LIMITS.shoulder,frame,side);
  const handDirection=palm?unit(sub(palm,ik.end)):unit(sub(ik.end,ik.joint));
  arms[i]={shoulder:arm.shoulder,elbow:ik.joint,wrist:ik.end,hand:add(ik.end,mul(handDirection,anatomy.hand)),palm:add(ik.end,mul(handDirection,anatomy.palm)),bend:ik.bend,flex:ik.flex,abduct:ik.abduct,target:wristTarget,targetError:ik.error};
  if(palm){arms[i].contactTarget=palm.slice();arms[i].contactError=len(sub(arms[i].palm,palm));if(keeper)nativePalmErrors.push(arms[i].contactError);}
 }
 result.presentationOffset=shift;result.contactError=contactTargets?Math.max(...arms.map(a=>a.contactError)):0;
 if(keeper&&nativePalmErrors.length){result.nativeKeeper.targets=nativePalmErrors.length;result.nativeKeeper.meanPalmError=nativePalmErrors.reduce((a,b)=>a+b,0)/nativePalmErrors.length;}
 if(aerial){
  // Translate the complete solved skeleton, not the simulated actor.
  // Whole-rig lift preserves each solved bone length.
  for(const key of bodyKeys)result[key][1]+=aerialJump;
  for(const leg of legs){for(const key of ['hip','knee','ankle','toe','target'])leg[key][1]+=aerialJump;if(aerialJump>.001)leg.stance=false;}
  for(const arm of arms)for(const key of ['shoulder','elbow','wrist','hand','palm','target'])arm[key][1]+=aerialJump;
  const center=[aerial.ball.x,aerial.ball.y,aerial.ball.z];
  // Head center is a proxy, not the rendered forehead or collision mesh.
  result.nativeAerial.headError=Math.abs(len(sub(result.head,center))-(BALL_RADIUS+.10));
 }
 if(headerWave>0){
  const jump=headerWave*(p.headerHeight?clamp((p.headerHeight-1.77)/.905,0,.33):.23);
  for(const key of bodyKeys)result[key][1]+=jump;
  for(const leg of legs){for(const key of ['hip','knee','ankle','toe','target'])leg[key][1]+=jump;leg.stance=false;}
  for(const arm of arms)for(const key of ['shoulder','elbow','wrist','hand','palm','target'])arm[key][1]+=jump;
 }
 if(p.nativeContactPrecision===true&&!special)refineNativeContact(result,p,frame,anatomy,bodyScale);
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
const API={surfaceError,sphereSurface,refineNativeContact,sampleClipArms,nativeClipCue,anatomyFor,bodyScaleFor,motionIdentityFactors,matchNativeStep,pose,update:pose,getPose:p=>getState(p).pose||pose(p,0),reset,solveKnee,solveLimb,boneFrames,ANATOMY,LIMITS,kickContact,kickAnkle,getDive,catchHands,saveHands,BALL_RADIUS};
if(typeof module!=='undefined'&&module.exports)module.exports=API;
global.TribunHumanoidRig=API;
})(typeof window!=='undefined'?window:globalThis);
