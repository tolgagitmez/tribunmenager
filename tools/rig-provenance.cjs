'use strict';
// Historical generated model/Blender files keep their original hashes.
// Only explicitly reviewed runtime source is accepted, and the glTF test
// still compares the complete canonical baked GLB byte-for-byte.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const historicalSHA256='0dc472e9f489106eb32dfff97b9577861552470807eeeca665e45c2d44e862d7';
// Explicitly reviewed runtime-only recovery pose; historical bind and baked bytes still verified.
const reviewedRuntimeSHA256='af30606b8991fc2397e0853a8abf92a20e545270139098bff7ecbde0eff388ed';
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function verifyRigReference(expected){
 const historical=hash(fs.readFileSync(path.join(root,'assets/interchange/rig-reference.js')));
 if(expected!==historicalSHA256||historical!==historicalSHA256)throw Error('Historical canonical rig reference changed');
 const runtime=hash(fs.readFileSync(path.join(root,'humanoid-rig.js')));
 if(runtime!==historicalSHA256&&runtime!==reviewedRuntimeSHA256)throw Error('Unreviewed runtime rig revision');
 return historical;
}
module.exports={verifyRigReference,historicalSHA256,reviewedRuntimeSHA256};
