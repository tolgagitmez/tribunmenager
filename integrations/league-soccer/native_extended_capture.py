"""Private extended native capture; clock observations are not exact media alignment."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

from native_extended_clock_verify import verify, DURATION
from native_media_retime import probe, duration
from native_audio_capture import pcm_metrics

HERE=Path(__file__).resolve().parent


def require(ok,message):
    if not ok:
        raise ValueError(message)


def capture_env(source,video):
    env={k:v for k,v in source.items() if not k.startswith(('TRIBUN_','GF_CAPTURE_'))}
    env.update(TRIBUN_NATIVE_VIDEO_OUT=str(video.resolve()),
        TRIBUN_NATIVE_REALTIME='1',TRIBUN_NATIVE_FIXED_DURATION='1',
        TRIBUN_NATIVE_CLOCK_SCALE='1.0',TRIBUN_NATIVE_EXTENDED_MATCH='1',
        TRIBUN_NATIVE_EXTENDED_CAPTURE='1',TRIBUN_NATIVE_AUDIO_CAPTURE='1',
        TRIBUN_LEAGUE_SOCCER_ATTACK='baseline',LIBGL_ALWAYS_SOFTWARE='1',
        LP_NUM_THREADS='2')
    for key in ('SDL_VIDEODRIVER','SDL_AUDIODRIVER','LD_PRELOAD'):
        env.pop(key,None)
    return env


def finite(v):
    return type(v) in (int,float) and math.isfinite(v)


def assess(capture,observations,video_seconds,audio_seconds,expected_ms=DURATION):
    first,kickoff,final=(capture.get(k) for k in
        ('firstEncodedObserved','kickoffObserved','finalObserved'))
    launch=observations.get('encoderLaunchMonotonic')
    stop=observations.get('encoderStopRequestedMonotonic')
    require(all(finite(v) for v in (first,kickoff,final,launch,stop,video_seconds,audio_seconds)),
            'Missing observed capture clocks')
    require(launch<=first<=stop and launch<=kickoff<final<=stop,
            'Invalid observed capture clock order')
    samples=observations.get('samples')
    require(isinstance(samples,list) and len(samples)>=2,'Missing native clock observations')
    previous_native=-1
    previous_wall=launch
    residuals=[]
    maximum_gap=0
    for s in samples:
        n,w=s.get('nativeMs'),s.get('observedMonotonic')
        require(type(n) is int and previous_native<=n<=expected_ms and
                finite(w) and previous_wall<=w<=stop,'Invalid native clock observation')
        if previous_native>=0:
            maximum_gap=max(maximum_gap,n-previous_native)
        residuals.append(abs((w-kickoff)*1000-n))
        previous_native,previous_wall=n,w
    wall=final-kickoff
    checks=dict(captureObservedBeforeKickoff=first<=kickoff,
        finalClockObserved=previous_native==expected_ms,
        nativeAudioOwned=capture.get('nativeSinkOwnershipVerified') is True and capture.get('audio') is True,
        mediaCoveragePlausible=min(video_seconds,audio_seconds)>=wall-.5,
        tracksDurationClose=abs(video_seconds-audio_seconds)<=.25)
    return dict(checks=checks,rawCoveragePassed=all(checks.values()),
        observedWallSeconds=round(wall,3),videoSeconds=video_seconds,audioSeconds=audio_seconds,
        maxNativeObservationGapMs=maximum_gap,
        maxObservedClockResidualMs=round(max(residuals),2),
        observationCount=len(samples),exactMediaAlignmentVerified=False,
        eligibleForAutomaticRetime=False,
        scope='Observed process clocks and duration only. No exact native-time to encoded-PTS mapping.')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path)
    p.add_argument('fixture',type=Path)
    p.add_argument('out',type=Path)
    p.add_argument('--private-diagnostic',action='store_true',required=True)
    a=p.parse_args()
    runtime,fixture,out=(x.resolve() for x in (a.runtime,a.fixture,a.out))
    require(fixture.is_file(),'Frozen JSON fixture required')
    out.mkdir(parents=True,exist_ok=False)
    video=out/'native-match.mp4'
    trace=out/'match.ndjson'
    report_path=out/'extended-capture-report.json'
    report=dict(schema=1,status='incomplete',productionEnabled=False,
                videoRedistributionApproved=False,eligibleForAutomaticRetime=False)
    def save():
        report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    save()
    with (out/'runner.log').open('wb') as log:
        subprocess.run(['bash',str(HERE/'run-frozen.sh'),str(runtime),str(fixture),str(trace),'0'],
            env=capture_env(os.environ,video),stdout=log,stderr=subprocess.STDOUT,
            check=True,timeout=3900)
    report['nativeClock']=verify(trace)
    v,au,fmt=probe(video)
    require(v.get('codec_name')=='h264' and au.get('codec_name')=='aac' and
            int(au['sample_rate'])==48000 and au['channels']==2,'Unexpected native media tracks')
    report.update(assess(json.loads(video.with_suffix('.capture.json').read_text()),
        json.loads(video.with_suffix('.clock-observations.json').read_text()),
        duration(v,fmt['duration']),duration(au,fmt['duration'])))
    proc=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-i',str(video),
        '-map','0:a:0','-ac','1','-ar','48000','-f','s16le','-'],
        stdout=subprocess.PIPE)
    try:
        with proc.stdout as f:
            report['audioEnergy']=pcm_metrics(f)
        require(proc.wait(timeout=30)==0,'Native audio decode failed')
    finally:
        if proc.poll() is None:
            proc.kill();proc.wait()
    report['traceSha256']=sha(trace)
    report['videoSha256']=sha(video)
    report['fixtureSha256']=sha(fixture)
    passed=report['rawCoveragePassed'] and report['audioEnergy']['nonSilentWindows']>=10
    report['status']='raw-capture-observed' if passed else 'raw-capture-inconclusive'
    save()
    print(json.dumps(report,indent=2))
    return 0 if passed else 2


if __name__=='__main__':
    raise SystemExit(main())
