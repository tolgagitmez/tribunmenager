"""Private Xvfb test of untouched upstream match presentation.
Run only inside a disposable Xvfb display, with upstream's own smoke config.
No footage is stored; measure capture delivery and pixel changes, not engine FPS.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time

import original_engine as engine

WIDTH, HEIGHT = 320, 256
FRAME_BYTES = WIDTH * HEIGHT
REQUEST_FPS = 30
ACTIVE = '[menu-smoke] Gameplay page reached and live match is active'
HALF = '[menu-smoke] Continuing second half automatically'
FULL = '[menu-smoke] Full match complete:'
DONE = '[menu-smoke] Full-match verification succeeded, quitting test run'


def repeated_pixels(frames):
    """Observed identical hashes only; do not bridge missing samples."""
    longest=0.0
    covered=0.0
    runs=0
    start=None
    for (ta,ha),(tb,hb) in zip(frames,frames[1:]):
        gap=tb-ta
        if ha==hb and 0<=gap<=0.25:
            if start is None:
                start=ta
            covered+=gap
            longest=max(longest,tb-start)
        elif start is not None:
            if ta-start>=1:
                runs+=1
            start=None
    if start is not None and frames[-1][0]-start>=1:
        runs+=1
    return longest,covered,runs


def summarize(samples, intervals):
    """Samples are (monotonic receipt time, frame digest). Intervals exclude menus."""
    if (not intervals or any(not math.isfinite(a) or not math.isfinite(b) or b<=a for a,b in intervals)
            or any(a[1]>b[0] for a,b in zip(intervals,intervals[1:]))):
        raise ValueError('Missing valid active-match intervals')
    if (any(not math.isfinite(t) for t,_ in samples)
            or any(b[0]<a[0] for a,b in zip(samples,samples[1:]))):
        raise ValueError('Nonmonotonic capture receipt times')
    count=changed=0
    max_gap=0.0
    static_max=static_coverage=0.0
    static_runs=0
    gaps=0
    seconds=sum(b-a for a,b in intervals)
    per_half=[]
    for start,end in intervals:
        frames=[(t,h) for t,h in samples if start<=t<end]
        n=len(frames)
        c=sum(a[1]!=b[1] for a,b in zip(frames,frames[1:]))
        same_max,same_coverage,same_runs=repeated_pixels(frames)
        static_max=max(static_max,same_max)
        static_coverage+=same_coverage
        static_runs+=same_runs
        times=[start]+[t for t,_ in frames]+[end]
        delays=[b-a for a,b in zip(times,times[1:])]
        longest=max(delays)
        count+=n
        changed+=c
        max_gap=max(max_gap,longest)
        gaps+=sum(d>=1 for d in delays)
        per_half.append(dict(seconds=round(end-start,3),samples=n,changedTransitions=c,
                             captureReceiptFps=round(n/(end-start),2),maxReceiptGapMs=round(longest*1000,1),
                             changedTransitionsPerSecond=round(c/(end-start),2),
                             identicalTransitions=max(0,n-1-c),
                             longestIdenticalPixelSpanMs=round(same_max*1000,1),
                             observedIdenticalPixelSpanSeconds=round(same_coverage,3),
                             identicalPixelRunsAtLeastOneSecond=same_runs,
                             observedMotion=c>0,
                             deliveryTargetMet=n/(end-start)>=24 and longest<1))
    return dict(activeWindowSeconds=round(seconds,3),captureSamples=count,
                captureReceiptFps=round(count/seconds,2),
                changedFrameTransitions=changed,changedTransitionsPerSecond=round(changed/seconds,2),
                identicalTransitions=sum(h['identicalTransitions'] for h in per_half),
                longestIdenticalPixelSpanMs=round(static_max*1000,1),
                observedIdenticalPixelSpanSeconds=round(static_coverage,3),
                identicalPixelRunsAtLeastOneSecond=static_runs,
                pixelContinuityScope='Exact sampled grayscale hashes; spans exclude gaps over 250 ms; not native render or simulation freeze proof.',
                longestReceiptGapMs=round(max_gap*1000,1),receiptGapsAtLeastOneSecond=gaps,
                halves=per_half,hasObservedMotion=changed>0,
                evidencePassed=seconds>=1 and all(h['samples']>=2 and h['observedMotion'] for h in per_half),
                deliveryQualityPassed=seconds>=1 and all(h['observedMotion'] and h['deliveryTargetMet'] for h in per_half),
                deliveryTarget=dict(minReceiptFpsPerHalf=24,maxReceiptGapExclusiveMs=1000),
                scope='External sampled Xvfb pixels at requested 30Hz; callback/pipe receipt timing, '
                      'not native FPS, unique rendered frames, browser screen-share or physics stall proof.')


def calibrate_capture(samples, env):
    """Compare known externally drawn motion against the same capture pipe."""
    pattern=Path(__file__).resolve().with_name('original_capture_pattern.py')
    proc=subprocess.run(['python3',str(pattern)],env=env,capture_output=True,
                        text=True,timeout=20,check=True)
    drawn=json.loads(proc.stdout)
    start,end=drawn['start'],drawn['end']
    report=summarize(list(samples),[(start+0.5,end-0.5)])
    report['referenceDrawCalls']=drawn['drawnFrames']
    report['referenceDrawCallsPerSecond']=round(drawn['drawnFrames']/(end-start),2)
    report['calibrationPassed']=(report['deliveryQualityPassed']
        and report['changedTransitionsPerSecond']>=20
        and report['referenceDrawCallsPerSecond']>=24)
    return report


def optional_diagnostic(args, env):
    try:
        p=subprocess.run(args,env=env,capture_output=True,text=True,timeout=5)
        return dict(exitCode=p.returncode,output=p.stdout.strip()[:4000])
    except (OSError,subprocess.TimeoutExpired) as exc:
        return dict(error=str(exc))


def match_capture(session, source, env):
    samples=[]
    events=[]
    errors=[]
    window_info={}
    graphics=optional_diagnostic(['glxinfo','-B'],env)
    def read_frames(pipe):
        try:
            while True:
                data=pipe.read(FRAME_BYTES)
                if not data:
                    break
                if len(data)!=FRAME_BYTES:
                    raise RuntimeError('Partial raw video frame')
                samples.append((time.monotonic(),hashlib.blake2s(data,digest_size=12).hexdigest()))
        except Exception as exc:
            errors.append(str(exc))

    # Dedicated display is created by the caller; no real desktop captured.
    display=env.get('DISPLAY','')
    if not display.startswith(':') or not display[1:].split('.')[0].isdigit():
        raise RuntimeError('Expected private Xvfb display')
    with tempfile.TemporaryFile() as capture_log, tempfile.TemporaryFile() as game_log:
        capture=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-f','x11grab',
            '-draw_mouse','0','-framerate',str(REQUEST_FPS),'-video_size','1280x1024','-i',display,
            '-vf',f'scale={WIDTH}:{HEIGHT}:flags=fast_bilinear,format=gray',
            '-threads','1','-vsync','0','-f','rawvideo','pipe:1'],
            env=env,stdout=subprocess.PIPE,stderr=capture_log)
        worker=threading.Thread(target=read_frames,args=(capture.stdout,),daemon=True)
        worker.start()
        game=None
        try:
            # Prove capture readiness before starting the game.
            deadline=time.monotonic()+15
            while not samples and capture.poll() is None and time.monotonic()<deadline:
                time.sleep(.05)
            if not samples:
                raise RuntimeError('Xvfb capture produced no frames')
            calibration=calibrate_capture(samples,env)
            print('Capture calibration: '+json.dumps(calibration),flush=True)
            if capture.poll() is not None:
                raise RuntimeError('Capture ended during reference calibration')
            game=subprocess.Popen(['stdbuf','-oL','-eL',str(session/'gameplayfootball'),
                str(source/'data/menu_smoke_full_match.config')],cwd=session,env=env,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            def read_game():
                for line in game.stdout:
                    game_log.write(line.encode())
                    for marker in (ACTIVE,HALF,FULL,DONE):
                        if marker in line:
                            events.append((time.monotonic(),marker,line.strip()))
            logger=threading.Thread(target=read_game,daemon=True)
            logger.start()
            deadline=time.monotonic()+420
            while game.poll() is None and time.monotonic()<deadline:
                if not window_info and any(m==ACTIVE for _,m,_ in events):
                    window_info=optional_diagnostic(['xwininfo','-name','League Soccer'],env)
                time.sleep(.1)
            code=game.wait(timeout=max(1,deadline-time.monotonic()))
            logger.join(timeout=10)
            if logger.is_alive() or code:
                raise RuntimeError('Native smoke game did not finish normally')
            if capture.poll() is not None:
                capture_log.seek(0)
                raise RuntimeError('Capture ended before the match completed: '+capture_log.read(4096).decode(errors='replace'))
        finally:
            if game is not None and game.poll() is None:
                game.kill();game.wait()
            capture.terminate()
            try:
                capture.wait(timeout=10)
            except subprocess.TimeoutExpired:
                capture.kill();capture.wait()
            worker.join(timeout=10)
        if errors or worker.is_alive():
            raise RuntimeError('Capture read failed: '+str(errors))
        if [m for _,m,_ in events]!=[ACTIVE,HALF,ACTIVE,FULL,DONE]:
            raise RuntimeError('Unexpected native smoke markers: '+str(events))
        intervals=[(events[0][0],events[1][0]),(events[2][0],events[3][0])]
        result=summarize(samples,intervals)
        result.update(captureCalibration=calibration,graphicsEnvironment=graphics,
                      nativeWindowDiagnostic=window_info,
                      calibrationComparisonScope='Tk reference window checks sampling path, not OpenGL rendering or GPU performance.',
                      revision=engine.REVISION,fixture='upstream menu_smoke_full_match.config',
                      fullTimeMarker=events[3][2],requestedCaptureFps=REQUEST_FPS,
                      sampledResolution=[WIDTH,HEIGHT],nativeSettingsPatched=False,
                      smokeFixtureUsesAcceleratedClock=True,browserPreviewVerified=False)
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--inside-private-xvfb',action='store_true')
    a=p.parse_args()
    if not a.inside_private_xvfb:
        # Always create a fresh display, never attach to the caller's desktop.
        engine.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                     'python3',Path(__file__).resolve(),a.output.resolve(),'--inside-private-xvfb'],
                    engine.clean_env(os.environ))
        return 0
    env=engine.clean_env(os.environ)
    work=engine.cache_root()/engine.REVISION
    build=engine.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='native-capture-smoke-') as d:
        session=Path(d)
        for name in engine.RUNTIME:
            p=build/name
            if p.is_dir():
                shutil.copytree(p,session/name)
            else:
                shutil.copy2(p,session/name)
        result=match_capture(session,work/'source',env)
    engine.verify_install(work,env)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0 if result['evidencePassed'] else 2


if __name__=='__main__':
    raise SystemExit(main())
