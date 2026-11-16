'use strict';
/* Compare the complete football state under old and revised presentation rigs. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),zlib=require('node:zlib'),Module=require('node:module');
const root=path.resolve(__dirname,'..'),digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const baselinePath='docs/validation/baselines/licensed-character-rig-6ddd4f1.js.gz',baseline=zlib.gunzipSync(fs.readFileSync(path.join(root,baselinePath)));
assert.equal(digest(baseline),'2c024a0fd130d50baa04533ae255a8f72b7dc93c269ef3d0af86ae6771820b3d');
const oldModule=new Module(path.join(root,'character-baseline-motion.js'),module);oldModule.filename=path.join(root,'character-baseline-motion.js');oldModule._compile(baseline.toString(),oldModule.filename);
const oldRig=oldModule.exports,Rig=require('../humanoid-rig'),{Match}=require('../football-sim'),Tactics=require('../tactics');
const sources=Object.fromEntries(['football-sim.js','humanoid-rig.js','tactics.js','player-model.js','player-model-profiles.js','player-model-profiles.json','player-perception.js','team-intent.js','match-rules.js','referee-laws.js','pitch-laws.js',baselinePath,'tools/check-character-physics.cjs'].map(p=>[p,digest(fs.readFileSync(path.join(root,p)))]));
assert.equal(sources['football-sim.js'],'315a732ed12eae6537f8790bd0095aad0e523e76aa8734303eacb48faeb017dd');
const snapshot=m=>structuredClone({...m,motion:null});
const configs=[{seed:21,matchMinutes:5},{seed:42,matchMinutes:5,tactics:Tactics.presets.find(p=>p.id==='press').tactics},{seed:77,matchMinutes:5,formation:'4-4-2'}];
const runs=[];
for(const config of configs){
 const a=new Match(config,oldRig),b=new Match(config,Rig);let ticks=0,comparisons=0;
 while(!a.done&&ticks<24000){
  a.step();b.step();ticks++;
  for(const p of a.players)if(p.active)oldRig.update(p,1/60);
  for(const p of b.players)if(p.active)Rig.update(p,1/60);
  if(ticks%120===0||a.done){assert.deepEqual(snapshot(a),snapshot(b),`seed${config.seed}/tick${ticks}: presentation rig changed complete physical state`);comparisons++;}
 }
 assert(a.done&&b.done,'Natural short match must complete including periods and added time');
 runs.push({seed:config.seed,ticks,completeStateComparisons:comparisons,elapsedSeconds:a.time,score:a.score,shots:a.shots,physicalStateEqual:true});
}
for(const [p,sha]of Object.entries(sources))assert.equal(digest(fs.readFileSync(path.join(root,p))),sha,'Source changed while comparing: '+p);
const report={generatedAt:new Date().toISOString(),sources,baselineCommit:'6ddd4f18b8ffb1789379fb8635dd37540983a952',baselineRigSHA256:digest(baseline),method:'Three natural 5-minute configurations, each run with the retained old rig and revised rig. Both rigs update every active player after each fixed physical step. Every two simulated seconds and at the end, complete own-state graphs are deeply compared, preserving object references, Maps and Sets. Only the immutable motion-module object is replaced with null for comparison; no player, ball, referee, RNG, task, perception, event or clock field is omitted.',runs,verified:true};
fs.writeFileSync(path.join(root,'docs/validation/character-physics.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({verified:true,naturalScenarios:runs.length,completeStateComparisons:runs.reduce((s,r)=>s+r.completeStateComparisons,0)}));
