'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
test('league screen exposes a usable, escaped and mobile-readable rotation list',async()=>{
 const html=fs.readFileSync(path.join(root,'league.html'),'utf8'),
       css=fs.readFileSync(path.join(root,'league.css'),'utf8'),
       code=fs.readFileSync(path.join(root,'league.js'),'utf8');
 assert.match(html,/id="rotationList"/);assert.match(html,/rotation-panel/);
 assert.match(css,/max-width:650px/);assert.match(css,/\.rotation-row/);
 const elements=new Map(),get=id=>{
  if(!elements.has(id))elements.set(id,{id,hidden:false,disabled:false,
    textContent:'',innerHTML:'',dataset:{},firstChild:{textContent:''},setAttribute:()=>{},focus:()=>{}});
  return elements.get(id);
 };
 const context={document:{
   getElementById:get,
   querySelector(selector){return selector==='#navClubName'?get('navClubName'):null;},
   querySelectorAll(){return []}
  },localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},
  fetch:async()=>({ok:true,json:async()=>({})}),
  setTimeout,clearTimeout,setInterval:()=>0,Date,Math,Array,Object,String,
  window:{location:{href:'',search:''}}};
 context.document.querySelector=selector=>selector==='#navClubName'?get('navClubName'):null;
 // Avoid a canvas/DOM dependency: call the real render() with fake text nodes.
 vm.createContext(context);vm.runInContext(code,context,{filename:'league.js'});
 const data={code:'ABC123',my_club:'Kulüp',manager:'Menajer',my_slot:0,
  my_formation:'4-3-3',my_tactics:{press:60,aggression:50},
  standings:[],teams:[],recent:[],active:[],next_kickoff:null,
  my_rotation:[{name:'<script>bad</script>',position:'DM',fitness:68,minutes:180,
    yellows:5,reds:1,suspended:true},{name:'Benç',position:'AM',
    fitness:97,minutes:0,suspended:false}]};
 // render() also accesses the nav label's first child when present.
 const nav={firstChild:{textContent:''}};
 context.document.querySelector=selector=>selector==='#navClubName'?nav:null;
 vm.runInContext('data='+JSON.stringify(data)+';render();',context);
 const htmlRows=get('rotationList').innerHTML;
 assert.match(htmlRows,/&lt;script&gt;bad&lt;\/script&gt;/);
 assert.doesNotMatch(htmlRows,/<script>/);
 assert.match(htmlRows,/data-suspended="true"/);
 assert.match(htmlRows,/CEZALI/);
 assert.match(htmlRows,/180 dk/);
 assert.match(htmlRows,/97%/);
 assert.match(get('tacticInfo').textContent,/Cezalı 1/);
 assert.match(get('tacticInfo').textContent,/Ortalama kondisyon %83/);
});
