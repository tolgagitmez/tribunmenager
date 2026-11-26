"""Analyze native applied-snapshot ankle positions, not planted sole contact."""
from collections import Counter
from pathlib import Path
import math
import re

LIMIT=32*1024*1024
MAX_EVENTS=200
PATTERN=re.compile(r'\[tribun-skeleton-feet\] snapshot=(\d+) match_ms=(\d+) phase=(-?\d+) player=(-?\d+) anim=(-?\d+) frame=(-?\d+) touch_frame=(-?\d+) left=(\S+) right=(\S+) ball=(\S+)')

def vec(value):
    v=tuple(map(float,value.split(',')))
    if len(v)!=3 or not all(math.isfinite(x) for x in v):
        raise ValueError('Invalid joint vector')
    return v

def inspect_skeleton(path):
    path=Path(path)
    if not path.is_file():
        return None
    if path.stat().st_size>LIMIT:
        raise ValueError('Skeleton log too large')
    samples=invalid=duplicates=0
    previous={}
    intervals=Counter()
    max_speed={'left':None,'right':None}
    contacts=[]
    contact_count=0
    near_ground=.16
    speed_threshold=.5
    with path.open('r',encoding='utf-8',errors='replace') as log:
        for line in log:
            if not line.startswith('[tribun-skeleton-feet]'):
                continue
            m=PATTERN.fullmatch(line.rstrip('\r\n'))
            if not m:
                invalid+=1
                continue
            try:
                snapshot,match,phase,player,anim,frame,touch=map(int,m.groups()[:7])
                left,right,ball=map(vec,m.groups()[7:10])
                if min(player,anim,frame)<0 or touch< -1 or (touch>=0 and abs(frame-touch)>3):
                    raise ValueError('Invalid animation frame')
            except ValueError:
                invalid+=1
                continue
            prev=previous.get(player)
            if prev and snapshot==prev[0]:
                duplicates+=1
                continue
            samples+=1
            if prev:
                dt=snapshot-prev[0]
                # Never interpret a frame jump or animation transition as slide.
                if 0<dt<=100 and phase==prev[1] and anim==prev[2] and frame>prev[3]:
                    for side,a,b in (('left',prev[4],left),('right',prev[5],right)):
                        speed=math.hypot(b[0]-a[0],b[1]-a[1])*1000/dt
                        intervals[side+'Intervals']+=1
                        if max_speed[side] is None or speed>max_speed[side]:
                            max_speed[side]=speed
                        if max(a[2],b[2])<=near_ground and min(a[2],b[2])>=0:
                            intervals[side+'LowAnkleIntervals']+=1
                            if speed>speed_threshold:
                                intervals[side+'LowAnkleMotionCandidates']+=1
                else:
                    intervals['excludedPairs']+=1
            previous[player]=(snapshot,phase,anim,frame,left,right)
            if touch>=0 and frame==touch:
                contact_count+=1
                if len(contacts)<MAX_EVENTS:
                    contacts.append(dict(snapshotMs=snapshot,matchMs=match,phase=phase,
                        playerId=player,animationId=anim,frame=frame,leftAnkle=list(left),
                        rightAnkle=list(right),ball=list(ball),
                        leftAnkleBallDistance=round(math.dist(left,ball),5),
                        rightAnkleBallDistance=round(math.dist(right,ball),5)))
    return dict(samples=samples,invalidLines=invalid,duplicateSamples=duplicates,
        intervals=dict(intervals),maxHorizontalAnkleSpeed={k:None if v is None else round(v,3) for k,v in max_speed.items()},
        lowAnkleHeightThreshold=near_ground,lowAnkleSpeedThreshold=speed_threshold,
        contactFrameSamples=contact_count,contactFrames=contacts,contactFramesTruncated=contact_count>len(contacts),
        evidenceAvailable=samples>0,
        scope='Native applied skeletal ankle positions before historical temporal smoothing. Low ankle motion is a candidate, not verified foot slide or sole-ground contact. Contact-frame distances are ankle-to-ball, not boot-to-ball or actual successful touch. Snapshot gaps and animation transitions are excluded from motion estimates.')
