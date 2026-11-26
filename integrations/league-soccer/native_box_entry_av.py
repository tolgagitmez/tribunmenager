"""Two matched full audiovisual box-lane comparisons; no promotion."""
import argparse
import json
import math
from pathlib import Path
import tempfile
from native_release_gate import candidate,runtime_identity
from native_av_attack_comparison import run_one

def counts(row,mode):
    if row.get('passed') is not True or row.get('profile')!='short-match' or row.get('boxLane') is not mode or row.get('boxLaneObserved') is not mode:
        raise ValueError('Incomplete or unobserved profile')
    f=row['quality']['football']
    keys=('totalControlledBoxCrossings','totalShots')
    values=[f[k] for k in keys]
    for k in ('passes','completed','onTarget'):
        pair=f[k]
        if not isinstance(pair,list) or len(pair)!=2 or any(type(v) is not int or v<0 for v in pair):raise ValueError('Invalid football count')
        values.append(sum(pair))
    if any(type(x) is not int or x<0 for x in values) or values[2]<=0 or values[3]>values[2] or values[4]>values[1]:raise ValueError('Invalid counts')
    return values

def compare(pairs):
    result={'passed':False,'candidateForFurtherReview':False,'productionQualified':False,'automaticPromotion':False,'pairs':[]}
    if len(pairs)!=2:return result
    seen=set()
    try:
        for base,trial in pairs:
            fixture=base.get('fixtureSha256')
            if not fixture or fixture in seen or fixture!=trial.get('fixtureSha256'):raise ValueError('Invalid paired fixture')
            seen.add(fixture)
            a,b=counts(base,False),counts(trial,True)
            result['pairs'].append({'fixtureSha256':fixture,'boxEntryDelta':b[0]-a[0],'shotDelta':b[1]-a[1],
                'onTargetDelta':b[4]-a[4],'passCompletionDelta':b[3]/b[2]-a[3]/a[2]})
        rows=result['pairs']
        result.update(passed=True,candidateForFurtherReview=bool(sum(x['boxEntryDelta'] for x in rows)>=2 and
            all(x['boxEntryDelta']>=0 and x['shotDelta']>=-1 and x['passCompletionDelta']>=-.05 for x in rows) and sum(x['onTargetDelta'] for x in rows)>=0))
    except (ValueError,KeyError,TypeError,AttributeError) as exc:result['failureType']=type(exc).__name__
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path);p.add_argument('fixtures',type=Path,nargs=2);p.add_argument('report',type=Path)
    a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='tribun-box-entry-') as t:
        root=Path(t);pairs=[]
        for i,f in enumerate(a.fixtures):
            fixture=root/f'fixture-{i}.json';fixture.write_bytes(f.read_bytes())
            # Reverse execution order for the second fixture to reduce order bias.
            order=(False,True) if i==0 else (True,False)
            rows={mode:run_one(a.runtime.resolve(),fixture,root/f'{i}-{int(mode)}','short-match',box_lane=mode) for mode in order}
            pairs.append([rows[False],rows[True]])
        result=compare(pairs)
    result.update(rows=pairs,candidateCommit=candidate(),runtime=runtime_identity(a.runtime),
        scope='Two fixtures, full AV, five-minute real time, short-match base versus opt-in widened safe box-lane policy. Not statistically conclusive, no live tactics or production promotion.')
    a.report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2,allow_nan=False))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
