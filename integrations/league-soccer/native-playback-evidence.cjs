'use strict';
// Browser's played TimeRanges provide media coverage, not unique renderer FPS.
function coverage(d,minSeconds){
 if(!Number.isFinite(minSeconds)||minSeconds<=0||minSeconds>900)throw Error('Invalid expected duration');
 const final=Number(d.finalMediaEnd);
 if(!Number.isFinite(final)||final<=0||final>1000)throw Error('Missing final media end');
 const ranges=d.played;
 if(!Array.isArray(ranges)||ranges.length>500)throw Error('Invalid played ranges');
 let seconds=0,previous=0;
 for(const row of ranges){
  if(!Array.isArray(row)||row.length!==2||!row.every(Number.isFinite)||row[0]<0||row[1]<row[0]||row[0]<previous-.001||row[1]>final+.5)throw Error('Invalid played timeline');
  seconds+=Math.max(0,row[1]-Math.max(row[0],previous));previous=Math.max(previous,row[1]);
 }
 const skipped=d.automaticSkippedSeconds;
 if(!Number.isFinite(skipped)||skipped<0)throw Error('Invalid skip telemetry');
 const initial=d.initialSeekSeconds;
 const checks={ended:d.ended===true&&d.phase==='ended',playlistComplete:d.playlistComplete===true,
  nearBeginning:d.firstSegment===0&&Number.isFinite(initial)&&initial<1,
  nearEnd:Math.abs(d.currentTime-final)<=.5,
  sufficientCoverage:seconds>=Math.max(minSeconds*.95,final*.95),
  boundedAutomaticSkip:skipped<=Math.max(1,minSeconds*.02),
  decodedVideo:Number.isFinite(d.decodedFrames)&&d.decodedFrames>0&&d.videoWidth>0&&d.videoHeight>0,
  noMediaError:d.mediaError===null&&!d.playError};
 return {passed:Object.values(checks).every(Boolean),checks,ended:d.ended,playlistComplete:d.playlistComplete,playedSeconds:seconds,finalMediaEnd:final,
  coverageFraction:seconds/final,automaticSeeks:d.automaticSeeks,automaticSkippedSeconds:skipped,waitingEvents:d.waitingEvents,stallEvents:d.stallEvents,
  decodedFrames:d.decodedFrames,droppedFrames:d.droppedFrames,videoWidth:d.videoWidth,videoHeight:d.videoHeight,
  note:'Browser played ranges and decoded frame counters; not exact native renderer FPS, network SLA or subjective visual quality.'};
}
module.exports={coverage};
