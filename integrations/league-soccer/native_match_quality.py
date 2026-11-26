"""Post-match football and presentation diagnostics; never generate or replace motor results."""
import json
import math
from pathlib import Path
import subprocess
import tempfile
from native_motion_audit import audit as motion_audit
HERE=Path(__file__).resolve().parent

def number(v,lo=0,hi=math.inf):
    return type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi

def pair(v):
    if not isinstance(v,list) or len(v)!=2 or not all(type(x) is int and x>=0 for x in v):raise ValueError('Invalid cumulative statistic')
    return v

def football(report):
    if report.get('engine')!='league-soccer':raise ValueError('Wrong engine')
    stats={k:pair(report[k]) for k in ('score','shots','onTarget','passes','completed','fouls','possessionMs')}
    if any(o>s or p>n for o,s,p,n in zip(stats['onTarget'],stats['shots'],stats['completed'],stats['passes'])):raise ValueError('Inconsistent statistics')
    sampled=report.get('sampled')
    if isinstance(sampled,dict):
        stats['controlledBoxCrossings']=pair(sampled['controlledBoxCrossings'])
        stats['observedBoxCrossings']=pair(sampled['observedBoxCrossings'])
        stats['observedOpenPlayMs']=sampled['observedOpenPlayMs']
        stats['excludedGapMs']=sampled['excludedGapMs']
    else:
        stats.update(controlledBoxCrossings=None,observedBoxCrossings=None,observedOpenPlayMs=None,excludedGapMs=None)
    stats['passCompletionPercent']=[round(100*a/b,2) if b else None for a,b in zip(stats['completed'],stats['passes'])]
    stats['totalShots']=sum(stats['shots'])
    stats['totalControlledBoxCrossings']=sum(stats['controlledBoxCrossings']) if stats['controlledBoxCrossings'] is not None else None
    return stats

def presentation(native,browser,motion):
    wall=native.get('checks',{}).get('observedWallSeconds')
    clock=native.get('nativeClock',{}).get('nativeElapsedMs')
    d=browser if browser.get('passed') is True else browser.get('diagnostic') or {}
    decoded,dropped=d.get('decodedFrames'),d.get('droppedFrames')
    fraction=dropped/decoded if number(decoded,1) and number(dropped,0,decoded) else None
    repeated=motion.get('repeatedFraction')
    longest=motion.get('longestIdenticalImageSeconds')
    checks={'fiveMinuteWall':number(wall,295,305) and clock==300000,
        'fullBrowserPlayback':browser.get('passed') is True and browser.get('ended') is True and number(browser.get('coverageFraction'),.95,1.01),
        'browserDropBudget':number(fraction,0,.01),
        'reducedImageRepetitionBudget':number(repeated,0,.20) and number(longest,0,.5)}
    return {'nativeElapsedMs':clock,'realMatchSeconds':wall,'browserCoverage':browser.get('coverageFraction'),
        'decodedFrames':decoded,'droppedFrames':dropped,'droppedFraction':fraction,
        'repeatedReducedImageFraction':repeated,'longestIdenticalImageSeconds':longest,
        'automaticSkippedSeconds':d.get('automaticSkippedSeconds'),'checks':checks,
        'presentationReviewEligible':all(checks.values()),
        'scope':'Provisional whole-video thresholds; reduced-image repetition is not native FPS, stationary scenes may be legitimate.'}

def inspect(directory):
    directory=Path(directory)
    result={'football':None,'presentation':None,'errors':{},'productionQualified':False,'subjectiveQualityVerified':False}
    trace=directory/'match.ndjson'
    try:
        if not trace.is_file() or trace.stat().st_size>100*1024*1024:raise ValueError('Missing/big trace')
        # Only complete native trace contributes football totals.
        with trace.open('rb') as f:
            final=None
            for line in f:
                if line.strip():final=line
        if final is None or json.loads(final).get('done') is not True:raise ValueError('Incomplete trace')
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'attack.json'
            subprocess.run(['node',str(HERE/'attack-report.cjs'),str(trace),str(dest)],check=True,timeout=90,capture_output=True)
            result['football']=football(json.loads(dest.read_text()))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:result['errors']['football']=type(exc).__name__
    native={};browser={};motion={}
    for name,field in (('live-report.json','native'),('browser-playback-report.json','browser')):
        try:
            raw=json.loads((directory/name).read_text())
            if not isinstance(raw,dict):raise ValueError('Invalid report')
            if field=='native':native=raw
            else:browser=raw
        except (OSError,ValueError,TypeError) as exc:result['errors'][field]=type(exc).__name__
    try:
        playlist=directory/'hls/live.m3u8'
        if not playlist.is_file() or '#EXT-X-ENDLIST' not in playlist.read_text().splitlines():raise ValueError('Incomplete playlist')
        motion=motion_audit(playlist)
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:result['errors']['motion']=type(exc).__name__
    result['presentation']=presentation(native,browser,motion)
    return result
