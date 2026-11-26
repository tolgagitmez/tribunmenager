'use strict';
// Static, deterministic procedural stadium. Never mutates laws or physics.
(function(root){
 const profiles=Object.freeze({performance:{rows:7,spacing:2.1,turf:6,net:.92},balanced:{rows:10,spacing:1.45,turf:12,net:.68},quality:{rows:12,spacing:1.05,turf:20,net:.52}});
 const up=[0,1,0],white=[.92,.95,.90],concrete=[.29,.34,.38],dark=[.055,.09,.13],steel=[.19,.26,.33],blue=[.13,.31,.48];
 const rng=()=>{let n=1987;return()=>{n=(Math.imul(n,1664525)+1013904223)>>>0;return n/4294967296;};};
 function build(m,g,mode='balanced'){
  const p=profiles[mode];if(!p)throw Error('Invalid stadium detail');
  const X=g.halfLength,Z=g.halfWidth,random=rng();
  function floor(x,z,x2,z2,y,c){m.quad([x,y,z],[x,y,z2],[x2,y,z2],[x2,y,z],c,[up,up,up,up]);}
  function marking(x,z,x2,z2,w=.12){
   const dx=x2-x,dz=z2-z,len=Math.hypot(dx,dz);if(!len)return;
   const ox=-dz/len*w/2,oz=dx/len*w/2;
   m.quad([x+ox,.009,z+oz],[x2+ox,.009,z2+oz],[x2-ox,.009,z2-oz],[x-ox,.009,z-oz],white,[up,up,up,up]);
  }
  function arc(x,z,r,a,b,steps=48){for(let j=0;j<steps;j++){let q=a+(b-a)*j/steps,t=a+(b-a)*(j+1)/steps;marking(x+r*Math.cos(q),z+r*Math.sin(q),x+r*Math.cos(t),z+r*Math.sin(t));}}
  function dot(x,z,r=.12){for(let i=0;i<12;i++){const a=i*Math.PI/6,b=(i+1)*Math.PI/6;m.tri([x,.01,z],[x+r*Math.cos(a),.01,z+r*Math.sin(a)],[x+r*Math.cos(b),.01,z+r*Math.sin(b)],white,[up,up,up]);}}
  m.box(0,-.4,0,158,.6,119,dark);
  floor(-X-4,-Z-4,X+4,Z+4,-.012,[.095,.33,.15]);
  for(let i=0;i<12;i++)for(let j=0;j<p.turf;j++){
   const x=-X+2*X*i/12,z=-Z+2*Z*j/p.turf,v=(random()-.5)*.017;
   const c=i%2?[.12+v,.39+v,.19+v]:[.145+v,.445+v,.215+v];
   floor(x,z,-X+2*X*(i+1)/12,-Z+2*Z*(j+1)/p.turf,0,c);
  }
  marking(-X,-Z,X,-Z);marking(-X,Z,X,Z);marking(-X,-Z,-X,Z);marking(X,-Z,X,Z);marking(0,-Z,0,Z);
  arc(0,0,9.15,0,Math.PI*2);dot(0,0);
  const penaltyHalf=g.goalHalfWidth+16.5,goalAreaHalf=g.goalHalfWidth+5.5,theta=Math.acos(5.5/9.15);
  for(const s of [-1,1]){
   const x=s*X;
   for(const [depth,half] of [[16.5,penaltyHalf],[5.5,goalAreaHalf]]){
    const inner=s*(X-depth);marking(x,-half,inner,-half);marking(inner,-half,inner,half);marking(inner,half,x,half);
   }
   const spot=s*(X-11);dot(spot,0);arc(spot,0,9.15,s>0?Math.PI-theta:-theta,s>0?Math.PI+theta:theta,24);
   for(const z of [-1,1]){
    const a=s>0?(z>0?Math.PI:Math.PI/2):(z>0?-Math.PI/2:0);
    // quarter circle points inward on both axes.
    const start=s===1?(z===1?Math.PI:Math.PI/2):(z===1?-Math.PI/2:0);
    arc(x,z*Z,1,start,start+Math.PI/2,12);
    m.segment(x,0,z*Z,x,1.5,z*Z,.027,white);
    m.tri([x,1.5,z*Z],[x-s*.48,1.34,z*Z],[x,1.16,z*Z],[.90,.67,.13]);
   }
   const w=g.goalHalfWidth+g.postRadius,h=g.goalHeight+g.postRadius,r=g.postRadius,bx=x+s*2.7,net=[.56,.68,.72];
   for(const z of [-w,w]){m.segment(x,0,z,x,h,z,r,white);m.segment(x,h,z,bx,h*.87,z,.04,white);m.segment(bx,0,z,bx,h*.87,z,.04,white);}
   m.segment(x,h,-w,x,h,w,r,white);
   for(let i=0;i<=Math.ceil(2*w/p.net);i++){
    const z=-w+2*w*i/Math.ceil(2*w/p.net);
    m.segment(x,h,z,bx,h*.87,z,.012,net);m.segment(bx,0,z,bx,h*.87,z,.012,net);
   }
   for(let i=0;i<=Math.ceil(h/p.net);i++){
    const y=h*.87*i/Math.ceil(h/p.net);m.segment(bx,y,-w,bx,y,w,.012,net);
    for(const z of [-w,w])m.segment(x,y,z,bx,y,z,.012,net);
   }
   for(const xx of [x+s*.9,x+s*1.8])m.segment(xx,h-(Math.abs(xx-x)/2.7)*h*.13,-w,xx,h-(Math.abs(xx-x)/2.7)*h*.13,w,.012,net);
  }
  // Perimeter walkway and LED boards: solid matte panels, no commercial marks.
  for(const s of [-1,1]){
   floor(-X-6,s<0?-Z-6:Z+3,X+6,s<0?-Z-3:Z+6,-.02,[.16,.22,.24]);
   for(let i=0;i<14;i++){const x=-X+3+(2*X-6)*i/13;m.box(x,.65,s*(Z+3.9),6.6,1.2,.26,i%3===0?[.14,.36,.43]:dark);m.box(x,1.27,s*(Z+3.9),6.6,.055,.27,[.24,.64,.70]);}
   for(let j=0;j<9;j++){const z=-Z+4+(2*Z-8)*j/8;m.box(s*(X+4.5),.62,z,.25,1.15,6.2,blue);}
  }
  // Camera-facing long stand is intentionally a low cutaway, so the near
  // touchline remains visible. Three other sides have stepped grandstands.
  const seats=[[.11,.25,.40],[.16,.34,.49],[.21,.42,.55],[.34,.40,.47],[.45,.46,.43]];
  function stand(axis,sign,length,base,rows,roof){
   const loc=(u,y,d)=>axis==='z'?[u,y,sign*d]:[sign*d,y,u];
   const box=(u,y,d,w,h,depth,c)=>m.box(...loc(u,y,d),axis==='z'?w:depth,h,axis==='z'?depth:w,c);
   for(let row=0;row<rows;row++){
    const d=base+row*1.12,y=1.4+row*.64;
    box(0,y,d,length,.44,1.13,concrete);
    const count=Math.floor(length/p.spacing);
    for(let j=0;j<count;j++){
     const u=-length/2+(j+.5)*length/count;
     if(Math.abs(u)<1.7||Math.abs(Math.abs(u)-length/4)<1.15)continue;
     const c=seats[Math.floor(random()*seats.length)];
     // Broad seat blocks, sparse simplified spectators, no per-frame animation.
     box(u,y+.34,d,p.spacing*.82,.28,.52,c);
     if(mode!=='performance'&&random()<.34)box(u,y+.72,d,.38,.48,.31,seats[Math.floor(random()*seats.length)]);
    }
    for(const u of [-length/4,0,length/4])box(u,y+.26,d,1.25,.09,1.12,[.54,.57,.59]);
   }
   const last=base+(rows-1)*1.12,top=1.4+(rows-1)*.64;
   box(0,top+.55,last+.6,length,1.1,.34,steel);
   for(let u=-length/2+3;u<length/2;u+=12)box(u,top+.96,last+.4,.08,.8,.08,steel);
   if(roof){
    const y=top+4.8,d=last-2;
    box(0,y,d,length+1,.28,7.8,steel);
    box(0,y-.26,d-3.65,length,.25,.3,[.44,.53,.60]);
    for(let u=-length/2+5;u<length/2;u+=13){
     box(u,(y+top)/2,last+.9,.33,y-top,.33,steel);
     m.segment(...loc(u,y-.2,d-3.3),...loc(u,top+.8,last+.9),.09,steel);
    }
   }
  }
  stand('z',-1,2*X+11,Z+7,p.rows,true);
  stand('z',1,2*X+11,Z+7,3,false);
  for(const s of [-1,1])stand('x',s,2*Z+6,X+8,Math.max(5,p.rows-2),false);
  for(const x of [-X-12,X+12])for(const z of [-Z-14,Z+14]){
   m.box(x,12,z,.56,24,.56,steel);
   m.box(x,23.8,z,7.6,2.2,.4,steel);
   for(let j=0;j<5;j++)m.box(x-3+j*1.5,23.8,z-.26,1.05,1.3,.11,[.82,.89,.94]);
  }
  return {mode,rows:p.rows};
 }
 const api={build,profiles};root.TribunStadiumDesign=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
