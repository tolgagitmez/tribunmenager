'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),L=require('./native-live-video.js');
test('restricted sequential media playlist',()=>{
 const head='#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-MAP:URI="init.mp4"\n';
 assert.deepEqual(L.playlist(head+'#EXTINF:2,\nsegment-00000.m4s\n#EXT-X-ENDLIST'),{files:['segment-00000.m4s'],done:true});
 for(const bad of ['../evil.m4s','https://example.com/evil.m4s','segment-00001.m4s','#EXT-X-KEY:METHOD=AES-128'])assert.throws(()=>L.playlist(head+bad));
});
test('derive exact H.264 codec from AVC configuration',()=>{
 const box=Uint8Array.from([0,0,0,0,0,0,0,15,97,118,99,67,1,66,192,31,0,0,0]);
 assert.equal(L.codec(box),'video/mp4; codecs="avc1.42c01f"');
 assert.equal(L.codec(box,true),'video/mp4; codecs="avc1.42c01f,mp4a.40.2"');
 assert.throws(()=>L.codec(new Uint8Array(20)));
});

test('prebuffer before play and recover a disjoint or stale range',()=>{
 assert.deepEqual(L.bufferDecision([[0,2]],0,false,false),{start:false,seek:.03});
 assert.equal(L.bufferDecision([[0,4]],0,false,false).start,true);
 assert.equal(L.bufferDecision([[0,1]],0,false,true).start,true);
 assert.equal(L.bufferDecision([[0,2],[5,9]],3,true,false).seek,6);
 assert.equal(L.bufferDecision([[0,9]],5,true,false).seek,null);
});

test('live edge does not jump backwards; completed stream is not fast-forwarded',()=>{
 assert.equal(L.bufferDecision([[0,6]],6.2,true,false).seek,null);
 assert.equal(L.bufferDecision([[0,20]],2,true,true).seek,null);
 assert.equal(L.bufferDecision([[0,20]],2,true,false).seek,17);
 assert.ok(L.bufferDecision([[0,2],[5,6]],3,true,true).seek>=5);
});
