'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),R=require('../../player-renderer.js');
test('fictional player appearance stable by native identity, not slot or motion',()=>{
 const p={id:3,databaseId:17,team:0,index:2,role:'FIELD'},a=R.appearanceOf(p,true);
 const b=R.appearanceOf({...p,index:7,speed:9,face:2},true);
 for(const k of ['skin','hair','variant','beard'])assert.deepEqual(a[k],b[k]);
 assert.ok(new Set(Array.from({length:22},(_,i)=>JSON.stringify(R.appearanceOf({...p,databaseId:i+1},true).skin))).size>1);
 assert.deepEqual(R.appearanceOf({...p,visual:{skin:[.1,.2,.3]}},true).skin,[.1,.2,.3]);
 assert.deepEqual(R.appearanceOf(p,true).shirt,R.appearanceOf(p,false).shirt);
});
test('batch carries same appearance without changing scale or bone payload',()=>{
 const dual={real:new Float32Array(76).fill(.25),dual:new Float32Array(76).fill(.5)},data=new Float32Array(180),p={team:0,id:5,databaseId:9,x:3,z:-2,index:4,nativeAnatomy:{scale:.9}};
 const a=R.appearanceOf(p,true);R.packInstance(data,0,dual,p,true);
 assert.deepEqual(Array.from(data.slice(0,76)),Array.from(dual.real));
 assert.deepEqual(Array.from(data.slice(76,152)),Array.from(dual.dual));
 for(let i=0;i<3;i++)assert.ok(Math.abs(data[152+i]-a.skin[i])<1e-6);
 assert.equal(data[155],3);assert.equal(data[159],-2);assert.ok(Math.abs(data[163]-.9)<1e-6);
 assert.ok(R.fragmentShader.includes('kitDetail'));assert.ok(R.batchShaders.fragment.includes('kitDetail'));
});
