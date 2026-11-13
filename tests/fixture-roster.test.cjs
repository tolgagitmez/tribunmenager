'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const http=require('node:http');
const path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const C=require('../club-data');
const code=fs.readFileSync(path.join(__dirname,'../match-config.js'),'utf8');
const copy=x=>JSON.parse(JSON.stringify(x));
function snapshot(isHome=true){
 const players=C.createRoster().map(p=>({...p,id:p.id+100,name:'Resmî '+p.name,preferredFoot:'left',strength:92}));
 return {version:1,snapshotAt:1234,fixture:{league:'ABC123',round:2,home:isHome?0:3,away:isHome?3:0,kickoff:1300,isHome,state:'scheduled'},
  ownTeam:{name:'Benim Kulübüm',source:'linked-roster'},opponent:{name:'Gerçek Rakip FK',source:'linked-roster',players,
   starters:C.starters.map(id=>id+100),formation:'4-4-2',tactics:{press:81,passing:'direct'},revision:19}};
}
function harness({token='',transfers,reply=snapshot(),fail=false}={}){
 let requests=0;const session=new Map();
 const root={TribunClubData:C,TribunTransfers:transfers,localStorage:{getItem:()=>token},sessionStorage:{getItem:key=>session.get(key)||null,setItem:(key,value)=>session.set(key,value)},AbortController,setTimeout,clearTimeout,
  fetch:async(url,options)=>{requests++;assert.equal(url,'/api/league/local-match');assert.equal(options.headers.Authorization,'Bearer '+token);if(fail)throw Error('offline');return {ok:true,json:async()=>copy(reply)};}};
 vm.runInNewContext(code,{window:root});
 return {api:root.TribunMatchConfig,requests:()=>requests,setToken:value=>{token=value;},setReply:value=>{reply=value;},session};
}
const input=()=>({players:C.createRoster(),starters:C.starters.slice(),formation:'4-3-3',tactics:{tempo:47},transferProfileId:'own',transferRevision:7});
test('the fixture competition supplies substitution limits while local clock preferences survive',async()=>{
 const reply={...snapshot(),competitionRules:{maxSubstitutions:2,substitutionWindows:1,minPlayers:7}},h=harness({token:'league-secret',reply}),source={...input(),rules:{maxSubstitutions:9,halftimeSeconds:12}};
 const cfg=await h.api.prepare(source);assert.equal(cfg.rules.maxSubstitutions,2);assert.equal(cfg.rules.substitutionWindows,1);assert.equal(cfg.rules.minPlayers,7);assert.equal(cfg.rules.halftimeSeconds,12);
});

test('official opponent snapshot preserves selected players, foot, profile, tactics and away venue',async()=>{
 const reply=snapshot(false),h=harness({token:'league-secret',reply}),cfg=await h.api.prepare(input());
 assert.deepEqual(copy(cfg.awayPlayers),reply.opponent.players);
 assert.deepEqual(copy(cfg.awayStarters),reply.opponent.starters);
 assert.equal(cfg.awayFormation,'4-4-2');assert.equal(cfg.awayTactics.press,81);
 assert.equal(cfg.homeName,'Benim Kulübüm');assert.equal(cfg.awayName,'Gerçek Rakip FK');
 assert.equal(cfg.fixture.isHome,false);assert.equal(cfg.opponentSource,'linked-roster');
 assert.equal(JSON.stringify(cfg).includes('league-secret'),false,'credentials never travel in URL/config');
 assert.equal(h.requests(),1);
});

test('same-revision own refresh preserves the selection and special roles that launched the match',async()=>{
 const source=input(),selected=source.starters.slice();[selected[0],selected[1]]=[selected[1],selected[0]];source.starters=selected;source.special={captain:selected[0]};
 const view={players:source.players,profileId:'own',revision:7};
 const h=harness({transfers:{hasSession:()=>true,sync:async()=>view,cached:()=>({starters:C.starters,special:{captain:0}})}});
 const cfg=await h.api.prepare(source);assert.deepEqual(copy(cfg.starters),selected);assert.equal(cfg.special.captain,selected[0]);
});

test('newer own revision replaces stale starters while preserving selected formation and tactics',async()=>{
 const source=input(),latest=C.starters.slice();latest[0]=16;
 const h=harness({transfers:{hasSession:()=>true,sync:async()=>({players:source.players,profileId:'own',revision:8}),cached:()=>({starters:latest,special:{captain:9}})}});
 const cfg=await h.api.prepare(source);assert.deepEqual(copy(cfg.starters),latest);assert.equal(cfg.transferRevision,8);
 assert.equal(cfg.formation,'4-3-3');assert.equal(cfg.tactics.tempo,47);
});

test('failed own authoritative refresh rejects the launch instead of passing stale players',async()=>{
 const h=harness({transfers:{hasSession:()=>true,sync:async()=>{throw Error('own offline');}}});
 await assert.rejects(h.api.prepare(input()),/own offline/);
});

test('a late older refresh cannot overwrite a newer already accepted roster revision',async()=>{
 const source=input();source.transferRevision=9;source.players[0].name='Yeni kaleci';
 const stale=C.createRoster(),h=harness({transfers:{hasSession:()=>true,
  sync:async()=>({players:stale,profileId:'own',revision:8}),
  cached:()=>({transferProfileId:'own',transferRevision:9,players:source.players,starters:C.starters})}});
 const cfg=await h.api.prepare(source);
 assert.equal(cfg.transferRevision,9);assert.equal(cfg.players[0].name,'Yeni kaleci');
});

test('switching transfer profiles uses the new account lineup instead of unrelated old array IDs',()=>{
 const old=input();old.starters[0]=16;
 const stored=new Map([['tribun-manager-pro09',JSON.stringify(old)]]);
 const root={TribunClubData:C,localStorage:{getItem:key=>stored.get(key)||null,setItem:(key,value)=>stored.set(key,value)},dispatchEvent:()=>{},addEventListener:()=>{}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../transfer-client.js'),'utf8'),{window:root,localStorage:root.localStorage,CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}}});
 const value=root.TribunTransfers.apply({profileId:'different-account',revision:1,players:C.createRoster(),starters:C.starters});
 assert.deepEqual(copy(value.starters),C.starters);
});

test('missing official opponent squad has an explicit demo source and visible explanation',async()=>{
 const reply=snapshot();reply.opponent={...reply.opponent,source:'missing-roster',players:[],starters:[]};
 const h=harness({token:'test',reply}),cfg=await h.api.prepare(input());
 assert.equal(cfg.opponentSource,'demo');assert.match(cfg.rosterNotice,/kayıtlı kadrosu bulunmuyor/);
 assert.equal(cfg.awayName,'Gerçek Rakip FK');assert.equal(cfg.awayPlayers.length,18);
 assert(cfg.awayPlayers.every(p=>p.dataKind==='demo'));assert.equal(cfg.fixture.round,2);
});

test('unavailable league API makes the fallback explicit and never claims a fixture roster',async()=>{
 const h=harness({token:'test',fail:true}),cfg=await h.api.prepare(input());
 assert.equal(cfg.opponentSource,'demo');assert.match(cfg.rosterNotice,/Lig kadrosuna ulaşılamadı/);
 assert.equal(cfg.fixture,undefined);
});

test('a completed launch snapshot survives page entry and restart without another refresh',async()=>{
 let syncs=0;
 const h=harness({token:'test',transfers:{hasSession:()=>true,sync:async()=>{syncs++;return {players:C.createRoster(),profileId:'own',revision:7};},cached:()=>({starters:C.starters})}});
 const first=await h.api.prepare(input()),second=await h.api.prepare(first);
 assert.deepEqual(copy(second),copy(first));assert.notEqual(first,second);
 assert.equal(h.requests(),1);assert.equal(syncs,1);
});

test('changing league credential invalidates an old page snapshot and refetches the new fixture',async()=>{
 const h=harness({token:'old-league'}),old=await h.api.prepare(input());
 assert(h.api.prepared(old));h.setToken('new-league');assert.equal(h.api.prepared(old),false);
 const next=snapshot(false);next.fixture.league='NEW456';next.opponent.name='Yeni Ligin Rakibi';h.setReply(next);
 const cfg=await h.api.prepare(old);assert.equal(cfg.fixture.league,'NEW456');assert.equal(cfg.awayName,'Yeni Ligin Rakibi');assert.equal(h.requests(),2);
 assert.equal(JSON.stringify(cfg).includes('new-league'),false);
});

test('removing league context cannot silently replay its old official opponent',async()=>{
 const h=harness({token:'old-league'}),old=await h.api.prepare(input());h.setToken('');
 const cfg=await h.api.prepare(old);assert.equal(cfg.fixture,undefined);assert.equal(cfg.opponentSource,'demo');assert.equal(cfg.awayName,'Deneme Rakibi');
});

test('changing transfer account invalidates the old snapshot and refreshes that account squad',async()=>{
 let profile='own',syncs=0;
 const roster=()=>C.createRoster().map(p=>({...p,name:profile+' '+p.name}));
 const transfers={hasSession:()=>true,sessionProfileId:()=>profile,
  sync:async()=>{syncs++;return {players:roster(),profileId:profile,revision:7};},
  cached:()=>({players:roster(),starters:C.starters,transferProfileId:profile,transferRevision:7})};
 const h=harness({transfers}),old=await h.api.prepare(input());profile='different';assert.equal(h.api.prepared(old),false);
 const cfg=await h.api.prepare(old);assert.equal(cfg.transferProfileId,'different');assert.match(cfg.players[0].name,/^different /);assert.equal(syncs,2);
});

test('an explicitly supplied opponent works offline using the same two-roster contract',async()=>{
 const cfg=input();cfg.awayPlayers=C.createRoster();cfg.awayStarters=C.starters.slice();cfg.awayName='Seçili Rakip';
 const h=harness(),result=await h.api.prepare(cfg);
 assert.equal(result.opponentSource,'provided-roster');assert.equal(result.awayName,'Seçili Rakip');assert.equal(h.requests(),0);
});

test('normal tactics launch transports the official roster into actual match HTML and pins its snapshot',async()=>{
 const root=path.resolve(__dirname,'..'),errors=[],requests=[];let response=snapshot(false);
 const server=http.createServer((req,res)=>{
  if(req.url==='/api/league/local-match'){requests.push(req.headers.authorization);res.setHeader('Content-Type','application/json');res.end(JSON.stringify(response));return;}
  const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
  if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
  fs.readFile(file,(error,data)=>{if(error){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',path.extname(file)==='.js'?'application/javascript':path.extname(file)==='.html'?'text/html':'text/css');res.end(data);});
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin=`http://127.0.0.1:${server.address().port}`,pages=[];
 const console=new VirtualConsole();console.on('jsdomError',error=>{if(error.type!=='resource-loading'&&!error.message.includes('navigation'))errors.push(error.message);});
 const context=new Proxy({}, {get(target,key){return target[key]??(target[key]=()=>{});}});
 async function page(route,matchConfig,launchContext){
  const dom=await JSDOM.fromURL(origin+route,{resources:'usable',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:console,
   beforeParse(window){window.localStorage.setItem('tribun-league-token','private-league-token');if(matchConfig)window.sessionStorage.setItem('tribun-match-config',JSON.stringify(matchConfig));if(launchContext)window.sessionStorage.setItem('tribun-match-launch-context-v1',launchContext);window.fetch=(url,options)=>fetch(origin+url,options);window.AbortController=AbortController;window.requestAnimationFrame=()=>1;window.HTMLCanvasElement.prototype.getContext=kind=>kind==='2d'?context:null;window.HTMLCanvasElement.prototype.getBoundingClientRect=()=>({width:960,height:540});}});
  pages.push(dom);
  await new Promise(resolve=>{if(dom.window.document.readyState==='complete')resolve();else dom.window.addEventListener('load',resolve,{once:true});});
  return dom.window;
 }
 try{
  const tactics=await page('/tactics.html');
  await tactics.document.getElementById('startMatch').onclick();
  const cfg=JSON.parse(tactics.sessionStorage.getItem('tribun-match-config'));
  assert.equal(cfg.opponentSource,'linked-roster');assert.equal(cfg.fixture.isHome,false);
  const match=await page('/match.html',cfg,tactics.sessionStorage.getItem('tribun-match-launch-context-v1'));
  assert.deepEqual(errors,[],'actual page scripts initialize without errors');
  const state=match.TRIBUN_MATCH_TEST.getState();
  const rival=state.players.find(p=>p.team===1&&p.index===0);
  assert.equal(rival.name,response.opponent.players.find(p=>p.id===cfg.awayStarters[0]).name);
  assert.equal(rival.preferredFoot,0);assert.equal(state.t[1].press,81);
  assert.match(match.document.querySelector('.scoreboard .club.away strong').textContent,/Gerçek Rakip/);
  assert.match(match.document.querySelector('.scoreboard .club:not(.away) small').textContent,/DEPLASMAN/);
  assert.match(match.document.querySelector('.bottom-note').textContent,/kayıtlı kadrosuyla/);
  response=snapshot(true);response.opponent.players.forEach(p=>p.name='Değişen kadro');
  match.TRIBUN_MATCH_TEST.restart();
  assert.equal(match.TRIBUN_MATCH_TEST.getState().players.find(p=>p.team===1&&p.index===0).name,rival.name);
  assert.deepEqual(requests,['Bearer private-league-token'],'prepared page and restart never refetch another squad');
  assert.deepEqual(errors,[]);
 }finally{pages.forEach(dom=>dom.window.close());await new Promise(resolve=>server.close(resolve));}
});
