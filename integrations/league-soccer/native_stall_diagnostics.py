"""Separate sampled native carrier inactivity, engine clock gaps and video repetition."""
import json
import math
from pathlib import Path
MAX_BYTES=100*1024*1024
MAX_LINE=262144
MAX_EVENTS=100

def integer(x):return type(x) is int and x>=0
def vector(v):
    if not isinstance(v,list) or len(v)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in v):
        raise ValueError('Invalid native vector')
    return v
def dist(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
def speed(v):return math.sqrt(sum(x*x for x in vector(v)))

def frame(row):
    c=row.get('fixedClock')
    if not isinstance(c,dict) or type(c.get('started')) is not bool:raise ValueError('Missing native clock')
    if not c['started']:return None
    t=c.get('elapsedMs')
    if not integer(t) or t>300000 or row.get('matchMs')!=t*18 or type(row.get('phaseCode')) is not int or type(row.get('inPlay')) is not bool or type(row.get('done')) is not bool:
        raise ValueError('Invalid native time')
    return t

def carrier(row):
    if not row['inPlay'] or row.get('setPiece') is not False or row.get('ballRetainerId') is not None or row.get('done'):return None
    if row.get('humanGamers')!=[0,0]:return None
    ball=vector(row['ball'])
    if ball[2]>=.8 or speed(row['ballVelocity'])>=1.0:return None
    owners=[p for p in row['players'] if p.get('uniquePossession') is True]
    if len(owners)!=1:return None
    p=owners[0]
    if p.get('goalkeeper') is not False or not integer(p.get('id')) or p.get('team') not in (0,1):return None
    pos=vector(p['position'])
    if dist(pos,ball)>1.25 or speed(p['velocity'])>=.75:return None
    return (p['team'],p['id'],row['phaseCode']),pos,ball

def inspect_trace(path):
    path=Path(path)
    if path.stat().st_size>MAX_BYTES:raise ValueError('Trace too large')
    events=[];total=0;longest=0;active=None;prev=None;observed=0;gaps=0;done=False
    def close(end_reason):
        nonlocal active,total,longest
        if active:
            key,start,last,_,_=active;duration=last-start
            if duration>=1200:
                total+=1;longest=max(longest,duration)
                if len(events)<MAX_EVENTS:events.append(dict(team=key[0],playerId=key[1],phaseCode=key[2],startNativeMs=start,endNativeMs=last,durationMs=duration,endReason=end_reason))
        active=None
    with path.open('rb') as f:
        while True:
            line=f.readline(MAX_LINE+1)
            if not line:break
            if len(line)>MAX_LINE:raise ValueError('Trace line too large')
            if not line.endswith(b'\n'):break
            row=json.loads(line);t=frame(row)
            if t is None:
                if prev is not None:raise ValueError('Clock reset')
                continue
            if done:raise ValueError('Frames after full time')
            if prev is not None:
                if t<prev:raise ValueError('Reversed clock')
                if t-prev>250:
                    gaps+=t-prev;close('sampling-gap')
                else:observed+=t-prev
            prev=t
            c=carrier(row)
            if c is None:close('control-or-play-ended')
            else:
                key,pos,ball=c
                if active:
                    k,start,last,anchor,ball_anchor=active
                    if key!=k or dist(pos,anchor)>.45 or dist(ball,ball_anchor)>.55:close('carrier-or-position-changed')
                if active:active=(active[0],active[1],t,active[3],active[4])
                else:active=(key,t,t,pos,ball)
            done=row['done']
    close('trace-ended')
    if prev is None:raise ValueError('No started trace')
    return dict(complete=done,lastNativeMs=prev,observedMs=observed,excludedGapMs=gaps,stationaryCarrierEpisodes=total,
        longestStationaryCarrierMs=longest,episodes=events,truncated=total>len(events),
        scope='Sampled unique control and low motion while native clock advances; not proof of AI deadlock or recovery causation.')

class ClockObserver:
    """Read only the bounded tail; observe wall time independently of tick time."""
    def __init__(self):
        self.last=None;self.last_change=None;self.finished=False;self.events=[];self.count=0;self.longest=0
        self.error=None;self.size=None;self.active=False
    def observe(self,t,done,now):
        if self.finished:return
        if self.last is not None and t<self.last:raise ValueError('Clock reset')
        if self.last is None or t>self.last or done:
            self._close(now,'advanced' if not done else 'full-time')
            self.last=t;self.last_change=now
        elif now-self.last_change>=3:self.active=True
        self.finished=done
    def _close(self,now,reason):
        if self.last_change is not None and now-self.last_change>=3:
            seconds=round(now-self.last_change,3)
            self.count+=1;self.longest=max(self.longest,seconds)
            if len(self.events)<MAX_EVENTS:self.events.append(dict(lastNativeMs=self.last,wallSeconds=seconds,endReason=reason))
        self.active=False
    def poll(self,path,now):
        if self.finished or self.error:return
        try:
            path=Path(path)
            if not path.is_file():
                if self.last is not None:raise ValueError('Trace disappeared')
                return
            size=path.stat().st_size
            if size>MAX_BYTES or (self.size is not None and size<self.size):raise ValueError('Invalid trace size')
            if size==self.size:
                if self.last is not None and now-self.last_change>=3:self.active=True
                return
            self.size=size
            with path.open('rb') as f:
                f.seek(max(0,size-2*MAX_LINE));raw=f.read(2*MAX_LINE)
            rows=raw.split(b'\n')
            if len(rows)<2:return
            # Last complete row only; skip any partial trailing write.
            row=json.loads(rows[-2]);t=frame(row)
            if t is not None:self.observe(t,row['done'],now)
        except (OSError,ValueError,KeyError,TypeError) as exc:self.error=type(exc).__name__
    def report(self,now):
        if not self.finished and self.last is not None and self.last_change is not None:self._close(now,'capture-ended')
        return dict(lastNativeMs=self.last,fullTimeObserved=self.finished,wallGapCount=self.count,
            longestWallGapSeconds=self.longest,wallGaps=self.events,truncated=self.count>len(self.events),error=self.error,
            scope='Wall gaps >=3s in observed native trace progress after kickoff. May reflect computation, scheduling, I/O or pause; not necessarily deadlock. No automatic clock advance or reset.')
