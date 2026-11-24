'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {JSDOM,VirtualConsole}=require('jsdom'),F=require('../catalog-friendly.js');
const root=path.resolve(__dirname,'..');
function snap(t){return {schema:1,source:'api-football',teamId:t,teamUid:'api-football:team:'+t,name:'Fictional '+t,fetchedAt:'2026-11-24T00:00:00Z',players:Array.from({length:22},(_,i)=>({providerId:t*100+i,uid:'api-football:player:'+(t*100+i),name:'Synthetic '+i,pos:i<2?'GK':i<9?'DEF':i<16?'MID':'ATT',number:i+1,age:25}))}}
function loaded(w){return new Promise((resolve,reject)=>{if(w.document.readyState==='complete')return resolve();const id=setTimeout(()=>reject(Error('page load timeout')),15000);w.addEventListener('load',()=>{clearTimeout(id);resolve()},{once:true});});}
async function until(fn){for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,20));}throw Error('UI not ready');}
test('real catalog page edits both XIs and sliders, actual match page starts isolated with 22 players',async()=>{
 const errors=[],requests=[],frames=[];
 const srv=http.createServer((req,res)=>{const p=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));requests.push(req.url);if(!p.startsWith(root+path.sep)){res.writeHead(403).end();return;}fs.readFile(p,(err,data)=>{if(err){res.writeHead(404).end();return;}res.setHeader('Content-Type',({'.html':'text/html','.js':'application/javascript','.css':'text/css'})[path.extname(p)]||'application/octet-stream');res.end(data);});});
 await new Promise(r=>srv.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+srv.address().port;
 const vc=new VirtualConsole();vc.on('jsdomError',e=>{if(e.type!=='resource-loading')errors.push(e.message)});
 let page,match;
 try{
  page=await JSDOM.fromURL(base+'/catalog-friendly.html',{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,virtualConsole:vc});
  const w=page.window,d=w.document;await loaded(w);
  const input=d.getElementById('files');Object.defineProperty(input,'files',{value:[snap(1),snap(2)].map(s=>({size:4000,text:async()=>JSON.stringify(s)}))});
  input.dispatchEvent(new w.Event('change'));await until(()=>d.querySelectorAll('#homeXI select').length===11&&d.querySelectorAll('#awayXI select').length===11);
  const rights=d.getElementById('rights');rights.checked=true;rights.dispatchEvent(new w.Event('change'));
  const press=d.getElementById('homepress');press.value=83;press.dispatchEvent(new w.Event('input'));
  const tempo=d.getElementById('awaytempo');tempo.value=42;tempo.dispatchEvent(new w.Event('input'));
  let cfg;w.TribunCatalogFriendly.launch=c=>{cfg=JSON.parse(JSON.stringify(c))};assert.equal(d.getElementById('launch').disabled,false);
  d.getElementById('launch').click();assert.equal(cfg.tactics.press,83);assert.equal(cfg.awayTactics.tempo,42);assert.equal(cfg.homeName,'Fictional 1');
  const sentinel=JSON.stringify({players:[{name:'Existing manager'}]});
  match=await JSDOM.fromURL(base+'/match.html?catalog=1',{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,virtualConsole:vc,
    beforeParse(w){w.sessionStorage.setItem(F.STORE,JSON.stringify(cfg));w.localStorage.setItem('tribun-manager-pro09',sentinel);w.localStorage.setItem('tribun-league-token','existing-league');w.requestAnimationFrame=cb=>{frames.push(cb);return frames.length};w.fetch=async u=>{if(String(u).includes('/api/'))throw Error('Unexpected league/transfer request');throw Error('Optional fetch unavailable')};const context=new Proxy({},{get(o,k){return o[k]??(o[k]=()=>{})}});w.HTMLCanvasElement.prototype.getContext=k=>k==='2d'?context:null;w.HTMLCanvasElement.prototype.getBoundingClientRect=()=>({width:960,height:540});}});
  await loaded(match.window);const mw=match.window;await until(()=>{try{return mw.TRIBUN_MATCH_TEST.getState().players.length>0}catch{return false}});
  const state=mw.TRIBUN_MATCH_TEST.getState();assert.equal(state.players.filter(p=>p.active&&!p.referee).length,22);assert.equal(state.t[0].press,83);assert.equal(state.t[1].tempo,42);
  assert.equal(mw.document.querySelector('.scoreboard .club strong').textContent,'Fictional 1');
  assert.equal(mw.sessionStorage.getItem(F.STORE),null);assert.equal(mw.localStorage.getItem('tribun-manager-pro09'),sentinel);assert.equal(mw.localStorage.getItem('tribun-league-token'),'existing-league');
  assert.equal(requests.some(x=>x.startsWith('/api/')),false);assert.deepEqual(errors,[]);
  mw.TRIBUN_MATCH_TEST.advance(2);assert(mw.TRIBUN_MATCH_TEST.getState().time>1);
 }finally{page?.window.close();match?.window.close();await new Promise(r=>srv.close(r));}
});
