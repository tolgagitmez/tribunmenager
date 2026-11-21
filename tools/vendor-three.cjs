'use strict';
// Copy a minimal, pinned official Three.js module closure for offline serving.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),source=path.join(root,'node_modules/three');
const pkg=JSON.parse(fs.readFileSync(path.join(source,'package.json')));
if(pkg.version!=='0.180.0')throw Error('Expected pinned three@0.180.0; run npm ci first');
const names=['LICENSE','build/three.module.min.js','build/three.core.min.js','examples/jsm/loaders/GLTFLoader.js','examples/jsm/utils/BufferGeometryUtils.js','examples/jsm/utils/SkeletonUtils.js','examples/jsm/controls/OrbitControls.js'];
const files=names.map(name=>{const target=path.join(root,'vendor/three',name),data=fs.readFileSync(path.join(source,name));fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,data);return {path:path.relative(root,target).split(path.sep).join('/'),bytes:data.length,sha256:crypto.createHash('sha256').update(data).digest('hex')};}).sort((a,b)=>a.path.localeCompare(b.path,'en'));
const locked=JSON.parse(fs.readFileSync(path.join(root,'package-lock.json'))).packages['node_modules/three'];
const manifest={package:'three',version:pkg.version,license:'MIT',source:locked.resolved,npmIntegrity:locked.integrity,files};
fs.writeFileSync(path.join(root,'vendor/three/manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({version:pkg.version,files:files.length,bytes:files.reduce((sum,file)=>sum+file.bytes,0)}));
