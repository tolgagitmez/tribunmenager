const {test}=require('node:test');const assert=require('node:assert/strict');
const {route}=require('../native-league-transport.js');
test('only allowed same-origin media and tactics',()=>{
 assert.equal(route('tactics.json',3),'/api/league/native-av/tactics?round=3');
 assert.equal(route('segment-00001.m4s',3),'/api/league/native-av/media?round=3&file=segment-00001.m4s');
 for(const name of ['../key','https://example.com','local-url.txt'])assert.throws(()=>route(name,3));
 assert.throws(()=>route('init.mp4',null));
});
