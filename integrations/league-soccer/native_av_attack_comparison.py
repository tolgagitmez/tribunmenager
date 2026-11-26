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

def diagnostic_summary(native,browser,children,first_exit):
    # Retain only allowlisted statuses and boolean checks. Never copy raw
    # messages, local URLs, capability tokens, logs or private paths.
    def choose(v,allowed):
        return v if isinstance(v,str) and v in allowed else None
    def flags(row,keys):
        if not isinstance(row,dict):return {}
        return {k:row[k] for k in keys if type(row.get(k)) is bool}
    n=native if isinstance(native,dict) else {}
    b=browser if isinstance(browser,dict) else {}
    return {'firstFailedChild':first_exit,
        'nativeExit':children[0].returncode if len(children)>0 else None,
        'browserExit':children[1].returncode if len(children)>1 else None,
        'nativeStatus':choose(n.get('status'),('incomplete','local-live-evidence','coverage-inconclusive','failed')),
        'nativeFailureType':choose(n.get('failureType'),('RuntimeError','TimeoutError','ValueError','AssertionError','KeyboardInterrupt','FileNotFoundError','KeyError','CalledProcessError','OSError')),
        'runnerExit':n.get('runnerExit') if type(n.get('runnerExit')) is int else None,
        'captureChecks':flags(n.get('checks'),('captureBeforeKickoff','videoLengthAtLeastObservedMatch','firstSegmentBeforeObservedFinal','wallWithinOneSecond')),
        'audioChecks':flags(n.get('audio'),('nonSilentCoveragePassed',)),
        'ownershipChecks':flags(n.get('audioOwnership'),('verified',)),
        'timelineChecks':flags(n.get('mediaTimeline'),('timelinePassed',)),
        'browserChecks':flags(b,('passed','ended','playlistComplete','coveragePassed')),
        'browserReportPresent':bool(b)}

def run_one(runtime,fixture,root,profile,*,render_size=None,shadow_size=None,skin_cache=None,vao_cache=None,texture_cache=None,render_suite=False,box_lane=False,timed_pass=False,controlled_carry=False,attacking_duel=False):
    root.mkdir(mode=0o700)
    out=root/'run'
    env={k:v for k,v in os.environ.items() if not k.startswith(('TRIBUN_NATIVE_','TRIBUN_AV_','TRIBUN_GPU_','TRIBUN_LEAGUE_SOCCER_','TRIBUN_EXPECT_','TRIBUN_PLAYBACK_'))}
    env.update(TRIBUN_EXPECT_AUDIO='1',TRIBUN_EXPECT_CONTROL='0',TRIBUN_EXPECT_FULL_PLAYBACK='1',TRIBUN_PLAYBACK_MIN_SECONDS='300',TRIBUN_EXPECT_SUSTAINED='0')
    if render_size is not None:
        from native_render_resolution import SIZES
        if render_size not in SIZES or profile!='baseline':raise ValueError('Unsupported resolution experiment')
        env.update(TRIBUN_AV_RENDER_SIZE=render_size,TRIBUN_AV_SWAP_PROBE='1')
    if shadow_size is not None:
        if type(shadow_size) is not int or shadow_size not in (1024,2048) or render_size not in ('1280x720','960x540') or (render_size=='960x540' and shadow_size!=2048):
            raise ValueError('Unsupported shadow experiment')
        env['TRIBUN_AV_SHADOW_SIZE']=str(shadow_size)
    if render_suite:
        if render_size!='1280x720' or shadow_size!=2048 or profile!='baseline' or any(type(m) is not int or m not in (0,1) for m in (skin_cache,vao_cache,texture_cache)):
            raise ValueError('Invalid fixed-quality suite configuration')
        env['TRIBUN_AV_RENDER_SUITE']='1'
    if skin_cache is not None:
        if type(skin_cache) is not int or skin_cache not in (0,1) or render_size!='1280x720' or shadow_size!=2048:
            raise ValueError('Unsupported skinning experiment')
        env['TRIBUN_AV_SKIN_CACHE']=str(skin_cache)
    if vao_cache is not None:
        if type(vao_cache) is not int or vao_cache not in (0,1) or render_size!='1280x720' or shadow_size!=2048 or (not render_suite and skin_cache is not None):
            raise ValueError('Unsupported VAO experiment')
        env['TRIBUN_AV_VAO_CACHE']=str(vao_cache)
    if texture_cache is not None:
        if type(texture_cache) is not int or texture_cache not in (0,1) or render_size!='1280x720' or shadow_size!=2048 or (not render_suite and (skin_cache is not None or vao_cache is not None)):
            raise ValueError('Unsupported texture experiment')
        env['TRIBUN_AV_TEXTURE_CACHE']=str(texture_cache)
    if box_lane and (profile!='short-match' or any(x is not None for x in (render_size,shadow_size,skin_cache,vao_cache,texture_cache)) or render_suite):
        raise ValueError('Isolated box lane comparison required')
    if timed_pass and (profile!='short-match' or box_lane or render_suite or any(x is not None for x in (render_size,shadow_size,skin_cache,vao_cache,texture_cache))):
        raise ValueError('Isolated timed-pass trial required')
    if controlled_carry and (profile!='short-match' or box_lane or timed_pass or render_suite or any(x is not None for x in (render_size,shadow_size,skin_cache,vao_cache,texture_cache))):
        raise ValueError('Isolated controlled-carry trial required')
    if attacking_duel and (profile!='short-match' or box_lane or timed_pass or controlled_carry or render_suite or any(x is not None for x in (render_size,shadow_size,skin_cache,vao_cache,texture_cache))):
        raise ValueError('Isolated attacking-duel trial required')
    children=[];error=None;firstExit=None
    fixture_sha=hashlib.sha256(fixture.read_bytes()).hexdigest()
    try:
        with (root/'native.log').open('wb') as n,(root/'browser.log').open('wb') as b:
            children.append(subprocess.Popen(['python3',str(HERE/'native-live-video.py'),str(runtime),str(fixture),str(out),'--audio','--linger','60','--attack-profile',profile]+(['--box-lane'] if box_lane else [])+(['--timed-pass'] if timed_pass else [])+(['--controlled-carry'] if controlled_carry else [])+(['--attacking-duel'] if attacking_duel else []),env=env,stdout=n,stderr=subprocess.STDOUT))
            children.append(subprocess.Popen(['node',str(HERE/'native-live-video-browser.cjs'),str(out/'local-url.txt')],env=env,stdout=b,stderr=subprocess.STDOUT,start_new_session=True))
            deadline=time.monotonic()+1200
            while any(p.poll() is None for p in children):
                failed=[(i,p.returncode) for i,p in enumerate(children) if p.poll() not in (None,0)]
                if failed:
                    firstExit={'process':('native','browser')[failed[0][0]],'code':failed[0][1]}
                    raise RuntimeError('Child failed')
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
    n={};b={}
    try:
        n=json.loads((out/'live-report.json').read_text());b=json.loads((out/'browser-playback-report.json').read_text())
        passed=bool(error is None and n['status']=='local-live-evidence' and n['requestedAttackProfile']==profile
            and n['fixtureSha256']==fixture_sha and n['traceSha256']==hashlib.sha256((out/'match.ndjson').read_bytes()).hexdigest()
            and n['audioOwnership']['verified'] is True and n['audio']['nonSilentCoveragePassed'] is True
            and n['mediaTimeline']['timelinePassed'] is True and quality['presentation']['checks']['fiveMinuteWall']
            and quality['presentation']['checks']['fullBrowserPlayback'] and b['videoWidth']==1280 and b['videoHeight']==720)
    except (OSError,ValueError,KeyError,TypeError):pass
    diagnostics=diagnostic_summary(n,b,children,firstExit)
    result={'profile':profile,'fixtureSha256':fixture_sha,'passed':passed,'failureType':error,'quality':quality,'renderSuite':render_suite,'diagnostics':diagnostics,'boxLane':box_lane,'boxLaneObserved':False,'evidenceErrors':{}}
    result.update(attackingDuel=attacking_duel,duelEvidence=None)
    if profile=='short-match' and not box_lane and not timed_pass and not controlled_carry:
        try:
            from native_duel_av import trace_counts
            result['duelEvidence']=trace_counts(out/'match.ndjson')
            observed=sum(x['inspected'] for x in result['duelEvidence'])
            if n.get('requestedAttackingDuel') is not attacking_duel or bool(observed)!=attacking_duel:
                result['passed']=False
        except (OSError,ValueError,KeyError,TypeError) as exc:
            result['passed']=False;result['evidenceErrors']['attackingDuel']=type(exc).__name__
    result.update(controlledCarry=controlled_carry,carryEvidence=None)
    if profile=='short-match' and not box_lane and not timed_pass:
        try:
            from native_controlled_carry_av import trace_counts
            result['carryEvidence']=trace_counts(out/'match.ndjson')
            attempts=sum(x['attempts'] for x in result['carryEvidence'])
            if n.get('requestedControlledCarry') is not controlled_carry or bool(attempts)!=controlled_carry:
                result['passed']=False
        except (OSError,ValueError,KeyError,TypeError) as exc:
            result['passed']=False;result['evidenceErrors']['controlledCarry']=type(exc).__name__
    result.update(timedPass=timed_pass,timedEvidence=None)
    if profile=='short-match' and not box_lane:
        try:
            from native_timed_pass_av import trace_counts
            result['timedEvidence']=trace_counts(out/'match.ndjson')
            if timed_pass and (n.get('requestedTimedPass') is not True or sum(x['passes'] for x in result['timedEvidence'])==0):
                result['passed']=False
            if not timed_pass and any(x['passes'] for x in result['timedEvidence']):
                result['passed']=False
        except (OSError,ValueError,KeyError,TypeError) as exc:
            result['passed']=False;result['evidenceErrors']['timedPass']=type(exc).__name__
    if box_lane:
        try:
            log=out/'native-match.game.log'
            if log.stat().st_size>16*1024*1024:raise ValueError('Oversized native log')
            result['boxLaneObserved']=n.get('requestedBoxLane') is True and '[tribun-box-entry] lane-selected=1' in log.read_text(errors='replace').splitlines()
            if not result['boxLaneObserved']:result['passed']=False
        except (OSError,ValueError) as exc:
            result['passed']=False;result['evidenceErrors']['boxLane']=type(exc).__name__
    if render_size is not None:
        result.update(renderSize=render_size,windowGeometry=None,renderProbe=None)
        try:
            capture=json.loads((out/'native-match.capture.json').read_text())
            result.update(windowGeometry=capture['windowGeometry'],renderProbe=capture['renderProbe'])
            from native_render_resolution import SIZES
            width,height=SIZES[render_size]
            geometry=result['windowGeometry']
            result['passed']=bool(passed and geometry['verified'] is True and geometry['requested']==render_size
                and (geometry['width'],geometry['height'])==(width,height) and result['renderProbe']['observed'] is True)
        except (OSError,ValueError,KeyError,TypeError):result['passed']=False
    if shadow_size is not None:
        from native_shadow_resolution_comparison import shadow_evidence
        result.update(shadowSize=shadow_size,shadowEvidence=None)
        try:
            log=out/'native-match.game.log'
            if log.stat().st_size>16*1024*1024:raise ValueError('Oversized native log')
            result['shadowEvidence']=shadow_evidence(log.read_text(errors='replace'),shadow_size)
        except (OSError,ValueError) as exc:result['passed']=False;result['evidenceErrors']['shadow']=type(exc).__name__
    if skin_cache is not None:
        from native_skinning_cache_comparison import parse_skin
        result.update(skinCache=skin_cache,skinEvidence=None)
        try:
            log=out/'native-match.game.log'
            if log.stat().st_size>16*1024*1024:raise ValueError('Oversized native log')
            result['skinEvidence']=parse_skin(log.read_text(errors='replace'),skin_cache)
        except (OSError,ValueError) as exc:result['passed']=False;result['evidenceErrors']['skin']=type(exc).__name__
    if vao_cache is not None:
        from native_vao_cache_comparison import parse_vao
        result.update(vaoCache=vao_cache,vaoEvidence=None)
        try:
            log=out/'native-match.game.log'
            if log.stat().st_size>16*1024*1024:raise ValueError('Oversized native log')
            result['vaoEvidence']=parse_vao(log.read_text(errors='replace'),vao_cache)
        except (OSError,ValueError) as exc:result['passed']=False;result['evidenceErrors']['vao']=type(exc).__name__
    if texture_cache is not None:
        from native_texture_cache_comparison import parse_texture
        result.update(textureCache=texture_cache,textureEvidence=None)
        try:
            log=out/'native-match.game.log'
            if log.stat().st_size>16*1024*1024:raise ValueError('Oversized native log')
            result['textureEvidence']=parse_texture(log.read_text(errors='replace'),texture_cache)
        except (OSError,ValueError) as exc:result['passed']=False;result['evidenceErrors']['texture']=type(exc).__name__
    return result

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
