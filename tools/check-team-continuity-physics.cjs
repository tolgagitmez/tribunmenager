#!/usr/bin/env node
'use strict';
// Source protection complements the live-step regression tests; it does not
// claim that changed intentions will produce identical complete matches.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),Module=require('node:module'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const before=zlib.gunzipSync(fs.readFileSync(path.join(root,'docs/validation/baselines/stage8-football-sim.js.gz')));
assert.equal(hash(before),'e16642b50e1d0b7d31cdc375dea7a83af85cf3da194a28362b65007f8420ad2e');
const filename=path.join(root,'continuity-physical-baseline.js'),baseline=new Module(filename,module);baseline.filename=filename;baseline.paths=module.paths;baseline._compile(before.toString(),filename);
const current=require('../football-sim'),protectedMethods=['move','effort','contactPoint','touchContact','touchPlan','firstControlContact','tackleAccess','doTackle','integrateBall','ballStep','release','kickStep','keeper','keeperVisibility','offsideTouch','receiverInterceptPoint'];
const methods=protectedMethods.map(name=>{const previous=baseline.exports.Match.prototype[name],next=current.Match.prototype[name];assert.equal(typeof next,'function',name);assert.equal(next.toString(),previous.toString(),name+' physical implementation changed');return {name,sha256:hash(next.toString()),identical:true};});
const physics=value=>Object.fromEntries(Object.entries(value).map(([key,value])=>[key,typeof value==='function'?value.toString():value]));
assert.deepEqual(physics(current.BallPhysics),physics(baseline.exports.BallPhysics));
const files=['football-sim.js','player-perception.js','team-intent.js','tests/touch-feasibility.test.cjs','tests/team-continuity-integration.test.cjs',path.relative(root,__filename)];
const report={baseline:hash(before),sources:Object.fromEntries(files.map(file=>[file,hash(fs.readFileSync(path.join(root,file)))])),method:'Exact source equality for BallPhysics and the named live movement/contact/release/referee/keeper methods against the retained published stage8 source. The stage9 test suite separately checks actual frames, physical intervention and prediction purity. Tactical intentions, observations and their preparation forecasts deliberately change.',ballPhysicsIdentical:true,methods,verified:true};
fs.writeFileSync(path.join(root,'docs/validation/team-continuity-physics.json'),JSON.stringify(report,null,2)+'\n');
process.stdout.write(JSON.stringify({verified:true,ballPhysicsIdentical:true,protectedMethods:methods.length})+'\n');
