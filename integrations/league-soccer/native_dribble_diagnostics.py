"""Separate native dribble launch adjustments from sampled carrier-ball separation."""
from pathlib import Path
import json
import math
import re
from native_stall_diagnostics import frame,vector,MAX_BYTES,MAX_LINE

LIMIT=32*1024*1024
TOUCH=re.compile(r'\[tribun-dribble-control\] phase=(-?\d+) match_ms=(\d+) team=([01]) player=(\d+) enabled=([01]) before=(\S+) after=(\S+) projected=(\S+) clearance=(\S+) proposed=(\S+)')

def inspect_dribble(log_path,trace_path):
    log_path=Path(log_path);trace_path=Path(trace_path)
    result={'touches':None,'separation':None,
            'scope':'Logged native ball-control launch vectors and sampled unique outfield possession with low ball. Not proof of completed dribble, touch-to-loss causation, or improvement across unmatched fixtures.'}
    if log_path.is_file():
        if log_path.stat().st_size>LIMIT:raise ValueError('Game log too large')
        groups={};invalid=0
        with log_path.open('r',encoding='utf-8',errors='replace') as log:
            for line in log:
                if not line.startswith('[tribun-dribble-control]'):continue
                m=TOUCH.fullmatch(line.rstrip('\r\n'))
                try:
                    if not m:raise ValueError('Malformed touch')
                    before,after,projected,clearance,proposed=map(float,m.groups()[5:])
                    if (not all(math.isfinite(v) for v in (before,after,projected,clearance,proposed))
                        or min(after,projected,clearance)<0 or before<=0 or not .79999<=proposed<=1.00001):
                        raise ValueError('Invalid touch')
                    expected=before*(proposed if m[5]=='1' else 1)
                    if abs(after-expected)>.0001+before*.00001:raise ValueError('Unexpected applied speed')
                except ValueError:
                    invalid+=1;continue
                group=groups.setdefault('experimental' if m[5]=='1' else 'baseline',
                    {'samples':0,'proposedReduction':0,'appliedReduction':0,'beforeSum':0.0,'afterSum':0.0})
                group['samples']+=1
                group['proposedReduction']+=int(proposed<.99999)
                group['appliedReduction']+=int(before-after>.0001)
                group['beforeSum']+=before;group['afterSum']+=after
        for group in groups.values():
            n=group['samples']
            group['meanBeforeMps']=round(group.pop('beforeSum')/n,4)
            group['meanAfterMps']=round(group.pop('afterSum')/n,4)
        result['touches']={'groups':groups,'invalidLines':invalid}
    if trace_path.is_file():
        if trace_path.stat().st_size>MAX_BYTES:raise ValueError('Trace too large')
        n=wide=far=0;total=0.;last=None
        with trace_path.open('rb') as f:
            while True:
                line=f.readline(MAX_LINE+1)
                if not line:break
                if len(line)>MAX_LINE:raise ValueError('Trace line too large')
                if not line.endswith(b'\n'):break
                row=json.loads(line);t=frame(row)
                if t is None:continue
                if last is not None and t<last:raise ValueError('Reversed clock')
                if t==last:continue
                last=t
                if not row['inPlay'] or row.get('setPiece') is not False or row.get('done') or row.get('humanGamers')!=[0,0] or row.get('ballRetainerId') is not None:continue
                ball=vector(row['ball'])
                if not 0<=ball[2]<=.35:continue
                owners=[p for p in row['players'] if p.get('uniquePossession') is True]
                if len(owners)!=1 or owners[0].get('goalkeeper') is not False:continue
                p=vector(owners[0]['position'])
                d=math.hypot(p[0]-ball[0],p[1]-ball[1])
                n+=1;total+=d;wide+=int(d>1.25);far+=int(d>2.0)
        result['separation']={'samples':n,'meanPlanarDistanceM':round(total/n,4) if n else None,
            'over1_25m':wide,'over2m':far,'over2mFraction':round(far/n,5) if n else None}
    return result
