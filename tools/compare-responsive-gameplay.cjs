'use strict';
const {Match}=require('../football-sim'),D=require('../attack-diagnostics');
for(const seed of [113,211,337]){
 for(const pilot of [false,true]){
  const m=new Match({seed,individualAI:true,gameplayResponsiveness:pilot,tactics:{playstyle:'possession',passing:'short'},awayTactics:{playstyle:'counter',passing:'direct'},rules:{periodSeconds:150,halftimeSeconds:8,addedTime:false}});
  const o=D.attach(m);let steps=0,maxGap=0,open=0;
  while(!m.done&&steps<24000){o.step(1/60);steps++;if(m.owner&&!m.owner.holdingBall){maxGap=Math.max(maxGap,Math.hypot(m.owner.x-m.ball.x,m.owner.z-m.ball.z));open++;}}
  if(!m.done)throw Error('full match not completed');
  const summary=o.summary();
  console.log(JSON.stringify({seed,pilot,score:m.score,shots:m.shots,passes:m.passes,completed:m.completed,steps,maxGap,open,stages:summary.teams.map(t=>t.stageCounts),telemetry:Object.fromEntries(Object.entries(m.telemetry).filter(([k])=>/responsive|looseBalls|turnovers|dribbleTouches|touchDeferrals/.test(k)))}));
 }
}
