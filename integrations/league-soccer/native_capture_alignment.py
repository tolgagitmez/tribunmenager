"""Audit a candidate common epoch mapping; not rendered-frame or sound-event proof."""
import argparse
import bisect
import json
import math
from pathlib import Path

from native_extended_clock_verify import verify, DURATION
from native_media_retime import probe, duration
from native_extended_capture import sha

MAX_NATIVE_GAP_MS = 250
MAX_WALL_GAP_MS = 500
MAX_EPOCH_DRIFT_US = 20000


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(rows, origin, tracks, expected_ms=DURATION):
    require(type(origin) is int and origin > 0, 'Missing shared capture epoch')
    anchors=[]
    max_native_gap=max_wall_gap=max_drift=0
    first_offset=None
    for row in rows:
        c=row['fixedClock']
        if not c['started']:
            continue
        n=c['elapsedMs']
        clock=row.get('captureClock',{})
        wall,steady=clock.get('wallUs'),clock.get('steadyUs')
        require(all(type(x) is int for x in (n,wall,steady)) and 0<=n<=expected_ms
                and wall>origin*1000000 and steady>0,'Invalid native capture timestamp')
        offset=wall-steady
        if first_offset is None:
            require(n==0,'Missing exact kickoff timestamp')
            first_offset=offset
        max_drift=max(max_drift,abs(offset-first_offset))
        media_us=wall-origin*1000000
        if anchors:
            prev_n,prev_us=anchors[-1]
            require(n>=prev_n and media_us>=prev_us,'Clock reversed')
            if n==prev_n:
                # Preserve the earliest observed state at that native tick.
                continue
            require(media_us>prev_us,'Non-increasing mapped clock')
            max_native_gap=max(max_native_gap,n-prev_n)
            max_wall_gap=max(max_wall_gap,(media_us-prev_us)/1000)
        anchors.append((n,media_us))
    require(len(anchors)>=2 and anchors[-1][0]==expected_ms,'Incomplete native clock anchors')
    first_pts,last_pts=anchors[0][1]/1e6,anchors[-1][1]/1e6
    require(len(tracks)==2,'Video and audio required')
    bounds=[]
    for track in tracks:
        start,end=track
        require(all(type(x) in (int,float) and math.isfinite(x) for x in track)
                and 0<=start<end,'Invalid encoded track bounds')
        bounds.append((start,end))
    checks=dict(nativeSampling=max_native_gap<=MAX_NATIVE_GAP_MS,
                wallSampling=max_wall_gap<=MAX_WALL_GAP_MS,
                stableWallEpoch=max_drift<=MAX_EPOCH_DRIFT_US,
                bothTracksCoverMatch=all(start<=first_pts+.05 and end>=last_pts-.05
                                         for start,end in bounds))
    return dict(schema=1,simulationMs=expected_ms,mediaEpochOriginSeconds=origin,
                kickoffCandidatePtsSeconds=first_pts,fullTimeCandidatePtsSeconds=last_pts,
                anchorCount=len(anchors),maxNativeGapMs=max_native_gap,
                maxWallGapMs=max_wall_gap,maxEpochDriftUs=max_drift,
                trackBoundsSeconds=bounds,checks=checks,candidateMappingPassed=all(checks.values()),
                exactMediaAlignmentVerified=False,eligibleForAutomaticRetime=False,
                anchors=[dict(nativeMs=n,candidatePtsUs=u) for n,u in anchors],
                scope='Candidate mapping based on native trace and common capture epoch. '
                      'Does not prove the displayed frame or audio event matches a native tick.')


def candidate_pts(report,native_ms):
    require(report.get('candidateMappingPassed') is True,'Unqualified candidate map')
    anchors=report['anchors']
    require(type(native_ms) is int and 0<=native_ms<=report['simulationMs'],'Out of range native time')
    times=[a['nativeMs'] for a in anchors]
    i=bisect.bisect_left(times,native_ms)
    if times[i]==native_ms:
        return anchors[i]['candidatePtsUs']/1e6
    a,b=anchors[i-1],anchors[i]
    f=(native_ms-a['nativeMs'])/(b['nativeMs']-a['nativeMs'])
    return (a['candidatePtsUs']+f*(b['candidatePtsUs']-a['candidatePtsUs']))/1e6


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('trace',type=Path)
    p.add_argument('video',type=Path)
    p.add_argument('observations',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args()
    verify(a.trace)
    origin=json.loads(a.observations.read_text())['mediaEpochOriginSeconds']
    v,au,fmt=probe(a.video)
    tracks=[]
    for stream in (v,au):
        start=float(stream['start_time'])
        tracks.append((start,start+duration(stream,fmt['duration'])))
    with a.trace.open() as f:
        report=audit((json.loads(line) for line in f),origin,tracks)
    report.update(traceSha256=sha(a.trace),videoSha256=sha(a.video))
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='anchors'},indent=2))
    return 0 if report['candidateMappingPassed'] else 2


if __name__=='__main__':
    raise SystemExit(main())
