"""Controlled-carry experiment in actual five-minute native audiovisual fixtures."""
import argparse
import json
from pathlib import Path
import tempfile
from native_release_gate import candidate,runtime_identity
KEYS=('attempts','progressed','lost','cancelled')

def valid(c):
    return isinstance(c,dict) and all(type(c.get(k)) is int and c[k]>=0 for k in KEYS) and sum(c[k] for k in KEYS[1:])<=c['attempts']

def trace_counts(path):
    prev=[dict.fromkeys(KEYS,0) for _ in range(2)]
    final=None
    with Path(path).open() as f:
        for line in f:
            row=json.loads(line);counts=row.get('controlledCarries')
            if not isinstance(counts,list) or len(counts)!=2 or any(not valid(c) or any(c[k]<prev[i][k] for k in KEYS) for i,c in enumerate(counts)):
                raise ValueError('Invalid native carry counters')
            prev=[{k:c[k] for k in KEYS} for c in counts];final=row
    if not final or final.get('done') is not True:raise ValueError('Incomplete match')
    return prev

def compare(pairs):
    result={'passed':False,'candidateForFurtherReview':False,'automaticPromotion':False,'productionQualified':False,'pairs':[]}
    seen=set()
    try:
        if len(pairs)!=2:raise ValueError('Two fixture pairs required')
        for base,trial in pairs:
            fid=base['fixtureSha256']
            if not fid or fid in seen or fid!=trial['fixtureSha256']:raise ValueError('Mismatched fixture')
            seen.add(fid)
            for row,mode in ((base,False),(trial,True)):
                if row.get('passed') is not True or row.get('profile')!='short-match' or row.get('controlledCarry') is not mode or row.get('timedPass') is not False or row.get('boxLane') is not False:
                    raise ValueError('Incomplete or mixed recording')
                c=row['carryEvidence']
                if len(c)!=2 or not all(valid(x) for x in c) or bool(sum(x['attempts'] for x in c))!=mode:raise ValueError('Invalid observed mode')
            tot={k:sum(x[k] for x in trial['carryEvidence']) for k in KEYS}
            a,b=(r['quality']['football'] for r in (base,trial))
            def rate(x):
                p,q=sum(x['passes']),sum(x['completed'])
                if not 0<=q<=p or p<=0:raise ValueError('Invalid passes')
                return q/p
            result['pairs'].append(dict(fixtureSha256=fid,**tot,boxEntryDelta=b['totalControlledBoxCrossings']-a['totalControlledBoxCrossings'],
                shotDelta=b['totalShots']-a['totalShots'],passCompletionDelta=rate(b)-rate(a)))
        rows=result['pairs']
        result.update(passed=True,candidateForFurtherReview=bool(sum(x['progressed'] for x in rows)>=2 and
            sum(x['boxEntryDelta'] for x in rows)>=2 and all(x['boxEntryDelta']>=0 and x['lost']<=x['progressed'] and x['shotDelta']>=-1 and x['passCompletionDelta']>=-.05 for x in rows)))
    except (ValueError,KeyError,TypeError,AttributeError) as e:result['failureType']=type(e).__name__
    return result

def main():
    from native_av_attack_comparison import run_one
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path);p.add_argument('fixtures',type=Path,nargs=2);p.add_argument('report',type=Path)
    a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='tribun-carry-av-') as t:
        root=Path(t);pairs=[]
        for i,f in enumerate(a.fixtures):
            fixture=root/f'fixture-{i}.json';fixture.write_bytes(f.read_bytes())
            order=(False,True) if i==0 else (True,False)
            rows={m:run_one(a.runtime.resolve(),fixture,root/f'{i}-{int(m)}','short-match',controlled_carry=m) for m in order}
            pairs.append([rows[False],rows[True]])
        result=compare(pairs)
    result.update(rows=pairs,candidateCommit=candidate(),runtime=runtime_identity(a.runtime),scope='Two full AV pairs; carry progress is at least 2m with confirmed same-player control, not proof of beating a named defender or carrying across box line. Box and timed-pass modes remain separate.')
    a.report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2,allow_nan=False))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
