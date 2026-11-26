"""Compare full native skinning with repeated joint-offset products cached."""
import argparse
import json
import math
from pathlib import Path
import re
import tempfile
from native_render_resolution_comparison import metrics
from native_release_gate import candidate,runtime_identity

def parse_skin(text,mode):
    if type(mode) is not int or mode not in (0,1):raise ValueError('Invalid mode')
    rows=[tuple(map(int,r)) for r in re.findall(r'^\[tribun-skin-cache\] mode=([01]) calls=(\d+) ns=(\d+)\s*$',text,re.MULTILINE)]
    if not rows or any(m!=mode or c!=(i+1)*256 or n<=0 or (i and n<=rows[i-1][2]) for i,(m,c,n) in enumerate(rows)):
        raise ValueError('Missing or inconsistent native skinning samples')
    _,calls,ns=rows[-1]
    return {'mode':mode,'sampledCalls':calls,'cumulativeThreadWallNs':ns,'meanCallMs':ns/calls/1e6,
            'scope':'Cumulative measured update-call wall times, including lock waits; overlapping calls are not process CPU time. Last partial block omitted.'}

def compare(rows):
    result={'passed':False,'candidateForFurtherReview':False,'automaticPromotion':False,'productionQualified':False,'delta':None}
    try:
        if len(rows)!=2 or [r['skinCache'] for r in rows]!=[0,1] or not rows[0]['fixtureSha256'] or rows[0]['fixtureSha256']!=rows[1]['fixtureSha256']:raise ValueError('Invalid matched pair')
        for row in rows:
            e=row['skinEvidence']
            if row['renderSize']!='1280x720' or row['shadowSize']!=2048 or row['shadowEvidence']!={'width':2048,'height':2048,'observed':True} or e['mode']!=row['skinCache'] or e['sampledCalls']<256 or not math.isfinite(e['meanCallMs']) or e['meanCallMs']<=0:raise ValueError('Missing observed evidence')
        a,b=map(metrics,rows)
        delta={k:b[k]-a[k] for k in a}
        saving=1-rows[1]['skinEvidence']['meanCallMs']/rows[0]['skinEvidence']['meanCallMs']
        result.update(passed=True,delta=delta,meanUpdateTimeSavingFraction=saving,
            candidateForFurtherReview=bool(saving>=.05 and b['swapRate']>=a['swapRate']*.95 and b['repeatedFraction']<=a['repeatedFraction']+.02 and b['dropFraction']<=.01))
    except (KeyError,ValueError,TypeError,AttributeError,ZeroDivisionError) as e:result['failureType']=type(e).__name__
    return result

def main():
    from native_av_attack_comparison import run_one
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runtime',type=Path);p.add_argument('fixture',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='tribun-skin-cache-') as t:
        root=Path(t);fixture=root/'fixture.json';fixture.write_bytes(a.fixture.read_bytes())
        rows=[run_one(a.runtime.resolve(),fixture,root/str(mode),'baseline',render_size='1280x720',shadow_size=2048,skin_cache=mode) for mode in (0,1)]
        result=compare(rows)
    result.update(rows=rows,candidateCommit=candidate(),runtime=runtime_identity(a.runtime),scope='One sequential full AV pair, same fixture and seed, no proof of deterministic pose equivalence or CPU saving.')
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
