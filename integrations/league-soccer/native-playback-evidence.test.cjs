'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{coverage}=require('./native-playback-evidence.cjs');
const full={ended:true,phase:'ended',playlistComplete:true,firstSegment:0,initialSeekSeconds:.03,currentTime:309.3,finalMediaEnd:309.3,played:[[.03,309.3]],automaticSkippedSeconds:0,decodedFrames:7500,videoWidth:1280,videoHeight:720,mediaError:null};
test('actual end and played coverage required',()=>{
 assert.ok(coverage(full,300).passed);
 assert.equal(coverage({...full,played:[[.03,2],[300,309.3]]},300).passed,false);
 assert.equal(coverage({...full,ended:false},300).passed,false);
 assert.equal(coverage({...full,automaticSkippedSeconds:20},300).passed,false);
 assert.equal(coverage({...full,firstSegment:4},300).passed,false);
});
test('bad or absent range evidence is rejected',()=>{
 assert.throws(()=>coverage({...full,played:[[0,9],[1,15]]},300));
 assert.throws(()=>coverage({...full,finalMediaEnd:NaN},300));
 assert.equal(coverage({...full,decodedFrames:0},300).passed,false);
});
