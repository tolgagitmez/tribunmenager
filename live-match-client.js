'use strict';
(function(root){
const endpoint='/api/league/live-match';
const pollInterval=180;
const requestTimeout=6500;

class LiveMatchClient{
 constructor(round,{onState,onError}){
  this.round=typeof round==='string'&&/^\d+$/.test(round)?Number(round):round;
  this.onState=onState;
  this.onError=onError;
  this.running=false;
  this.polling=null;
  this.striking=false;
  this.retryDelay=pollInterval;
  this.visibility=()=>{
   this.clearTimer();
   if(!root.document.hidden)this.poll();
  };
 }
 start(){
  if(this.startup)return this.startup;
  if(!Number.isInteger(this.round)||this.round<0||this.round>9){
   this.onError(new Error('Geçerli bir lig maçı seç.'));
   return Promise.resolve(null);
  }
  let token;
  try{token=root.localStorage.getItem('tribun-league-token');}catch{}
  if(!token){
   this.onError(new Error('Canlı maça girmek için lig oturumu aç.'));
   return Promise.resolve(null);
  }
  this.token=token;
  this.running=true;
  root.document.addEventListener('visibilitychange',this.visibility);
  this.startup=this.poll();
  return this.startup;
 }
 clearTimer(){
  root.clearTimeout(this.timer);
  this.timer=null;
 }
 stop(){
  this.running=false;
  this.clearTimer();
  this.controller?.abort();
  root.document.removeEventListener('visibilitychange',this.visibility);
 }
 schedule(){
  this.clearTimer();
  if(this.running&&!this.striking&&!root.document.hidden)this.timer=root.setTimeout(()=>this.poll(),this.retryDelay);
 }
 async request(path,body){
  const payload=body?JSON.stringify(body):null;
  const controller=new root.AbortController(),timer=root.setTimeout(()=>controller.abort(),requestTimeout);
  this.controller=controller;
  const headers={Authorization:'Bearer '+this.token};
  const options={headers,cache:'no-store',signal:controller.signal};
  if(payload){
   headers['Content-Type']='application/json';
   options.method='POST';
   options.body=payload;
  }
  try{
   const response=await root.fetch(path,options);
   const data=await response.json().catch(()=>null);
   if(!response.ok){
    const error=new Error(data?.error||'Canlı maç bağlantısı kesildi.');
    error.status=response.status;
    throw error;
   }
   if(!data?.state||!([0,1].includes(data.side)))throw new Error('Canlı maç verisi alınamadı.');
   return data;
  }finally{
   root.clearTimeout(timer);
   this.controller=null;
  }
 }
 receive(data){
  if(!this.running)return null;
  this.retryDelay=pollInterval;
  this.onState(data);
  if(data.state.done)this.stop();
  return data;
 }
 report(error){
  if(!this.running)return;
  const problem=error.name==='AbortError'?new Error('Canlı maç bağlantısı zaman aşımına uğradı.'):error;
  this.onError(problem);
  if(error.status===401||error.status===403||error.status===404)this.stop();
 }
 poll(){
  if(!this.running||this.striking||root.document.hidden)return Promise.resolve(null);
  if(this.polling)return this.polling;
  this.clearTimer();
  this.polling=this.request(endpoint+'?round='+encodeURIComponent(this.round))
   .then(data=>this.receive(data))
   .catch(error=>{
    this.retryDelay=Math.min(2000,Math.max(500,this.retryDelay*2));
    this.report(error);
    return null;
   })
   .finally(()=>{
    this.polling=null;
    this.schedule();
   });
  return this.polling;
 }
 async strike(id,input){
  if(!this.running||this.striking||root.document.hidden)return false;
  this.striking=true;
  this.clearTimer();
  let refresh=false;
  try{
   await this.polling;
   if(!this.running)return false;
   const data=await this.request(endpoint+'/kick',{round:this.round,id,input:input??null});
   return !!this.receive(data);
  }catch(error){
   this.report(error);
   refresh=true;
   return false;
  }finally{
   this.striking=false;
   if(refresh)this.poll();
   else this.schedule();
  }
 }
}

root.TribunLiveMatchClient=LiveMatchClient;
})(window);
