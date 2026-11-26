"""Rendered native lead-pass trial with actual touch and receipt counters."""
import argparse
import json
from pathlib import Path
import tempfile
from native_release_gate import candidate,runtime_identity

KEYS=('passes','receipts','shots')
def trace_counts(path):
    previous=[dict.fromkeys(KEYS,0) for _ in range(2)]
    final=None
    with Path(path).open() as f:
        for line in f:
            row=json.loads(line)
            counts=row.get('timedAttacks')
            if not isinstance(counts,list) or len(counts)!=2:raise ValueError('Missing timed attack counters')
            for i,c in enumerate(counts):
                if not isinstance(c,dict) or any(type(c.get(k)) is not int or c[k]<previous[i][k] for k in KEYS) or not 0<=c['shots']<=c['receipts']<=c['passes']:
                    raise ValueError('Invalid native counters')
            previous=[{k:c[k] for k in KEYS} for c in counts]
            final=row
    if not final or final.get('done') is not True:raise ValueError('Incomplete native match')
    return previous

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
                if row.get('passed') is not True or row.get('profile')!='short-match' or row.get('timedPass') is not mode or row.get('boxLane') is not False:raise ValueError('Incomplete recording')
                c=row['timedEvidence']
                if len(c)!=2 or any(any(type(t.get(k)) is not int for k in KEYS) or not 0<=t['shots']<=t['receipts']<=t['passes'] for t in c):raise ValueError('Invalid counters')
                if not mode and any(t['passes'] for t in c):raise ValueError('Baseline contaminated')
            c=trial['timedEvidence'];tot={k:sum(x[k] for x in c) for k in KEYS}
            if not tot['passes']:raise ValueError('No actual qualifying pass contact')
            a,b=(r['quality']['football'] for r in (base,trial))
            def pass_rate(x):
                p=sum(x['passes']);q=sum(x['completed'])
                if not 0<=q<=p or not p:raise ValueError('Invalid pass total')
                return q/p
            result['pairs'].append(dict(fixtureSha256=fid,actualLeadPasses=tot['passes'],controlledReceipts=tot['receipts'],followupShots=tot['shots'],
                boxEntryDelta=b['totalControlledBoxCrossings']-a['totalControlledBoxCrossings'],onTargetDelta=sum(b['onTarget'])-sum(a['onTarget']),passCompletionDelta=pass_rate(b)-pass_rate(a)))
        rows=result['pairs']
        result.update(passed=True,candidateForFurtherReview=bool(sum(x['controlledReceipts'] for x in rows)>=2 and
            sum(x['boxEntryDelta'] for x in rows)>=2 and all(x['boxEntryDelta']>=0 and x['passCompletionDelta']>=-.05 for x in rows) and sum(x['onTargetDelta'] for x in rows)>=0))
    except (ValueError,KeyError,TypeError,AttributeError) as e:result['failureType']=type(e).__name__
    return result

def main():
    from native_av_attack_comparison import run_one
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path);p.add_argument('fixtures',type=Path,nargs=2);p.add_argument('report',type=Path)
    a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='tribun-timed-pass-') as t:
        root=Path(t);pairs=[]
        for i,f in enumerate(a.fixtures):
            fixture=root/f'fixture-{i}.json';fixture.write_bytes(f.read_bytes())
            order=(False,True) if i==0 else (True,False)
            rows={mode:run_one(a.runtime.resolve(),fixture,root/f'{i}-{int(mode)}','short-match',timed_pass=mode) for mode in order}
            pairs.append([rows[False],rows[True]])
        result=compare(pairs)
    result.update(rows=pairs,candidateCommit=candidate(),runtime=runtime_identity(a.runtime),scope='Two full AV fixture pairs; qualifying native long-pass contact and subsequent possession, not proof that each pass originated from the new ranking branch. No simultaneous box-lane activation or promotion.')
    a.report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2,allow_nan=False))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
