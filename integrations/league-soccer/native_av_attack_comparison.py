"""Sequential same-fixture AV attack comparison; no league settlement or promotion."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from native_match_quality import inspect
from native_release_gate import candidate,runtime_identity
HERE=Path(__file__).resolve().parent
PROFILES=('baseline','short-match')

def compare(rows):
    if len(rows)!=2 or [r.get('profile') for r in rows]!=list(PROFILES):raise ValueError('Expected two ordered profiles')
    valid=all(r.get('passed') is True and isinstance(r.get('quality',{}).get('football'),dict) for r in rows)
    same=rows[0].get('fixtureSha256')==rows[1].get('fixtureSha256') and bool(rows[0].get('fixtureSha256'))
    result={'passed':bool(valid and same),'productionQualified':False,'automaticPromotion':False,'rows':rows,'delta':None}
    if valid and same:
        a,b=(r['quality']['football'] for r in rows)
        keys=('totalShots','totalControlledBoxCrossings')
        if all(type(r.get(k)) is int for r in (a,b) for k in keys):
            result['delta']={k:b[k]-a[k] for k in keys}
            result['delta']['onTarget']=sum(b['onTarget'])-sum(a['onTarget'])
        else:result['passed']=False
    return result

def run_one(runtime,fixture,root,profile):
    root.mkdir(mode=0o700)
    out=root/'run'
    env={k:v for k,v in os.environ.items() if not k.startswith(('TRIBUN_NATIVE_','TRIBUN_AV_','TRIBUN_GPU_','TRIBUN_LEAGUE_SOCCER_','TRIBUN_EXPECT_','TRIBUN_PLAYBACK_'))}
    env.update(TRIBUN_EXPECT_AUDIO='1',TRIBUN_EXPECT_CONTROL='0',TRIBUN_EXPECT_FULL_PLAYBACK='1',TRIBUN_PLAYBACK_MIN_SECONDS='300',TRIBUN_EXPECT_SUSTAINED='0')
    children=[];error=None
    fixture_sha=hashlib.sha256(fixture.read_bytes()).hexdigest()
    try:
        with (root/'native.log').open('wb') as n,(root/'browser.log').open('wb') as b:
            children.append(subprocess.Popen(['python3',str(HERE/'native-live-video.py'),str(runtime),str(fixture),str(out),'--audio','--linger','60','--attack-profile',profile],env=env,stdout=n,stderr=subprocess.STDOUT))
            children.append(subprocess.Popen(['node',str(HERE/'native-live-video-browser.cjs'),str(out/'local-url.txt')],env=env,stdout=b,stderr=subprocess.STDOUT,start_new_session=True))
            deadline=time.monotonic()+1200
            while any(p.poll() is None for p in children):
                if any(p.poll() not in (None,0) for p in children):raise RuntimeError('Child failed')
                if time.monotonic()>deadline:raise TimeoutError('Match deadline')
                time.sleep(.5)
            if any(p.returncode for p in children):raise RuntimeError('Child failed')
    except (OSError,RuntimeError,ValueError) as exc:error=type(exc).__name__
    finally:
        for i,p in enumerate(children):
            if p.poll() is None:
                if i:os.killpg(p.pid,signal.SIGTERM)
                else:p.terminate()
            try:p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                if i:os.killpg(p.pid,signal.SIGKILL)
                else:p.kill()
                p.wait()
    quality=inspect(out)
    passed=False
    try:
        n=json.loads((out/'live-report.json').read_text());b=json.loads((out/'browser-playback-report.json').read_text())
        passed=bool(error is None and n['status']=='local-live-evidence' and n['requestedAttackProfile']==profile
            and n['fixtureSha256']==fixture_sha and n['traceSha256']==hashlib.sha256((out/'match.ndjson').read_bytes()).hexdigest()
            and n['audioOwnership']['verified'] is True and n['audio']['nonSilentCoveragePassed'] is True
            and n['mediaTimeline']['timelinePassed'] is True and quality['presentation']['checks']['fiveMinuteWall']
            and quality['presentation']['checks']['fullBrowserPlayback'] and b['videoWidth']==1280 and b['videoHeight']==720)
    except (OSError,ValueError,KeyError,TypeError):pass
    return {'profile':profile,'fixtureSha256':fixture_sha,'passed':passed,'failureType':error,'quality':quality}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path);p.add_argument('fixture',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='tribun-av-attack-') as t:
        root=Path(t);fixture=root/'fixture.json';fixture.write_bytes(a.fixture.read_bytes())
        rows=[run_one(a.runtime.resolve(),fixture,root/profile,profile) for profile in PROFILES]
        result=compare(rows)
    result.update(candidateCommit=candidate(),runtime=runtime_identity(a.runtime),scope='One sequential matched fixture pair; no live tactics; not deterministic, statistically conclusive, or actual league readiness')
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
