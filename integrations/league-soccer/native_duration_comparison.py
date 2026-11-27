"""Compare matched native fixtures at 5 and 30 simulation minutes, not video length."""
import argparse
import json
from pathlib import Path
from native_extended_capture import sha

SHORT, LONG = 300000, 1800000
COUNTERS = ('shots','onTarget','passes','completed','fouls')


def require(ok,message):
    if not ok:
        raise ValueError(message)


def pair(value):
    require(isinstance(value,list) and len(value)==2 and
            all(type(x) is int and x>=0 for x in value),'Invalid native counter')
    return value


def read_match(path, duration):
    """Use only started native frames; count controlled crossings conservatively."""
    require(duration in (SHORT,LONG),'Unsupported comparison duration')
    start=None
    previous=None
    previous_counts=None
    final=None
    frames=open_ms=gap_ms=0
    half_seen=False
    box_entries=[0,0]
    box_control_ms=[0,0]
    def owner(row):
        owners=[p for p in row['players'] if p['uniquePossession'] is True]
        return owners[0]['team'] if len(owners)==1 else None
    def inside(row,team):
        x,y,_=row['ball']
        return 38.5<=x*row['attackDirection'][team]<=55 and abs(y)<=20.15
    with Path(path).open(encoding='utf-8') as source:
        for line in source:
            row=json.loads(line)
            require(final is None and row.get('engine')=='league-soccer' and row.get('schema')==1,
                    'Unexpected native trace frame')
            c=row['fixedClock']
            require(type(c['started']) is bool,'Invalid clock state')
            if not c['started']:
                require(start is None and row['done'] is False,'Unexpected stopped clock')
                continue
            t=c['elapsedMs']
            require(type(t) is int and 0<=t<=duration,'Invalid simulation elapsed time')
            if start is None:
                require(t==0 and row['inPlay'] is True,'Missing kickoff')
                start=c['startMs']
            require(type(start) is int and c['startMs']==start and row['elapsedMs']==start+t and
                    row['matchMs']==t*(5400000//duration),'Inconsistent native clock')
            require(c['half'] is (t>=duration//2) and c['finished'] is (t==duration)
                    and row['done'] is (t==duration),'Inconsistent match boundaries')
            half_seen |= t==duration//2
            counts={'goals':pair(row['score']),**{k:pair(row['stats'][k]) for k in COUNTERS}}
            require(all(x<=y for x,y in zip(counts['onTarget'],counts['shots'])) and
                    all(x<=y for x,y in zip(counts['completed'],counts['passes'])),'Invalid cumulative totals')
            require(row['attackDirection'] in ([1,-1],[-1,1]) and
                    type(row['inPlay']) is bool,'Missing play-state telemetry')
            if previous is not None:
                pt,pr=previous
                dt=t-pt
                require(dt>=0 and all(a<=b for k in counts for a,b in
                    zip(previous_counts[k],counts[k])),'Native time or counters reversed')
                if dt>250:
                    gap_ms+=dt
                elif dt>0 and pr['inPlay'] and row['inPlay'] and pr['attackDirection']==row['attackDirection']:
                    open_ms+=dt
                    po,co=owner(pr),owner(row)
                    for team in (0,1):
                        was,now=inside(pr,team),inside(row,team)
                        if not was and now and co==team:
                            box_entries[team]+=1
                        if was and now and po==co==team:
                            box_control_ms[team]+=dt
            frames+=1
            previous=t,row
            previous_counts=counts
            if row['done']:
                final=counts
    require(final is not None and half_seen and frames>100 and open_ms>0,'Incomplete native match')
    require(gap_ms<=duration*.01,'Too much unobserved simulation time')
    metrics={**final,'controlledBoxCrossings':box_entries}
    totals={k:sum(v) for k,v in metrics.items()}
    return dict(simulationMs=duration,observedOpenPlayMs=open_ms,excludedGapMs=gap_ms,
                recordedFrames=frames,byTeam=metrics,totals=totals,
                controlledBoxMs=box_control_ms,
                perSimulationMinute={k:round(v/(duration/60000),4) for k,v in totals.items()},
                perObservedOpenPlayMinute={k:round(v/(open_ms/60000),4) for k,v in totals.items()})


def compare(short_trace,long_trace):
    short_fixture=Path(str(short_trace)+'.fixture.json')
    long_fixture=Path(str(long_trace)+'.fixture.json')
    a=json.loads(short_fixture.read_text())
    b=json.loads(long_fixture.read_text())
    require(a==b and type(a.get('seed')) is int and len(a.get('teams',[]))==2,
            'Frozen fixture or seed mismatch')
    short=read_match(short_trace,SHORT)
    long=read_match(long_trace,LONG)
    return dict(schema=1,seed=a['seed'],fixtureSha256=sha(short_fixture),
                shortTraceSha256=sha(short_trace),longTraceSha256=sha(long_trace),
                short=short,long=long,
                totalDelta={k:long['totals'][k]-v for k,v in short['totals'].items()},
                rateDeltaPerSimulationMinute={k:round(long['perSimulationMinute'][k]-v,4)
                                              for k,v in short['perSimulationMinute'].items()},
                scope='One matched fixture/seed, baseline AI, same prepared runtime in CI. '
                      'Long capture has extra video/audio/marker overhead. Descriptive comparison only; '
                      'not proof of general improvement or measured five-minute playback.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('short','long','output'):
        p.add_argument(name,type=Path)
    a=p.parse_args()
    report=compare(a.short,a.long)
    a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
