'use strict';
/* Browser evidence for the GLB/glTF comparison prototype.
 * Records serial completed-frame latency on the available adapter, not device FPS.
 * Run from any directory: node tools/check-gltf-comparison.cjs
 */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {PNG}=require('pngjs');
const {createServer}=require('./serve-character-viewer.cjs');
const ROOT=path.resolve(__dirname,'..');
const REPORT=path.join(ROOT,'docs/validation/gltf-comparison.json');
const PREVIEWS=path.join(ROOT,'docs/previews');
const BACKENDS=['custom','three'];
const FIXTURE='assets/interchange/footballer.blender.glb';
const EXTERNAL='assets/interchange/footballer.blender.gltf';
const CLIPS=[['idle',.15],['run',.40],['shoot',.26],['dive-right',.27]];
const WARMUP=Number(process.env.GLTF_WARMUP||30),SAMPLES=Number(process.env.GLTF_SAMPLES||60),TRIALS=Number(process.env.GLTF_TRIALS||3);
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const hashFile=file=>sha(fs.readFileSync(path.join(ROOT,file)));
function summary(values){
 const sorted=values.slice().sort((a,b)=>a-b),at=p=>sorted[Math.floor((sorted.length-1)*p)];
 assert(sorted.length&&sorted.every(Number.isFinite),'Timing samples must be finite');
 return {samples:sorted.length,minMs:sorted[0],medianMs:at(.5),p95Ms:at(.95),maxMs:sorted.at(-1),meanMs:sorted.reduce((a,b)=>a+b,0)/sorted.length};
}
function parseGLB(bytes){
 assert.equal(bytes.readUInt32LE(0),0x46546c67,'Real GLB magic');assert.equal(bytes.readUInt32LE(4),2,'GLB v2');assert.equal(bytes.readUInt32LE(8),bytes.length,'GLB declared length');
 let offset=12,json=null,binary=null;
 while(offset<bytes.length){const length=bytes.readUInt32LE(offset),kind=bytes.readUInt32LE(offset+4);offset+=8;assert.equal(length%4,0,'GLB aligned chunks');assert(offset+length<=bytes.length,'GLB chunk boundary');
  if(kind===0x4e4f534a)json=JSON.parse(bytes.subarray(offset,offset+length).toString('utf8').trim());
  if(kind===0x004e4942)binary=bytes.subarray(offset,offset+length);offset+=length;
 }assert(json&&binary,'GLB JSON and binary chunks');return {json,binary};
}
function fixtureEvidence(){
 const bytes=fs.readFileSync(path.join(ROOT,FIXTURE)),{json,binary}=parseGLB(bytes),external=JSON.parse(fs.readFileSync(path.join(ROOT,EXTERNAL),'utf8'));
 assert.match(json.asset.generator,/Blender/i,'The comparison fixture must be a Blender export');
 assert.equal(json.asset.version,'2.0');assert.equal(json.materials.length,10,'Ten real material primitives');
 assert(json.animations.length>=4&&json.skins.length>0,'Skin and animation export');
 assert(external.buffers.some(b=>b.uri&&!b.uri.startsWith('data:')),'External glTF must request a .bin');
 assert(external.images.some(i=>i.uri&&!i.uri.startsWith('data:')),'External glTF must request images');
 const externalPaths=[...external.buffers,...external.images].filter(v=>v.uri&&!v.uri.startsWith('data:')).map(v=>path.posix.join(path.posix.dirname(EXTERNAL),v.uri));
 for(const file of externalPaths)assert(fs.statSync(path.join(ROOT,file)).isFile(),'External resource '+file);
 const triangles=json.meshes.reduce((sum,m)=>sum+m.primitives.reduce((n,p)=>{assert.equal(p.mode??4,4,'Triangle primitive');return n+json.accessors[p.indices].count/3;},0),0);
 return {path:FIXTURE,bytes:bytes.length,sha256:sha(bytes),generator:json.asset.generator,binaryBytes:binary.length,triangles,
  materials:json.materials.map(m=>m.name),skins:json.skins.map(s=>({name:s.name,joints:s.joints.length})),
  clips:json.animations.map(a=>a.name),primitives:json.meshes.reduce((sum,m)=>sum+m.primitives.length,0),
  external:{path:EXTERNAL,sha256:hashFile(EXTERNAL),resources:externalPaths.map(p=>({path:p,bytes:fs.statSync(path.join(ROOT,p)).size,sha256:hashFile(p)}))}};
}
/* Installed before page scripts. Actual GL calls and texture allocations are
 * observed without replacing render, animation, materials, or scene geometry. */
const INSTRUMENT=()=>{
 const qa=window.__gltfQA={contexts:[],frame:null,shaders:[],programs:[],shaderFailures:[],textureUploads:[],rafCallbacks:0};
 const originalContext=HTMLCanvasElement.prototype.getContext,states=new WeakMap(),shaderSource=new WeakMap(),attached=new WeakMap(),uniformNames=new WeakMap();
 const patches=[],raf=window.requestAnimationFrame;
 window.requestAnimationFrame=function(callback){return raf.call(window,time=>{qa.rafCallbacks++;return callback(time);});};
 const state=gl=>{if(!states.has(gl))states.set(gl,{buffers:new Map(),textures:new Map(),boundBuffers:new Map(),boundTextures:new Map(),textureUnit:0});return states.get(gl);};
 const triangleCount=(gl,mode,count,instances=1)=>mode===gl.TRIANGLES?Math.floor(count/3)*instances:(mode===gl.TRIANGLE_STRIP||mode===gl.TRIANGLE_FAN)?Math.max(0,count-2)*instances:0;
 const frameEntry=gl=>{if(!qa.frame)return null;const index=qa.contexts.findIndex(c=>c.gl===gl);return qa.frame.contexts[index]||(qa.frame.contexts[index]={drawCalls:0,triangles:0,verticesOrIndices:0,boneUniformUploadBytes:0,floatTextureUploadBytes:0,completionReadbacks:0,readbackBytes:0});};
 HTMLCanvasElement.prototype.getContext=function(kind,...args){const gl=originalContext.call(this,kind,...args);if(gl&&/^webgl/.test(kind)&&!qa.contexts.some(c=>c.gl===gl)){qa.contexts.push({gl,canvas:this,kind});state(gl);}return gl;};
 function install(proto){
  if(!proto)return;
  function wrap(name,hook){const original=proto[name];if(typeof original!=='function'||original.__gltfQA)return;const fn=function(...args){return hook.call(this,original,args);};fn.__gltfQA=true;proto[name]=fn;patches.push({proto,name,original,fn});}
  wrap('shaderSource',function(original,args){shaderSource.set(args[0],args[1]);qa.shaders.push(args[1]);return original.apply(this,args);});
  wrap('compileShader',function(original,args){const result=original.apply(this,args);if(!this.getShaderParameter(args[0],this.COMPILE_STATUS))qa.shaderFailures.push({stage:'compile',message:this.getShaderInfoLog(args[0])});return result;});
  wrap('attachShader',function(original,args){const list=attached.get(args[0])||[];list.push(args[1]);attached.set(args[0],list);return original.apply(this,args);});
  wrap('linkProgram',function(original,args){const result=original.apply(this,args),program=args[0],sources=(attached.get(program)||[]).map(shader=>shaderSource.get(shader)||'');if(this.getProgramParameter(program,this.LINK_STATUS)){const activeUniforms=[];for(let i=0;i<this.getProgramParameter(program,this.ACTIVE_UNIFORMS);i++){const uniform=this.getActiveUniform(program,i);activeUniforms.push({name:uniform.name,size:uniform.size,type:uniform.type});}qa.programs.push({context:qa.contexts.findIndex(c=>c.gl===this),activeUniforms,dualQuaternion:sources.some(s=>/uBoneReal\s*\[\s*19\s*\]/.test(s)&&/uBoneDual\s*\[\s*19\s*\]/.test(s)),linearBlend:activeUniforms.some(u=>u.name==='boneTexture')&&sources.some(s=>/skinMatrix|skinned/.test(s))});}else qa.shaderFailures.push({stage:'link',message:this.getProgramInfoLog(program)});return result;});
  wrap('bindBuffer',function(original,args){state(this).boundBuffers.set(args[0],args[1]);return original.apply(this,args);});
  wrap('getUniformLocation',function(original,args){const result=original.apply(this,args);if(result)uniformNames.set(result,args[1]);return result;});
  wrap('uniform4fv',function(original,args){const entry=frameEntry(this);if(entry&&/^uBone(?:Real|Dual)/.test(uniformNames.get(args[0])||''))entry.boneUniformUploadBytes+=args[1].byteLength;return original.apply(this,args);});
  wrap('bufferData',function(original,args){const s=state(this),buffer=s.boundBuffers.get(args[0]);if(buffer)s.buffers.set(buffer,typeof args[1]==='number'?args[1]:args[1]?.byteLength||0);return original.apply(this,args);});
  wrap('deleteBuffer',function(original,args){state(this).buffers.delete(args[0]);return original.apply(this,args);});
  wrap('activeTexture',function(original,args){state(this).textureUnit=args[0];return original.apply(this,args);});
  wrap('bindTexture',function(original,args){const s=state(this);s.boundTextures.set(s.textureUnit+':'+args[0],args[1]);return original.apply(this,args);});
  wrap('deleteTexture',function(original,args){state(this).textures.delete(args[0]);return original.apply(this,args);});
  wrap('readPixels',function(original,args){const entry=frameEntry(this);if(entry){entry.completionReadbacks++;entry.readbackBytes+=args[2]*args[3]*4;}return original.apply(this,args);});
  function texInfo(gl,target,level,width,height,bytesPerPixel,levels=1){const s=state(gl),texture=s.boundTextures.get(s.textureUnit+':'+target);if(!texture||!width||!height)return;const info=s.textures.get(texture)||{levels:{}};for(let i=0;i<levels;i++)info.levels[level+i]=Math.max(1,width>>i)*Math.max(1,height>>i)*bytesPerPixel;s.textures.set(texture,info);}
  wrap('texImage2D',function(original,args){const result=original.apply(this,args),image=args.length===6?args[5]:null,width=image?(image.naturalWidth||image.width):args[3],height=image?(image.naturalHeight||image.height):args[4],type=image?args[4]:args[7],format=image?args[3]:args[6],channels=format===this.RGB?3:format===this.RED?1:format===this.RG?2:4,bpp=channels*(type===this.FLOAT?4:type===this.HALF_FLOAT?2:1);texInfo(this,args[0],args[1],width,height,bpp);if(image||args[8])qa.textureUploads.push({context:qa.contexts.findIndex(c=>c.gl===this),method:'texImage2D',url:image?.src||null,source:image?.constructor.name||'typed-array',width,height,type});return result;});
  wrap('texStorage2D',function(original,args){const result=original.apply(this,args),bpp=args[2]===this.RGBA32F?16:args[2]===this.RGBA16F?8:4;texInfo(this,args[0],0,args[3],args[4],bpp,args[1]);return result;});
  wrap('texSubImage2D',function(original,args){const entry=frameEntry(this),type=args.length>=9?args[7]:args[5],data=args.length>=9?args[8]:args[6],width=args.length>=9?args[4]:(data?.naturalWidth||data?.width),height=args.length>=9?args[5]:(data?.naturalHeight||data?.height);if(entry&&type===this.FLOAT&&data?.byteLength)entry.floatTextureUploadBytes+=data.byteLength;if(data)qa.textureUploads.push({context:qa.contexts.findIndex(c=>c.gl===this),method:'texSubImage2D',url:data.src||null,source:data.constructor.name,width,height,type});return original.apply(this,args);});
  wrap('generateMipmap',function(original,args){const result=original.apply(this,args),s=state(this),texture=s.boundTextures.get(s.textureUnit+':'+args[0]),info=s.textures.get(texture);if(info?.levels[0])info.generatedMipmapBytes=Math.floor(info.levels[0]*4/3);return result;});
  for(const name of ['drawElements','drawArrays','drawElementsInstanced','drawArraysInstanced'])wrap(name,function(original,args){const entry=frameEntry(this);if(entry){const count=name.startsWith('drawElements')?args[1]:args[2],instances=name.endsWith('Instanced')?args[name.startsWith('drawElements')?4:3]:1;entry.drawCalls++;entry.verticesOrIndices+=count*instances;entry.triangles+=triangleCount(this,args[0],count,instances);}return original.apply(this,args);});
 }
 install(window.WebGLRenderingContext?.prototype);install(window.WebGL2RenderingContext?.prototype);
 qa.uninstall=()=>{for(const {proto,name,original,fn}of patches)if(proto[name]===fn)proto[name]=original;};
 qa.reinstall=()=>{for(const {proto,name,fn}of patches)proto[name]=fn;};
 qa.begin=()=>{qa.frame={contexts:{}};};
 qa.end=()=>{const f=qa.frame;qa.frame=null;return f;};
 qa.stats=()=>qa.contexts.map(({gl,canvas,kind})=>{const s=state(gl),debug=gl.getExtension('WEBGL_debug_renderer_info');return {canvas:canvas.id,kind,contextLost:gl.isContextLost(),drawingBuffer:[gl.drawingBufferWidth,gl.drawingBufferHeight],cssSize:[canvas.clientWidth,canvas.clientHeight],adapter:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),vendor:debug?gl.getParameter(debug.UNMASKED_VENDOR_WEBGL):gl.getParameter(gl.VENDOR),version:gl.getParameter(gl.VERSION),attributes:gl.getContextAttributes(),bufferBytes:[...s.buffers.values()].reduce((a,b)=>a+b,0),estimatedTextureBytes:[...s.textures.values()].reduce((sum,t)=>sum+(t.generatedMipmapBytes||Object.values(t.levels).reduce((a,b)=>a+b,0)),0),textureCount:s.textures.size,glError:gl.getError()};});
 qa.pixels=id=>{const found=qa.contexts.find(c=>c.canvas.id===id);if(!found)throw Error('No context for '+id);const {gl}=found,width=gl.drawingBufferWidth,height=gl.drawingBufferHeight,pixels=new Uint8Array(width*height*4);gl.finish();gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);let hash=2166136261,nonBackground=0;const colors=new Set(),background=pixels.slice(0,3);for(let i=0;i<pixels.length;i+=4){for(let k=0;k<3;k++)hash=Math.imul(hash^pixels[i+k],16777619);if(Math.abs(pixels[i]-background[0])+Math.abs(pixels[i+1]-background[1])+Math.abs(pixels[i+2]-background[2])>20)nonBackground++;if(i%52===0)colors.add((pixels[i]>>3)*1024+(pixels[i+1]>>3)*32+(pixels[i+2]>>3));}return {width,height,pixelHash:(hash>>>0).toString(16),nonBackground,colors:colors.size,glError:gl.getError()};};
};

function pixelDifference(first,second){const a=PNG.sync.read(first),b=PNG.sync.read(second);assert.equal(a.width,b.width);assert.equal(a.height,b.height);let difference=0,changed=0;for(let i=0;i<a.data.length;i+=4){const d=Math.abs(a.data[i]-b.data[i])+Math.abs(a.data[i+1]-b.data[i+1])+Math.abs(a.data[i+2]-b.data[i+2]);difference+=d;if(d>25)changed++;}return {meanAbsoluteRGB:difference/(a.width*a.height*3),changedPixels:changed};}

function readAccessor(gltf,binary,index){
 const accessor=gltf.accessors[index],view=gltf.bufferViews[accessor.bufferView];assert(!accessor.sparse,'Fixture expected sampler does not support sparse accessors');
 const components={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16}[accessor.type],size={5126:4,5125:4,5123:2,5121:1}[accessor.componentType];assert(components&&size,'Known accessor format');
 const out=[],offset=(view.byteOffset||0)+(accessor.byteOffset||0),stride=view.byteStride||size*components;
 const method={5126:'readFloatLE',5125:'readUInt32LE',5123:'readUInt16LE',5121:'readUInt8'}[accessor.componentType];
 for(let i=0;i<accessor.count;i++)for(let j=0;j<components;j++)out.push(binary[method](offset+i*stride+j*size));return {values:out,components,count:accessor.count};
}
const multiply=(a,b)=>{const out=Array(16).fill(0);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];return out;};
function compose(t,q,s){const [x,y,z,w]=q,x2=x+x,y2=y+y,z2=z+z,xx=x*x2,xy=x*y2,xz=x*z2,yy=y*y2,yz=y*z2,zz=z*z2,wx=w*x2,wy=w*y2,wz=w*z2;return [(1-(yy+zz))*s[0],(xy+wz)*s[0],(xz-wy)*s[0],0,(xy-wz)*s[1],(1-(xx+zz))*s[1],(yz+wx)*s[1],0,(xz+wy)*s[2],(yz-wx)*s[2],(1-(xx+yy))*s[2],0,...t,1];}
function slerp(a,b,t){let dot=a.reduce((sum,n,i)=>sum+n*b[i],0),target=b.slice();if(dot<0){dot=-dot;target=target.map(v=>-v);}if(dot>.9995){const q=a.map((v,i)=>v+(target[i]-v)*t),norm=Math.hypot(...q);return q.map(v=>v/norm);}const angle=Math.acos(Math.min(1,dot)),sin=Math.sin(angle);return a.map((v,i)=>(Math.sin((1-t)*angle)*v+Math.sin(t*angle)*target[i])/sin);}
function expectedBones(clip,time){
 const {json:g,binary}=parseGLB(fs.readFileSync(path.join(ROOT,FIXTURE))),animation=g.animations.find(a=>a.name===clip);assert(animation,'Fixture clip '+clip);
 const transforms=g.nodes.map(n=>({translation:n.translation?.slice()||[0,0,0],rotation:n.rotation?.slice()||[0,0,0,1],scale:n.scale?.slice()||[1,1,1]}));
 for(const channel of animation.channels){const sampler=animation.samplers[channel.sampler],times=readAccessor(g,binary,sampler.input).values,output=readAccessor(g,binary,sampler.output);assert(['LINEAR','STEP'].includes(sampler.interpolation||'LINEAR'),'Expected linear fixture animation');let index=0;while(index<times.length-2&&time>times[index+1])index++;const next=Math.min(index+1,times.length-1),alpha=Math.max(0,Math.min(1,(time-times[index])/(times[next]-times[index]||1))),a=output.values.slice(index*output.components,(index+1)*output.components),b=output.values.slice(next*output.components,(next+1)*output.components);transforms[channel.target.node][channel.target.path]=sampler.interpolation==='STEP'?a:channel.target.path==='rotation'?slerp(a,b,alpha):a.map((v,i)=>v+(b[i]-v)*alpha);}
 const parents=new Map();g.nodes.forEach((node,i)=>(node.children||[]).forEach(c=>parents.set(c,i)));const world=new Map();function matrix(index){if(world.has(index))return world.get(index);const n=g.nodes[index],t=transforms[index],local=n.matrix||compose(t.translation,t.rotation,t.scale),result=parents.has(index)?multiply(matrix(parents.get(index)),local):local;world.set(index,result);return result;}
 return g.skins[0].joints.map(index=>({name:g.nodes[index].name,matrix:matrix(index)}));
}

function sourceHashes(){
 const files=new Set(['tools/check-gltf-comparison.cjs','tools/serve-character-viewer.cjs','player-renderer.js','player-skinning.js','player-asset-status.js','humanoid-rig.js','character-palette-constraints.js']);
 const walk=directory=>{for(const entry of fs.readdirSync(path.join(ROOT,directory),{withFileTypes:true})){const name=path.posix.join(directory,entry.name);if(entry.isDirectory())walk(name);else files.add(name);}};
 for(const name of fs.readdirSync(ROOT))if(/^(interop|gltf|standard-gltf)/.test(name)&&fs.statSync(path.join(ROOT,name)).isFile())files.add(name);
 for(const directory of ['assets/interchange','vendor/three'])if(fs.existsSync(path.join(ROOT,directory)))walk(directory);
 return Object.fromEntries([...files].sort().map(file=>[file,hashFile(file)]));
}
const statusRecord=result=>result&&typeof result==='object'?result:{value:result};
function compareBones(actual,expected){
 const actors=Array.isArray(actual)?actual:actual.actors;assert(actors?.length,'Actor bone snapshot is required');
 const bones=actors[0].bones||actors,map=new Map(bones.map(b=>[b.name,b.matrix||b.world||b.matrixWorld]));let maximum=0;
 for(const bone of expected){const matrix=map.get(bone.name);assert(matrix?.length===16,'World matrix missing for '+bone.name);for(let i=0;i<16;i++){assert(Number.isFinite(matrix[i]),'Finite bone world matrix');maximum=Math.max(maximum,Math.abs(matrix[i]-bone.matrix[i]));}}
 assert(maximum<3e-5,'Sampled world bones differ from independently sampled GLB: '+maximum);return {bones:expected.length,maximumAbsoluteMatrixError:maximum};
}
async function prepare(browser,base){
 const context=await browser.newContext({viewport:{width:1320,height:1000},deviceScaleFactor:1}),page=await context.newPage(),errors=[],consoleErrors=[],responses=[],requests=[],failed=[];
 page.on('pageerror',error=>errors.push(error.message));page.on('request',request=>requests.push(request.url()));
 page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text());});
 page.on('requestfailed',request=>failed.push({url:request.url(),failure:request.failure()?.errorText}));
 page.on('response',response=>responses.push({url:response.url(),status:response.status(),headers:response.headers()}));
 await page.addInitScript(INSTRUMENT);
 await page.goto(base+'/interop-lab.html?manual=1',{waitUntil:'load'});
 await page.waitForFunction(()=>!!window.TribunInteropLab?.load,null,{timeout:45000});
 await page.evaluate(()=>{window.TribunInteropLab.pauseAll();window.TribunInteropLab.resize?.({width:600,height:560,pixelRatio:1});});
 return {context,page,errors,consoleErrors,responses,requests,failed};
}
function assertHealthy(contexts){for(const context of contexts){assert.equal(context.contextLost,false,context.canvas+' context remains live');assert.equal(context.glError,0,context.canvas+' has no WebGL error');}}
async function load(page,backend,url,count=1,extra={}){return page.evaluate(async options=>{const metadata=await window.TribunInteropLab.load(options),stats=window.TribunInteropLab.stats(options.backend);return {metadata,stats};},{backend,url,count,...extra});}
function assertReady(loaded,fixture,count=1){const metadata=loaded.metadata?.metadata||loaded.metadata||loaded.stats.metadata;assert.equal(loaded.stats.status,'ready','Terminal ready state');assert.equal(loaded.stats.actorCount??loaded.stats.count,count,'Loaded real actor count');assert.equal(metadata.materialCount,10,'All ten standard materials');assert.equal(metadata.jointCount,19,'Complete standard skeleton');assert.equal(metadata.triangles,fixture.triangles,'Full source geometry');assert.equal(metadata.textureCount,2,'Both standard source maps');assert(metadata.textures.every(t=>t.width>0&&t.height>0),'Source maps have decoded pixels');return metadata;}
async function capture(page,backend,clip,time){
 await page.evaluate(options=>window.TribunInteropLab.frame(options),{backend,clip,time});
 const scene=await page.evaluate(name=>{const stats=window.TribunInteropLab.stats(name);return {clip:stats.clip,time:stats.time,camera:stats.camera,features:stats.features,render:stats.render};},backend);
 const pixels=await page.evaluate(id=>window.__gltfQA.pixels(id),backend+'-canvas');
 assert(pixels.colors>30&&pixels.nonBackground>1000,'Rendered character scene requires actual varying pixels');assert.equal(pixels.glError,0,'Pixel read WebGL error');
 const file='docs/previews/gltf-'+backend+'-'+clip+'.png',bytes=await page.locator('#'+backend+'-canvas').screenshot({path:path.join(ROOT,file),timeout:90000});
 return {backend,clip,time,path:file,sha256:sha(bytes),bytes:bytes.length,pixels,scene};
}
async function normalEvidence(browser,base,fixture){
 const record=await prepare(browser,base),{page}=record,result={loads:[],poses:[],captures:[],external:[],trials:[]};
 try{
  for(const backend of BACKENDS){const start=performance.now(),loaded=await load(page,backend,'/'+FIXTURE),metadata=assertReady(loaded,fixture);result.loads.push({backend,wallMs:performance.now()-start,metadata:statusRecord(metadata),stats:loaded.stats});}
  const adapters=await page.evaluate(()=>window.__gltfQA.stats());result.contexts=adapters;assert.equal(adapters.length,2,'Two independent real WebGL contexts');
  assertHealthy(adapters);
  assert.deepEqual(adapters.map(a=>a.drawingBuffer),[[600,560],[600,560]],'Matched resolution and DPR');
  for(const backend of BACKENDS){
   for(const [clip,time]of CLIPS){
    await page.evaluate(options=>window.TribunInteropLab.sample(options),{backend,clip,time});
    const bones=await page.evaluate(name=>window.TribunInteropLab.boneWorld(name),backend);
    result.poses.push({backend,clip,time,...compareBones(bones,expectedBones(clip,time))});
    result.captures.push(await capture(page,backend,clip,time));
   }
   // Exact source keys and between-key samples, independently evaluated from
   // glTF accessors, prove animation playback rather than static rest bones.
   for(const [clip,time]of [['run',0],['run',1/30],['shoot',.235],['dive-right',.281]]){
    await page.evaluate(options=>window.TribunInteropLab.sample(options),{backend,clip,time});
    result.poses.push({backend,clip,time,...compareBones(await page.evaluate(name=>window.TribunInteropLab.boneWorld(name),backend),expectedBones(clip,time))});
   }
   const idle=fs.readFileSync(path.join(ROOT,'docs/previews/gltf-'+backend+'-idle.png'));
   for(const [clip]of CLIPS.slice(1)){const entry=result.captures.find(c=>c.backend===backend&&c.clip===clip)||result.captures.find(c=>c.path==='docs/previews/gltf-'+backend+'-'+clip+'.png');entry.differenceFromIdle=pixelDifference(idle,fs.readFileSync(path.join(ROOT,entry.path)));assert(entry.differenceFromIdle.changedPixels>100,'Frozen pose screenshots must change actual character pixels');}
  }
  for(const [clip,time]of CLIPS){const pair=BACKENDS.map(backend=>result.captures.find(c=>c.backend===backend&&c.clip===clip));for(const capture of pair){assert.equal(capture.scene.clip,clip);assert.equal(capture.scene.time,time);assert.equal(capture.scene.features.adaptiveQuality,false);assert.equal(capture.scene.features.lod,false);}for(const key of ['projectionMatrix','viewMatrix'])assert(pair[0].scene.camera[key].every((v,i)=>Math.abs(v-pair[1].scene.camera[key][i])<1e-6),'Matched camera '+key+' for '+clip);}
  await page.evaluate(()=>{for(const backend of ['custom','three'])window.TribunInteropLab.frame({backend,clip:'idle',time:.15});});
  const preview='docs/previews/gltf-comparison-idle.png';await page.screenshot({path:path.join(ROOT,preview),fullPage:true,timeout:90000});result.pagePreview={path:preview,sha256:hashFile(preview)};
  for(const backend of BACKENDS){const previous=record.responses.length,metadata=assertReady(await load(page,backend,'/'+EXTERNAL),fixture);await page.evaluate(options=>window.TribunInteropLab.frame(options),{backend,clip:'run',time:.4});const wanted=['/'+EXTERNAL,...fixture.external.resources.map(r=>'/'+r.path)],actual=record.responses.slice(previous);for(const resource of wanted)assert(actual.some(r=>new URL(r.url).pathname===resource&&r.status===200),'Real external glTF request missing '+backend+' '+resource);result.external.push({backend,metadata:statusRecord(metadata),requests:actual.filter(r=>wanted.includes(new URL(r.url).pathname))});}
  // Reload the same binary fixture for both, then alternate ordering to reduce
  // thermal/order bias. No automatic animation or quality selection is active.
  for(const count of [1,22]){
   for(const backend of BACKENDS)assertReady(await load(page,backend,'/'+FIXTURE,count),fixture,count);
   for(let trial=0;trial<TRIALS;trial++)for(const backend of trial%2?BACKENDS.slice().reverse():BACKENDS){
    const measurement=await page.evaluate(async({backend,warmup,samples})=>{
     const api=window.TribunInteropLab,qa=window.__gltfQA,times=i=>.05+(i%30)/60;
     api.pauseAll();const programsBefore=qa.programs.length;qa.begin();const first=api.frame({backend,clip:'run',time:times(0)}),probeDraw=qa.end(),programsAfterFirst=qa.programs.length;
     // Native GL methods are restored during all timed samples. Memory/draw
     // instrumentation is a separate untimed probe to avoid charging Three's
     // extra binds/draws for harness Map bookkeeping.
     qa.uninstall();let values=[],rafCallbacks;
     try{for(let i=0;i<warmup;i++)api.frame({backend,clip:'run',time:times(i)});const beforeRAF=qa.rafCallbacks;
      for(let i=0;i<samples;i++){const frame=api.frame({backend,clip:'run',time:times(i)});if(frame.completionFence!=='synchronous-readPixels-4-bytes')throw Error('A native pixel completion fence is required for every timing sample');values.push({cpuUpdateMs:frame.cpuUpdateMs,submitMs:frame.submitMs,completedFrameMs:frame.completedFrameMs,completionFence:frame.completionFence});if(i%10===9)await new Promise(resolve=>setTimeout(resolve,0));}rafCallbacks=qa.rafCallbacks-beforeRAF;
     }finally{qa.reinstall();}
     return {firstFrame:first,programsBefore,programsAfterFirst,programsAfterWarmup:qa.programs.length,values,probeDraw,rafCallbacks,stats:api.stats(backend),contexts:qa.stats()};
    },{backend,warmup:WARMUP,samples:SAMPLES});
    const index=measurement.contexts.findIndex(c=>c.canvas===backend+'-canvas');assert(index>=0);
    assertHealthy(measurement.contexts);
    const actual=measurement.probeDraw.contexts[index];assert(actual?.drawCalls>0&&actual.triangles>0,'Untimed native scene probe must draw real geometry');
    assert.equal(actual.completionReadbacks,2,'Native frame must drain previous work and complete current work with a pixel readback');assert.equal(actual.readbackBytes,8,'Matched two 1px RGBA8 completion readbacks per frame');
    assert(Object.keys(measurement.probeDraw.contexts).every(key=>Number(key)===index),'No background backend draw during measurement');
    assert.equal(measurement.rafCallbacks,0,'Automatic RAF must remain frozen during timed sampling');
    assert.equal(measurement.stats.actorCount??measurement.stats.count,count,'Real backend actor count');assert.equal(actual.triangles,fixture.triangles*count+2,'Full source mesh and one 2-triangle floor; no LOD reduction');
    for(const field of ['cpuUpdateMs','submitMs','completedFrameMs'])assert(measurement.values.every(v=>Number.isFinite(v[field])&&v[field]>=0),'Required timing '+field);
    const item={backend,count,trial:trial+1,order:trial%2?['three','custom']:BACKENDS,warmupFrames:WARMUP,untimedProbeAfterReload:measurement.firstFrame,nativeGLTiming:true,automaticRAFCallbacks:measurement.rafCallbacks,shaderPrograms:{before:measurement.programsBefore,afterProbe:measurement.programsAfterFirst,afterWarmup:measurement.programsAfterWarmup},
     cpuUpdate:summary(measurement.values.map(v=>v.cpuUpdateMs)),submit:summary(measurement.values.map(v=>v.submitMs)),completedFrame:summary(measurement.values.map(v=>v.completedFrameMs)),
     rawSamples:measurement.values.map(v=>({cpuUpdateMs:v.cpuUpdateMs,submitMs:v.submitMs,completedFrameMs:v.completedFrameMs,completionFence:v.completionFence})),drawCalls:[actual.drawCalls],triangles:[actual.triangles],boneUploads:{uniformBytes:actual.boneUniformUploadBytes,floatTextureBytes:actual.floatTextureUploadBytes},completionReadbacks:{calls:actual.completionReadbacks,totalBytes:actual.readbackBytes,currentFrameTimedBytes:4,previousFrameDrainTimed:false},stats:measurement.stats,context:measurement.contexts[index]};
    result.trials.push(item);console.log(JSON.stringify({progress:'benchmark',backend,count,trial:trial+1,completedFrame:item.completedFrame,drawCalls:item.drawCalls,triangles:item.triangles}));
   }
  }
  result.summary=[];for(const count of [1,22])for(const backend of BACKENDS){const runs=result.trials.filter(t=>t.backend===backend&&t.count===count);result.summary.push({backend,count,cpuUpdate:summary(runs.flatMap(r=>r.rawSamples.map(s=>s.cpuUpdateMs))),submit:summary(runs.flatMap(r=>r.rawSamples.map(s=>s.submitMs))),completedFrame:summary(runs.flatMap(r=>r.rawSamples.map(s=>s.completedFrameMs))),drawCalls:runs[0].drawCalls,triangles:runs[0].triangles});}
  result.finalStats=await page.evaluate(()=>({custom:window.TribunInteropLab.stats('custom'),three:window.TribunInteropLab.stats('three')}));
  result.shaderPrograms=await page.evaluate(()=>window.__gltfQA.programs);assert(result.shaderPrograms.some(p=>p.dualQuaternion),'Linked custom DQS shader');assert(result.shaderPrograms.some(p=>p.linearBlend),'Linked Three LBS shader');
  result.shaderFailures=await page.evaluate(()=>window.__gltfQA.shaderFailures);assert.deepEqual(result.shaderFailures,[],'No failed shader compilation or linking');
  result.textureUploads=await page.evaluate(()=>window.__gltfQA.textureUploads);for(let index=0;index<adapters.length;index++)assert(result.textureUploads.filter(t=>t.context===index&&t.width===256&&t.height===256&&t.type===5121).length>=2,'Both decoded 256px source maps must actually upload to '+adapters[index].canvas);
  result.errors=record.errors;assert.deepEqual(record.errors,[],'Normal comparison JavaScript errors');
  result.consoleErrors=record.consoleErrors;assert.deepEqual(record.consoleErrors,[],'Normal comparison console errors');
  const externalRequests=record.requests.filter(url=>/^https?:/.test(url)&&new URL(url).origin!==base);assert.deepEqual(externalRequests,[],'No CDN or other remote asset requests');
  assert.deepEqual(record.failed,[],'Normal comparison failed requests');assert(record.responses.every(r=>r.status<400),'Normal comparison HTTP resource errors');
  result.network={requests:record.responses.map(r=>({path:new URL(r.url).pathname,status:r.status})),failed:record.failed,externalRequests};
  return result;
 }finally{await record.context.close();}
}

async function coldEvidence(browser,base,fixture){const out=[];for(const backend of BACKENDS){const record=await prepare(browser,base);try{const before=record.responses.length,start=performance.now(),loaded=await load(record.page,backend,'/'+FIXTURE);const wallMs=performance.now()-start,metadata=assertReady(loaded,fixture),firstFrame=await record.page.evaluate(name=>{const qa=window.__gltfQA;qa.uninstall();try{return window.TribunInteropLab.frame({backend:name,clip:'idle',time:.15});}finally{qa.reinstall();}},backend),resources=await record.page.evaluate(()=>performance.getEntriesByType('resource').filter(r=>/footballer\.blender|blob:/.test(r.name)).map(r=>({name:r.name,duration:r.duration,transferSize:r.transferSize,encodedBodySize:r.encodedBodySize,decodedBodySize:r.decodedBodySize})));assert.deepEqual(record.errors,[]);out.push({backend,kind:'Fresh browser context; module imports complete; first uncached asset fetch/parse/texture readiness. Custom shader creation may occur in load; Three may compile lazily on first frame.',wallMs,firstFrameAfterLoad:firstFrame,metadata:statusRecord(metadata),resources,requests:record.responses.slice(before).map(r=>({path:new URL(r.url).pathname,status:r.status}))});}finally{await record.context.close();}}return out;}

async function faultEvidence(browser,base){
 const cases=['main-404','corrupt','buffer-404','texture-404','unsupported-extension','timeout','cancel'],out=[];
 for(const backend of BACKENDS)for(const fault of cases){const record=await prepare(browser,base),{page}=record;let release;
  try{
   let url='/'+FIXTURE,options={};
   if(fault==='main-404')url='/assets/interchange/does-not-exist.glb';
   if(fault==='corrupt')await page.route('**/'+FIXTURE,route=>route.fulfill({status:200,contentType:'model/gltf-binary',body:'broken GLB'}));
   if(fault==='buffer-404'||fault==='texture-404'){url='/'+EXTERNAL;const target=fault==='buffer-404'?'**/footballer.blender.bin':'**/textures/skin-detail.png';await page.route(target,route=>route.fulfill({status:404,body:'not found'}));}
   if(fault==='unsupported-extension'){url='/'+EXTERNAL;const json=JSON.parse(fs.readFileSync(path.join(ROOT,EXTERNAL),'utf8'));json.extensionsRequired=['QA_unsupported_required_extension'];await page.route('**/'+EXTERNAL,route=>route.fulfill({status:200,contentType:'model/gltf+json',body:JSON.stringify(json)}));}
   if(fault==='timeout'||fault==='cancel'){options.timeoutMs=fault==='timeout'?40:12000;let releaseRoute;const gate=new Promise(resolve=>{releaseRoute=resolve;});release=releaseRoute;await page.route('**/'+FIXTURE,async route=>{await gate;try{await route.fulfill({status:200,contentType:'model/gltf-binary',body:fs.readFileSync(path.join(ROOT,FIXTURE))});}catch{}});}
   const result=await page.evaluate(async({backend,url,options,cancel})=>{const controller=new AbortController(),start=performance.now();if(cancel)setTimeout(()=>controller.abort(),25);try{await window.TribunInteropLab.load({backend,url,count:1,...options,signal:controller.signal});return {resolved:true,elapsedMs:performance.now()-start,stats:window.TribunInteropLab.stats(backend)};}catch(error){return {resolved:false,message:error.message,code:error.code,stage:error.stage,url:error.url,elapsedMs:performance.now()-start,stats:window.TribunInteropLab.stats(backend)};}},{backend,url,options,cancel:fault==='cancel'});
   assert.equal(result.resolved,false,backend+' '+fault+' must reject');assert.equal(result.stats.status,'error',backend+' '+fault+' must publish terminal error');assert(result.message,'Readable failure');
   const expected={ 'main-404':['GLTF_HTTP','fetch'],'buffer-404':['GLTF_HTTP','buffer'],'texture-404':['GLTF_HTTP','image'],'unsupported-extension':['GLTF_EXTENSION','document'],'timeout':['GLTF_TIMEOUT','timeout'],'cancel':['GLTF_ABORTED','cancel'] }[fault];
   if(expected){assert.equal(result.code,expected[0],fault+' error code');assert.equal(result.stage,expected[1],fault+' error stage');}else assert.equal(result.stage,'document','Corrupt container fails document parsing');
   if(fault==='timeout'||fault==='cancel')assert(result.elapsedMs<1500,'Timeout/AbortSignal must act promptly, rather than falling back to default timeout');
   if(fault==='main-404')assert(result.url.endsWith('/does-not-exist.glb'));if(fault==='buffer-404')assert(result.url.endsWith('/footballer.blender.bin'));if(fault==='texture-404')assert(result.url.endsWith('/skin-detail.png'));
   const visible=await page.evaluate(name=>({state:document.getElementById(name+'-status').dataset.state,text:document.getElementById(name+'-message').textContent}),backend);assert.equal(visible.state,'error','Visible fault state');assert(visible.text.trim(),'Visible diagnostic message');
   assert.deepEqual(record.errors,[],'Handled fault should not throw unhandled JavaScript error');out.push({backend,fault,...result,visible,network:record.responses.map(r=>({path:new URL(r.url).pathname,status:r.status})),requestFailures:record.failed});console.log(JSON.stringify({progress:'fault',backend,fault,code:result.code,message:result.message}));
  }finally{release?.();await record.context.close();}
 }
 const record=await prepare(browser,base);try{const json=JSON.parse(fs.readFileSync(path.join(ROOT,EXTERNAL),'utf8'));json.materials[0].pbrMetallicRoughness.metallicFactor=.5;await record.page.route('**/'+EXTERNAL,route=>route.fulfill({status:200,contentType:'model/gltf+json',body:JSON.stringify(json)}));const three=await load(record.page,'three','/'+EXTERNAL);assert.equal(three.stats.status,'ready');assert(three.metadata.materials.some(m=>m.metalness===.5),'Three preserves authored metallic material');const custom=await record.page.evaluate(async url=>{try{await window.TribunInteropLab.load({backend:'custom',url,count:1});return {resolved:true};}catch(error){return {resolved:false,message:error.message,code:error.code,stage:error.stage,stats:window.TribunInteropLab.stats('custom')};}},'/'+EXTERNAL);assert.equal(custom.resolved,false);assert.match(custom.message,/metallic/i);assert.equal(custom.stats.status,'error');assert.deepEqual(record.errors,[]);out.push({backend:'custom-versus-three',fault:'valid-standard-metallic-material',three:three.metadata,custom});}finally{await record.context.close();}return out;
}
async function main(){
 assert(WARMUP>=30&&SAMPLES>=60&&TRIALS>=3,'Evidence requires >=30warmup,60samples,3alternatingtrials');fs.mkdirSync(path.dirname(REPORT),{recursive:true});fs.mkdirSync(PREVIEWS,{recursive:true});
 const fixture=fixtureEvidence(),sources=sourceHashes(),server=createServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||'/usr/bin/chromium',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-gpu-sandbox','--disable-background-timer-throttling']});
 try{
  const report={schemaVersion:1,generatedAt:new Date().toISOString(),kind:'Actual local-browser prototype comparison; readback-inclusive serial completed-frame latency on software WebGL; not real-device FPS or a pure engine speed comparison.',
   method:{fixture:'Same Blender-exported GLB and exact clip times, full source geometry, same camera/drawing buffer/DPR, independent WebGL contexts, no rAF/adaptive quality/LOD. Actual GL draw instrumentation and framebuffer reads; no mocked scene or animation.',warmupFrames:WARMUP,samplesPerTrial:SAMPLES,trials:TRIALS,counts:[1,22],resolution:[600,560],pixelRatio:1,measurement:'cpuUpdateMs measures animation/pose update; submitMs measures GL submission; completedFrameMs includes update + submit + gl.finish + synchronous 1x1 RGBA8 readPixels. A separate identical readback drains the previous frame before the timer. First frame and load are separate from warmed samples.',completionFence:'A native 1px RGBA8 readPixels is required. Diagnostic testing found gl.finish alone returned in 0.5–3.4ms while a following readPixels still waited 27–81ms on this Chromium/SwiftShader adapter.',limitations:['DQS custom versus LBS Three can produce different skin surfaces with matching bone matrices.','Custom uses one combined material-ID draw per actor; Three renders ten glTF material primitives.','PBR BRDF/tone mapping and material coverage differ despite matched inputs; screenshots require human judgment.','Completed-frame latency includes a 4-byte synchronous readback and driver/browser synchronization; it is not a GPU timer.','SwiftShader serial latency does not predict hardware throughput or device FPS.']},fixture,sources};
  report.coldLoads=await coldEvidence(browser,base,fixture);report.normal=await normalEvidence(browser,base,fixture);report.faults=await faultEvidence(browser,base);
  assert.deepEqual(sourceHashes(),sources,'Sources changed during evidence run; rerun on stable source');
  report.sourceHashesUnchanged=true;fs.writeFileSync(REPORT,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({report:path.relative(ROOT,REPORT),poseChecks:report.normal.poses.length,faults:report.faults.length,summaries:report.normal.summary}));
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
}
module.exports={summary,parseGLB,fixtureEvidence,INSTRUMENT,pixelDifference,expectedBones};
if(require.main===module)main().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
