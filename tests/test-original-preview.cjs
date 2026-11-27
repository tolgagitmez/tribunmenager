'use strict';
const assert=require('node:assert/strict');
const {test}=require('node:test');
const {createPreview}=require('../original-preview.js');

function setup(surface='window'){
 const states=[];
 const track={stops:0,ended:null,getSettings:()=>({displaySurface:surface}),
  stop(){this.stops++;},addEventListener(name,fn){if(name==='ended')this.ended=fn;}};
 const stream={getVideoTracks:()=>[track],getTracks:()=>[track]};
 const video={srcObject:null,play:async()=>{}};
 const requests=[];
 const mediaDevices={getDisplayMedia:async options=>{requests.push(options);return stream;}};
 const preview=createPreview({mediaDevices,video,onState:s=>states.push(s)});
 return {states,track,stream,video,requests,mediaDevices,preview};
}

test('no capture before explicit start; local window playback and stop',async()=>{
 const s=setup();
 assert.equal(s.requests.length,0);
 assert.equal(await s.preview.start(),true);
 assert.equal(s.requests[0].video.displaySurface,'window');
 assert.equal(s.requests[0].audio,false);
 assert.equal(s.video.srcObject,s.stream);
 assert.equal(s.states.at(-1).state,'playing');
 assert.equal(await s.preview.start(),false);
 assert.equal(s.requests.length,1);
 s.preview.stop();
 assert.equal(s.track.stops,1);
 assert.equal(s.video.srcObject,null);
});

test('reject monitor, browser tab and unidentified display surface',async()=>{
 for(const surface of ['monitor','browser',null]){
  const s=setup(surface);
  assert.equal(await s.preview.start(),false);
  assert.equal(s.track.stops,1);
  assert.equal(s.video.srcObject,null);
  assert.equal(s.states.at(-1).state,'error');
 }
});

test('browser share ended releases the preview',async()=>{
 const s=setup();
 await s.preview.start();
 s.track.ended();
 assert.equal(s.video.srcObject,null);
 assert.equal(s.states.at(-1).state,'idle');
});

test('denied permission does not attach a stream',async()=>{
 const s=setup();
 s.mediaDevices.getDisplayMedia=async()=>{throw Object.assign(Error('denied'),{name:'NotAllowedError'});};
 assert.equal(await s.preview.start(),false);
 assert.equal(s.video.srcObject,null);
 assert.equal(s.states.at(-1).state,'error');
});

test('late permission after stop is discarded',async()=>{
 const s=setup();
 let resolve;
 s.mediaDevices.getDisplayMedia=()=>new Promise(r=>{resolve=r;});
 const pending=s.preview.start();
 s.preview.stop();
 resolve(s.stream);
 assert.equal(await pending,false);
 assert.equal(s.track.stops,1);
 assert.equal(s.video.srcObject,null);
 assert.equal(s.states.at(-1).state,'idle');
});

test('play failure releases tracks',async()=>{
 const s=setup();
 s.video.play=async()=>{throw Error('play failed');};
 assert.equal(await s.preview.start(),false);
 assert.equal(s.track.stops,1);
 assert.equal(s.video.srcObject,null);
});

test('unsupported browser remains idle until requested',async()=>{
 const states=[];
 const p=createPreview({mediaDevices:undefined,video:{},onState:s=>states.push(s)});
 assert.equal(p.supported,false);
 assert.equal(await p.start(),false);
 assert.equal(states.at(-1).state,'unsupported');
});
