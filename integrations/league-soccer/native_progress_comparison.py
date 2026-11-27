"""Compare two equally long native traces in the isolated progression trial."""
import argparse
import json
from pathlib import Path
from native_duration_comparison import read_match, LONG
from native_stall_diagnostics import inspect_trace
from native_extended_capture import sha


def compare(baseline, trial):
    paths=[Path(baseline),Path(trial)]
    fixtures=[json.loads(Path(str(p)+'.fixture.json').read_text()) for p in paths]
    if fixtures[0]!=fixtures[1]:
        raise ValueError('Mismatched frozen fixtures')
    reports=[]
    for path in paths:
        metrics=read_match(path,LONG)
        stalls=inspect_trace(path,LONG)
        if not stalls['complete'] or stalls['lastNativeMs']!=LONG:
            raise ValueError('Incomplete stall evidence')
        reports.append(dict(metrics=metrics,stalls={k:stalls[k] for k in (
            'stationaryCarrierEpisodes','totalStationaryCarrierMs','longestStationaryCarrierMs','longestEpisode')},
            traceSha256=sha(path)))
    a,b=reports
    delta={k:b['metrics']['totals'][k]-v for k,v in a['metrics']['totals'].items()}
    return dict(schema=1,seed=fixtures[0]['seed'],baseline=a,progressRecovery=b,delta=delta,
                stationaryDeltaMs=b['stalls']['totalStationaryCarrierMs']-a['stalls']['totalStationaryCarrierMs'],
                scope='One matched seed, same native runtime, trace-only. No causal generalization or release approval.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','trial','output'):
        p.add_argument(name,type=Path)
    a=p.parse_args()
    result=compare(a.baseline,a.trial)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
