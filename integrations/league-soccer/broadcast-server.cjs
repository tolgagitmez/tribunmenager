'use strict';
// Separate loopback-only pilot, never uses production league database.
// Only the currently due native frame is exposed; no future score or trace file.
const http=require('node:http'),fs=require('node:fs');
const Replay=require('./native-replay.js'),Broadcast=require('./broadcast-clock.js');
function createServer(frames,{kickoffMs,now=Date.now}={}){
 if(!Number.isSafeInteger(kickoffMs))throw Error('Invalid kickoff timestamp');
 const clock=Broadcast.create(frames);
 let lastTime=-Infinity;
 return http.createServer((req,res)=>{
  const headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
  function send(status,data){res.writeHead(status,headers);res.end(JSON.stringify(data));}
  if(req.method!=='GET')return send(405,{error:'GET required'});
  if(req.url!=='/api/native-pilot/broadcast')return send(404,{error:'Not found'});
  const time=now();if(!Number.isFinite(time))return send(503,{error:'Clock unavailable'});
  lastTime=Math.max(lastTime,time);
  const state=clock.at(lastTime-kickoffMs);
  const frame=state.phase==='scheduled'?null:frames[state.index];
  return send(200,{engine:'league-soccer',source:'precomputed-native-pilot',kickoffMs,serverTimeMs:lastTime,durationMs:clock.durationMs,phase:state.phase,elapsedMs:state.broadcastMs,remainingMs:state.remainingMs,frame});
 });
}
if(require.main===module){
 const [path,start]=process.argv.slice(2);
 if(!path)throw Error('Usage: node broadcast-server.cjs trace.ndjson [kickoff ISO timestamp]');
 const kickoffMs=start===undefined?Date.now()+10000:Date.parse(start);
 const frames=Replay.parse(fs.readFileSync(path,'utf8'));
 const port=Number(process.env.PORT||8091);
 const server=createServer(frames,{kickoffMs});
 server.listen(port,'127.0.0.1',()=>console.log('Native pilot API: http://127.0.0.1:'+port+'/api/native-pilot/broadcast; kickoff '+new Date(kickoffMs).toISOString()));
}
module.exports={createServer};
