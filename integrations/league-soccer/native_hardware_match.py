"""Explicit single-match dedicated-GPU and hardware-encoder diagnostic."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from native_gpu_display import local_display,hardware_env,probe
from native_hw_encoder import BACKENDS,plan

HERE=Path(__file__).resolve().parent

def verify(native,browser,backend):
    if not (native.get('status')=='local-live-evidence' and native.get('hardwareContext',{}).get('hardwareContextVerified') is True
            and native.get('videoEncoder')==backend and native.get('encoderPreflight',{}).get('syntheticProbePassed') is True
            and native['nativeClock']['nativeElapsedMs']==300000 and 295<=native['checks']['observedWallSeconds']<=305
            and native['mediaTimeline']['timelinePassed'] is True and native['audio']['nonSilentCoveragePassed'] is True
            and native['audioOwnership']['verified'] is True and browser.get('passed') is True and browser.get('ended') is True
            and browser.get('playlistComplete') is True and browser['coverageFraction']>=.95
            and browser['videoWidth']==1280 and browser['videoHeight']==720):
        raise ValueError('Incomplete hardware match evidence')
    control=native['control'];evidence=control['traceEvidence']
    if not (control['submitted']==control['applied']==[1,1] and control['pending']==[False,False]
            and control['formations']==[442,4231] and evidence['consistent'] is True
            and evidence['allSubmittedObserved'] is True and len(evidence['acknowledgements'])==2
            and all(a['formationTargetsVerified'] is True for a in evidence['acknowledgements'])):
        raise ValueError('Incomplete hardware control evidence')
    return {'passed':True,'productionQualified':False,'backend':backend,'hardwareContext':native['hardwareContext'],
            'realMatchSeconds':native['checks']['observedWallSeconds'],'coverage':browser['coverageFraction'],
            'scope':'One dedicated GPU match only; no same-device, concurrency, or production claim'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path);p.add_argument('fixture',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--display',required=True);p.add_argument('--encoder',choices=BACKENDS[1:],required=True)
    p.add_argument('--drm-device',default='');p.add_argument('--gpu-index',default='')
    p.add_argument('--dedicated-display',action='store_true',required=True)
    a=p.parse_args();display=local_display(a.display)
    plan(a.encoder,a.drm_device,a.gpu_index)
    if os.environ.get('TRIBUN_GPU_DEDICATED')!='1':p.error('Explicit operator opt-in TRIBUN_GPU_DEDICATED=1 required')
    env={k:v for k,v in os.environ.items() if not k.startswith(('TRIBUN_NATIVE_','TRIBUN_AV_','TRIBUN_EXPECT_','TRIBUN_GPU_','TRIBUN_LEAGUE_SOCCER_'))}
    env=hardware_env(env,display)
    env.update(TRIBUN_GPU_DISPLAY=display,TRIBUN_GPU_DEDICATED='1',TRIBUN_AV_ENCODER=a.encoder,
        TRIBUN_AV_DRM_DEVICE=a.drm_device,TRIBUN_AV_GPU_INDEX=a.gpu_index,TRIBUN_EXPECT_AUDIO='1',
        TRIBUN_EXPECT_CONTROL='1',TRIBUN_EXPECT_FULL_PLAYBACK='1',TRIBUN_PLAYBACK_MIN_SECONDS='300')
    out=a.out.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    children=[];result={'passed':False,'productionQualified':False}
    try:
        probe(env)
        with (out/'native.log').open('wb') as n,(out/'browser.log').open('wb') as b:
            children.append(subprocess.Popen(['python3',str(HERE/'native-live-video.py'),str(a.runtime.resolve()),
                str(a.fixture.resolve()),str(out/'run'),'--audio','--interactive','--linger','60'],env=env,stdout=n,stderr=subprocess.STDOUT))
            children.append(subprocess.Popen(['node',str(HERE/'native-live-video-browser.cjs'),str(out/'run/local-url.txt')],
                env=env,stdout=b,stderr=subprocess.STDOUT,start_new_session=True))
            end=time.monotonic()+1200
            while any(c.poll() is None for c in children):
                if any(c.poll() not in (None,0) for c in children):raise RuntimeError('Child failed')
                if time.monotonic()>end:raise TimeoutError('Hardware diagnostic deadline')
                time.sleep(.5)
            if any(c.returncode for c in children):raise RuntimeError('Child failed')
        native=json.loads((out/'run/live-report.json').read_text())
        browser=json.loads((out/'run/browser-playback-report.json').read_text())
        result=verify(native,browser,a.encoder)
    except (OSError,ValueError,TypeError,KeyError,AttributeError,subprocess.SubprocessError,RuntimeError) as e:
        result['failureType']=type(e).__name__
    finally:
        for i,c in enumerate(children):
            if c.poll() is None:
                if i:os.killpg(c.pid,signal.SIGTERM)
                else:c.terminate()
            try:c.wait(timeout=30)
            except subprocess.TimeoutExpired:
                if i:os.killpg(c.pid,signal.SIGKILL)
                else:c.kill()
                c.wait()
        from native_release_gate import stamp
        result=stamp(result,a.runtime.resolve(),'hardware')
        (out/'hardware-match-report.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
