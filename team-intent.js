/* Shared, deterministic task lifetimes. Physical movement remains in Match.move. */
(function(root){
'use strict';
const distance=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z),finitePoint=p=>Number.isFinite(p?.x)&&Number.isFinite(p?.z);
const attack=new Set(['support','build-support','return-support','between-lines','penetration','channel-run','give-go','overlap','wide-support','inside-support','box-run','cutback-support','receive-run','dribble','receive','shield']);
const defence=new Set(['press','counterpress','intercept','mark','track-run','cover','screen','recovery-screen','recovery','block','delay']);
const moving=new Set(['press','mark','receive','block','recover','control']);
const limits={support:[.50,1.8,.32],run:[.70,3.2,.36],press:[.45,1.4,.32],mark:[.60,2.1,.36],cover:[.50,1.8,.32],recover:[.45,1.8,.28],carry:[.45,1.2,.28],receive:[0,2.4,0],block:[0,.8,0],control:[0,1.2,0],shape:[.25,1.2,.24]};
function phaseFamily(phase){return ['win','possession','gain','in-possession'].includes(phase)?'attack':['loss','defence','defense','out-of-possession'].includes(phase)?'defence':null;}
function purposeFor(state){
 if(['support','build-support','return-support','between-lines'].includes(state))return 'support';
 if(['penetration','channel-run','give-go','overlap','wide-support','inside-support','box-run','cutback-support'].includes(state))return 'run';
 if(['press','counterpress','intercept','loose-ball'].includes(state))return 'press';
 if(['mark','track-run'].includes(state))return 'mark';
 if(['cover','screen','recovery-screen','delay'].includes(state))return 'cover';
 if(state==='recovery')return 'recover';if(state==='receive-run')return 'receive';
 if(['dribble','shield'].includes(state))return 'carry';if(state==='receive')return 'control';if(state==='block')return 'block';return 'shape';
}
function now(c){return Number.isFinite(c?.time)?c.time:0;}
function epoch(c){return c.attackEpoch??c.phaseEpoch??null;}
function player(c,id){if(id===null||id===undefined||!c.players)return null;return c.players instanceof Map?c.players.get(id):c.players.find?.(p=>p.id===id);}
function unavailable(c,id){return id!==null&&id!==undefined&&!!c.players&&(!player(c,id)||player(c,id).active===false);}
function identity(a,b){return a.purpose===b.purpose&&(moving.has(a.purpose)||a.state===b.state)&&a.partnerId===b.partnerId&&a.focusId===b.focusId;}
function trace(p,c,from,to,reason){
 const entry={time:now(c),reason,from:from?.purpose??null,to:to?.purpose??null,fromState:from?.state??null,toState:to?.state??null,phase:c.phase??null,partnerId:to?.partnerId??from?.partnerId??null,focusId:to?.focusId??from?.focusId??null};
 const history=Array.isArray(p.taskHistory)?p.taskHistory.slice():[];history.push(entry);if(history.length>24)history.splice(0,history.length-24);p.taskHistory=history;
 if(typeof c.trace==='function')c.trace({...entry},p);
}
function invalidReason(p,t,c){
 if(!t||t.version!==1||!finitePoint(t))return 'invalid';
 if(p.active===false)return 'inactive';
 if(t.actorRosterId!=null&&t.actorRosterId!==(p.rosterId??null))return 'substitution';
 const family=phaseFamily(c.phase);if(family&&t.family&&family!==t.family)return family==='defence'?'loss':'phase';
 if(epoch(c)!==null&&t.epoch!==null&&epoch(c)!==t.epoch)return 'epoch';
 if(unavailable(c,t.partnerId))return 'partner';if(unavailable(c,t.focusId))return 'focus';
 if(c.players&&t.partnerRosterId!=null&&player(c,t.partnerId)?.rosterId!==t.partnerRosterId)return 'partner';
 if(c.players&&t.focusRosterId!=null&&player(c,t.focusId)?.rosterId!==t.focusRosterId)return 'focus';
 if(c.partnerValid===false)return 'partner';if(c.invalid===true)return 'invalid';
 if(c.safe===false||typeof c.safe==='function'&&c.safe(p,t,c)===false)return 'safety';
 if(typeof c.invalid==='function'&&c.invalid(p,t,c))return 'invalid';
 if(now(c)>=t.expiresAt)return 'expiry';return null;
}
function clear(p,reason='invalid',c={}){if(p.task){trace(p,c,p.task,null,reason);p.task=null;}return null;}
function candidate(p,q,c){
 const purpose=q.purpose||purposeFor(q.state),family=phaseFamily(c.phase)||(attack.has(q.state)?'attack':defence.has(q.state)?'defence':null);
 return {version:1,purpose,state:q.state||'shape',family,phase:c.phase??null,phaseEpoch:c.phaseEpoch??null,epoch:epoch(c),partnerId:q.partnerId??null,focusId:q.focusId??null,actorRosterId:p.rosterId??null,partnerRosterId:player(c,q.partnerId)?.rosterId??null,focusRosterId:player(c,q.focusId)?.rosterId??null,x:q.x,z:q.z,pace:Number.isFinite(q.pace)?q.pace:.9,priority:Number.isFinite(q.priority)?q.priority:0};
}
function point(q,t){return {...q,x:t.x,z:t.z,pace:t.pace,state:t.state,purpose:t.purpose,priority:t.priority,partnerId:t.partnerId,focusId:t.focusId};}
function adopt(p,q,c,reason){
 const old=p.task,t=candidate(p,q,c),time=now(c),[min,max]=limits[t.purpose]||limits.shape;
 Object.assign(t,{since:time,commitUntil:time+min,expiresAt:time+max,lastProgressAt:time,lastDistance:distance(p,t),arrivedAt:null,challenge:null,reason});
 p.task=t;trace(p,c,old,t,reason);return point(q,t);
}
function reserved(p,c={},allowedPurposes=[]){
 const t=p.task;if(invalidReason(p,t,c))return false;
 if(allowedPurposes.includes(t.purpose)||allowedPurposes.includes(t.state))return false;
 return now(c)<t.commitUntil||t.arrivedAt!==null&&t.purpose==='support'&&now(c)<Math.min(t.expiresAt,t.arrivedAt+.45);
}
function resolve(p,q,c={}){
 const time=now(c),old=p.task?{...p.task,challenge:p.task.challenge?{...p.task.challenge}:null}:null;
 // Forecast actors may be shallow copies; never mutate a shared task record.
 if(old)p.task=old;
 if(p.active===false){clear(p,'inactive',c);return {...q,x:p.x,z:p.z,pace:0,state:'inactive'};}
 if(!finitePoint(q)){
  if(old&&!invalidReason(p,old,c)){old.reason='proposal-invalid';return point(q||{},old);}
  clear(p,'invalid',c);return {x:Number.isFinite(p.x)?p.x:0,z:Number.isFinite(p.z)?p.z:0,pace:0,state:'shape'};
 }
 const next=candidate(p,q,c),invalid=old?invalidReason(p,old,c):null;
 if(!old||invalid)return adopt(p,q,c,invalid||'start');
 const same=identity(old,next),urgent=q.urgent===true||c.directThreat===true||c.ballContact===true||next.purpose==='block'||next.purpose==='receive'&&(c.flightTargetId===p.id||c.kickTargetId===p.id||q.state==='receive-run')||next.purpose==='control'&&c.ownerId===p.id;
 if(c.forceReason)return adopt(p,q,c,c.forceReason);
 if(urgent&&!same)return adopt(p,q,c,'urgent');
 const remaining=distance(p,old);
 if(remaining<old.lastDistance-.12){old.lastDistance=remaining;old.lastProgressAt=time;}
 if(remaining<=.85&&old.arrivedAt===null)old.arrivedAt=time;
 if(old.phase!==c.phase&&phaseFamily(c.phase)===old.family){old.phase=c.phase;old.phaseEpoch=c.phaseEpoch??null;trace(p,c,old,old,'phase-continue');}
 const shifted=distance(old,next)>1.35;
 // Commitment protects the objective, not the current effort or urgency.
 // A different task must not smuggle its operational inputs onto the old one.
 if(same){old.pace=next.pace;old.priority=next.priority;}
 if(same&&moving.has(old.purpose)){
  Object.assign(old,{x:next.x,z:next.z,pace:next.pace,state:next.state,reason:'track',challenge:null});return point(q,old);
 }
 if(same&&!shifted){old.reason='continue';old.challenge=null;return point(q,old);}
 if(urgent&&same){
  const from={...old};Object.assign(old,{x:next.x,z:next.z,pace:next.pace,lastProgressAt:time,lastDistance:distance(p,next),arrivedAt:null,challenge:null,reason:'urgent-target'});
  trace(p,c,from,old,'urgent-target');return point(q,old);
 }
 // Reaching an open angle starts a bounded chance to use the connection.
 // Ordinary replanning cannot end that chance before its readiness window.
 if(old.purpose==='support'&&old.arrivedAt!==null&&c.complete!==true&&time<Math.min(old.expiresAt,old.arrivedAt+.45)){old.reason='ready-window';return point(q,old);}
 const complete=c.complete===true||old.arrivedAt!==null&&time>=Math.max(old.commitUntil,old.arrivedAt+(old.purpose==='support'?.45:0));
 if(complete)return adopt(p,q,c,'arrived');
 if(remaining>1.2&&time-old.lastProgressAt>=1.2)return adopt(p,q,c,'stalled');
 if(next.priority>=old.priority+20)return adopt(p,q,c,'priority');
 const previous=old.challenge,matching=previous&&identity(previous,next)&&distance(previous,next)<1.5;
 old.challenge=matching?previous:{...next,since:time};
 if(time<old.commitUntil){old.reason='commitment';return point(q,old);}
 const confirm=(limits[old.purpose]||limits.shape)[2];
 if(time-old.challenge.since<confirm-1e-7){old.reason='candidate-pending';return point(q,old);}
 if(same){
  const from={...old};Object.assign(old,{x:next.x,z:next.z,pace:next.pace,lastProgressAt:time,lastDistance:distance(p,next),arrivedAt:null,challenge:null,reason:'target-update'});
  trace(p,c,from,old,'target-update');return point(q,old);
 }
 return adopt(p,q,c,next.priority>old.priority?'priority':'replan');
}
const api={resolve,reserved,clear,purposeFor,phaseFamily};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.TribunIntent=api;
})(typeof window!=='undefined'?window:globalThis);
