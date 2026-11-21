'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const readline=require('node:readline');
const path=require('node:path');
const workerFile=path.resolve(__dirname,'../live-match-worker.cjs');
function worker(){
 const child=spawn(process.execPath,[workerFile],{stdio:['pipe','pipe','pipe']});
 const closed=once(child,'close');
 const lines=readline.createInterface({input:child.stdout})[Symbol.asyncIterator]();
 let stderr='';child.stderr.setEncoding('utf8').on('data',chunk=>stderr+=chunk);
 return {
  async request(operation){
   child.stdin.write(JSON.stringify(operation)+'\n');
   const answer=await lines.next();
   assert.equal(answer.done,false,stderr);
   const value=JSON.parse(answer.value);
   assert.equal(value.ok,true,value.error||stderr);
   return value;
  },
  async close(){child.stdin.end();const [code]=await closed;assert.equal(code,0,stderr);}
 };
}
const config={
 seed:6,
 tactics:{playstyle:'wing',crossing:'early',tempo:90,mentality:'attacking',aggression:80,press:76,passing:'direct'},
 awayTactics:{playstyle:'wing',crossing:'early',tempo:90,mentality:'attacking',aggression:80,press:76,passing:'direct'},
 rules:{periodSeconds:45,halftimeSeconds:0,addedTime:false}
};
async function game(teams){
 const client=worker();
 try{
  let current=(await client.request({op:'init',config})).state,steps=0,offered=0;
  while(!current.done&&steps<14000){
   const eligible=typeof teams==='function'?teams(steps):teams;
   const reply=await client.request({op:'advance',steps:120,teams:eligible});
   steps+=reply.steps;
   current=reply.state;
   if(current.pendingManagerKick){
    assert(eligible.length,'unwatched fixtures cannot wait for a spectator');
    const id=current.pendingManagerKick.id;
    offered++;
    const result=await client.request({op:'kick',id,input:null});
    assert.equal(result.accepted,true);
    current=result.state;
   }else if(!reply.steps&&!current.done)assert.fail('autonomous game stalled without a decision');
  }
  assert(current.done,'natural match must terminate');
  return {current,steps,offered};
 }finally{await client.close();}
}
test('watching two screens, watching one screen or closing both changes only control rights', {timeout:120000},async()=>{
 const [unwatched,both,homeOnly,awayOnly,watchedThenClosed]=await Promise.all([
  game([]),game([0,1]),game([0]),game([1]),
  game(steps=>steps<3600?[0,1]:[])
 ]);
 // A tactical upgrade can produce a complete clean fixture with no stoppage
 // kick. Presence invariance must still hold; explicit manager-kick tests
 // exercise guaranteed restart opportunities independently.
 assert.equal(unwatched.offered,0);
 for(const attended of [both,homeOnly,awayOnly,watchedThenClosed]){
  assert.equal(attended.steps,unwatched.steps,'all modes run the same number of physics ticks');
  // Includes event order, physical ball and every player position/animation,
  // scores, cards and referee state; no manager command means same world.
  assert.deepEqual(attended.current,unwatched.current);
 }
});
