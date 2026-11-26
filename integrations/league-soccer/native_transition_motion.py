"""Sample actual native planar player movement; never infer animation success."""
from pathlib import Path
import math
import json
from native_stall_diagnostics import frame,vector,MAX_BYTES,MAX_LINE

def inspect_transitions(path):
    path=Path(path)
    if path.stat().st_size>MAX_BYTES:
        raise ValueError('Trace too large')
    prev={}
    intervals=turns=brakes=accelerations=excluded=0
    max_accel=max_turn=None
    last=None
    phase=None
    with path.open('rb') as f:
        while True:
            line=f.readline(MAX_LINE+1)
            if not line:break
            if len(line)>MAX_LINE:raise ValueError('Trace line too large')
            if not line.endswith(b'\n'):break
            row=json.loads(line)
            t=frame(row)
            if t is None:continue
            if last is not None and t<last:raise ValueError('Reversed native clock')
            if row['inPlay'] is not True or row.get('setPiece') is not False or row.get('done') or row.get('humanGamers')!=[0,0]:
                prev={};last=t;phase=row['phaseCode'];continue
            if last is not None and (not 0<t-last<=250 or phase!=row['phaseCode']):
                prev={}
                excluded+=1
            ball=vector(row['ball'])
            current={}
            for p in row['players']:
                if p.get('goalkeeper') is not False or p.get('team') not in (0,1) or type(p.get('id')) is not int:
                    continue
                pos=vector(p['position']);v=vector(p['velocity'])
                if math.hypot(pos[0]-ball[0],pos[1]-ball[1])<=2:continue
                key=(p['team'],p['id'])
                if key in current:raise ValueError('Duplicate player')
                current[key]=(v[0],v[1])
                if key not in prev:continue
                a,b=prev[key]
                dt=(t-last)/1000
                old=math.hypot(a,b);new=math.hypot(v[0],v[1])
                accel=(new-old)/dt
                intervals+=1
                max_accel=abs(accel) if max_accel is None else max(max_accel,abs(accel))
                if accel>=3:accelerations+=1
                if accel<=-3:brakes+=1
                if min(old,new)>=1:
                    angle=math.degrees(math.atan2(abs(a*v[1]-b*v[0]),a*v[0]+b*v[1]))
                    max_turn=angle if max_turn is None else max(max_turn,angle)
                    if angle>=45:turns+=1
            prev=current;last=t;phase=row['phaseCode']
    return dict(intervals=intervals,excludedFramePairs=excluded,accelerationIntervals=accelerations,
        brakingIntervals=brakes,sharpTurnIntervals=turns,
        maxAbsoluteSpeedChangeMps2=None if max_accel is None else round(max_accel,3),
        maxSampledTurnDegrees=None if max_turn is None else round(max_turn,3),
        scope='Adjacent sampled planar velocities in CPU open play away from ball. Thresholds 3 m/s² and 45 degrees; not animation identity, traction force, or causal proof. No coverage of sub-sample motion.')
