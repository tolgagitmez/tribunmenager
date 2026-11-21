'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),manifest=JSON.parse(fs.readFileSync(path.join(root,'vendor/three/manifest.json')));
test('offline Three module closure matches the pinned official MIT package and local viewer import maps',()=>{
 const lock=JSON.parse(fs.readFileSync(path.join(root,'package-lock.json'))),installed=JSON.parse(fs.readFileSync(path.join(root,'node_modules/three/package.json')));
 assert.equal(manifest.version,'0.180.0');assert.equal(installed.version,manifest.version);assert.equal(manifest.npmIntegrity,lock.packages['node_modules/three'].integrity);assert.equal(manifest.license,'MIT');
 assert.equal(manifest.files.length,7);
 for(const item of manifest.files){
  assert(item.path.startsWith('vendor/three/')&&!item.path.split('/').includes('..'));
  const bytes=fs.readFileSync(path.join(root,item.path)),original=fs.readFileSync(path.join(root,'node_modules/three',item.path.slice('vendor/three/'.length)));
  assert.equal(bytes.length,item.bytes,item.path);assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),item.sha256,item.path);assert.deepEqual(bytes,original,item.path);
 }
 assert.match(fs.readFileSync(path.join(root,'vendor/three/LICENSE'),'utf8'),/Permission is hereby granted, free of charge/);
 for(const file of ['interop-lab.html','character-viewer.html']){
  const source=fs.readFileSync(path.join(root,file),'utf8'),match=source.match(/<script type="importmap">([\s\S]*?)<\/script>/);assert(match,file+' import map');
  const imports=JSON.parse(match[1]).imports;assert.equal(imports.three,'./vendor/three/build/three.module.min.js');assert.equal(imports['three/addons/'],'./vendor/three/examples/jsm/');
  assert(!source.includes('/node_modules/three/'),file+' must work under documented Python launcher without npm');
 }
});
