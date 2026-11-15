'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const Status=require('../player-asset-status');
const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const base64=array=>Buffer.from(array.buffer,array.byteOffset,array.byteLength).toString('base64');
function mesh(){
 const vertices=new Float32Array(60);
 for(let i=0;i<3;i++)vertices.set([i*.1,i*.9,0,0,0,1,0,0,0,0,0,0,1,0,0,0,0,1,1,1],i*20);
 return {vertices:base64(vertices),indices:base64(new Uint16Array([0,1,2])),indexType:'H'};
}
function asset(){return {metadata:{id:'human-test',version:'1',license:'CC0-1.0',source:'https://example.test/source',files:[{path:'model.glb',sha256:'a'.repeat(64)}]},bones:Status.boneNames.map(name=>({name,head:[0,1,0],tail:[0,1.1,0],matrix:identity.slice(),inverseBind:identity.slice()})),lods:[mesh()]};}
function vertexEdit(a,index,value){const bytes=Buffer.from(a.lods[0].vertices,'base64'),values=new Float32Array(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));values[index]=value;a.lods[0].vertices=base64(values);}
const codes=a=>Status.validate(a).errors.map(e=>e.code);

test('valid interleaved geometry reports actual counts without changing asset data',()=>{
 const a=asset(),before=structuredClone(a),r=Status.validate(a);assert(r.ok);assert.deepEqual(a,before);assert.equal(r.summary.boneCount,19);assert.equal(r.summary.lods[0].vertexCount,3);assert.equal(r.summary.lods[0].triangleCount,1);assert.deepEqual(r.summary.lods[0].bounds.max,[.20000000298023224,1.7999999523162842,0]);assert.equal(r.summary.metadata.id,'human-test');
});
test('defined globals and valid buffers alone never imply an initialized GPU renderer',()=>{
 assert.equal(Status.inspect({assets:{}}).state,'invalid');assert.equal(Status.inspect({assets:asset()}).state,'loading');assert.equal(Status.inspect({assets:asset(),renderer:{}}).state,'ready');
});
test('missing model, explicit loading, WebGL failure and renderer failure are distinguished',()=>{
 assert.equal(Status.inspect({}).state,'missing');assert.equal(Status.inspect({loading:true}).state,'loading');assert.equal(Status.inspect({webgl:false}).state,'webgl-unavailable');const s=Status.inspect({assets:asset(),rendererError:new Error('shader link failed')});assert.equal(s.state,'renderer-error');assert(s.details.some(x=>x.includes('shader link failed')));
});
test('a missing script exposes the expected path and actual loading error',()=>{const s=Status.inspect({loadError:'HTTP 404'});assert.equal(s.state,'missing');assert(s.details.some(x=>x.includes(Status.expectedPath)));assert(s.details.some(x=>x.includes('404')));});
test('bone count and exact palette names protect the current renderer contract',()=>{
 const count=asset();count.bones.pop();assert(codes(count).includes('BONE_COUNT'));
 const names=asset();names.bones[0].name='unknown';assert(codes(names).includes('BONE_NAME'));
 const duplicate=asset();duplicate.bones[0].name='spine';assert(codes(duplicate).includes('BONE_NAME'));
 const hand=asset();[hand.bones[8],hand.bones[9]]=[hand.bones[9],hand.bones[8]];assert(codes(hand).includes('HAND_BONE_ORDER'));
});
test('zero length or nonfinite bone coordinates cannot enter a skin palette',()=>{const a=asset();a.bones[0].tail=a.bones[0].head.slice();assert(codes(a).includes('BONE_LENGTH'));a.bones[1].head[0]=NaN;assert(codes(a).includes('BONE_ENDPOINT'));});
test('inverse bind and rest matrices need the complete finite shape',()=>{const a=asset();a.bones[0].matrix.pop();a.bones[1].inverseBind[2]=Infinity;assert(codes(a).filter(x=>x==='BONE_MATRIX').length>=2);});
test('empty or malformed base64 and non-interleaved vertex lengths fail explicitly',()=>{
 for(const value of ['', 'not base64!', 'AAAA']){const a=asset();a.lods[0].vertices=value;assert(codes(a).includes('VERTEX_BUFFER'));}
});
test('floating point vertex data must remain finite',()=>{const a=asset();vertexEdit(a,0,NaN);assert(codes(a).includes('NONFINITE_VERTEX'));});
test('realistic model-sized base64 buffers validate without regexp stack exhaustion',()=>{
 const a=asset(),vertices=new Float32Array(20000*20);for(let i=0;i<20000;i++){vertices[i*20]=i/20000;vertices[i*20+1]=i/20000*1.8;vertices[i*20+5]=1;vertices[i*20+12]=1;}a.lods[0].vertices=base64(vertices);const result=Status.validate(a);assert(result.ok,JSON.stringify(result.errors));assert.equal(result.summary.lods[0].vertexCount,20000);
});
test('normal vectors cannot be zero',()=>{const a=asset();vertexEdit(a,5,0);assert(codes(a).includes('ZERO_NORMAL'));});
test('all four shader joint references are bounded integer indices even for zero weights',()=>{
 for(const value of [-1,19,.5]){const a=asset();vertexEdit(a,11,value);assert(codes(a).includes('JOINT_RANGE'));}
});
test('skin influences must be normalized nonnegative values',()=>{
 for(const [index,value] of [[12,-.2],[12,1.2],[12,.5],[13,.5]]){const a=asset();vertexEdit(a,index,value);assert(codes(a).includes('SKIN_WEIGHTS'));}
 const a=asset();vertexEdit(a,12,.6);vertexEdit(a,13,.4);assert(Status.validate(a).ok);
});
test('indices must address complete triangles within the vertex buffer',()=>{
 const outside=asset();outside.lods[0].indices=base64(new Uint16Array([0,1,3]));assert(codes(outside).includes('INDEX_RANGE'));
 const short=asset();short.lods[0].indices=base64(new Uint16Array([0,1]));assert(codes(short).includes('INDEX_BUFFER'));
 const odd=asset();odd.lods[0].indices='AAAA';assert(codes(odd).includes('INDEX_BUFFER'));
});
test('unsupported index format and absent LODs fail before draw',()=>{const a=asset();a.lods[0].indexType='X';assert(codes(a).includes('INDEX_BUFFER'));a.lods=[];assert(codes(a).includes('LOD_MISSING'));});
test('32-bit indices are structurally supported and GPU extension failure can be reported separately',()=>{const a=asset();a.lods[0].indexType='I';a.lods[0].indices=base64(new Uint32Array([0,1,2]));assert(Status.validate(a).ok);assert.equal(Status.inspect({assets:a,rendererError:'OES_element_index_uint'}).state,'renderer-error');});
test('metadata is copied as declared information without certifying a licence',()=>{
 const a=asset(),s=Status.inspect({assets:a,renderer:{}});assert.equal(s.provenance.license,'CC0-1.0');assert.equal(s.provenance.declaredOnly,true);assert.equal(s.provenance.verified,undefined);assert(Object.isFrozen(s));assert(Object.isFrozen(s.provenance.files));assert.notEqual(s.provenance.files,a.metadata.files);
 const unknown=asset();delete unknown.metadata;assert(Status.validate(unknown).warnings.some(w=>w.code==='PROVENANCE_UNDECLARED'));
});
test('a separately packaged manifest may provide metadata and never alters geometry readiness',()=>{
 const s=Status.inspect({assets:asset(),renderer:{},manifest:{id:'manifest-human',version:2,license:{spdx:'CC-BY-4.0'},source:{url:'https://example.test/model'}}});assert.equal(s.modelId,'manifest-human');assert.equal(s.provenance.version,'2');assert.equal(s.provenance.license,'CC-BY-4.0');assert.equal(s.state,'ready');
});
test('diagnostic DOM uses readable text, state selectors and an expandable technical view',()=>{
 const dom=new JSDOM('<div id="status"></div>'),element=dom.window.document.getElementById('status'),a=asset();a.metadata.source='<img src=x onerror=alert(1)>';
 const s=Status.inspect({assets:a,rendererError:'<script>bad()</script>'});Status.mount(element,s);assert.equal(element.dataset.playerAssetState,'renderer-error');assert.equal(element.dataset.playerModelState,'renderer-error');assert(element.querySelector('details summary'));assert.equal(element.querySelector('img'),null);assert.equal(element.querySelector('script'),null);assert(element.textContent.includes('<script>bad()</script>'));assert(element.textContent.includes('assets/player/CREDITS.md'));assert(element.textContent.includes('assets/player/manifest.json'));assert.equal(s.provenance.declaredOnly,true);
 Status.mount(element,Status.inspect({assets:asset(),renderer:{}}));assert.equal(element.querySelectorAll('details').length,1);assert.equal(element.dataset.playerAssetState,'ready');dom.window.close();
});
test('browser and CommonJS variants expose the same API without renderer or engine access',()=>{
 const context={window:{},atob:s=>Buffer.from(s,'base64').toString('binary')};vm.runInNewContext(fs.readFileSync(require.resolve('../player-asset-status'),'utf8'),context);const api=context.window.TribunPlayerAssetStatus;assert.equal(api.inspect({}).state,'missing');assert.deepEqual(Array.from(api.states),Status.states);assert.equal(api.validate(asset()).ok,true);
});

test('script load diagnostics report an observed HTTP status without inventing an unknown status',()=>{
 const context={window:{performance:{getEntriesByName:url=>url.includes('missing')?[{responseStatus:404}]:[]}},atob:s=>Buffer.from(s,'base64').toString('binary')};vm.runInNewContext(fs.readFileSync(require.resolve('../player-asset-status'),'utf8'),context);const api=context.window.TribunPlayerAssetStatus;api.scriptFailed('https://test/missing.js');assert(api.inspect({}).details.some(s=>s.includes('HTTP 404')));api.scriptFailed('https://test/offline.js');const details=api.inspect({}).details.join(' ');assert(details.includes('HTTP/ağ'));assert(!details.includes('404'));
});
