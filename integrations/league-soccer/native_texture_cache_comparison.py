"""Private diffuse texture bind comparison; no material or shader value changes."""
import argparse
import json
import math
from pathlib import Path
import re
import tempfile
from native_render_resolution_comparison import metrics
from native_release_gate import candidate,runtime_identity

def parse_texture(text,mode):
    if type(mode) is not int or mode not in (0,1):raise ValueError('Invalid mode')
    rows=[tuple(map(int,x)) for x in re.findall(r'^\[tribun-texture-cache\] mode=([01]) calls=(\d+) changes=(\d+) binds=(\d+) repeats=(\d+)\s*$',text,re.MULTILINE)]
    if not rows:raise ValueError('No texture samples')
    previous=(0,0,0,0)
    for i,(m,c,e,b,r) in enumerate(rows):
        if m!=mode or c!=(i+1)*256 or any(x<y for x,y in zip((c,e,b,r),previous)):
            raise ValueError('Inconsistent counters')
        de,db,dr=e-previous[1],b-previous[2],r-previous[3]
        if not 0<=dr<=de or db!=(de-dr if mode else de):
            raise ValueError('Incorrect diffuse bind count')
        previous=(c,e,b,r)
    _,c,e,b,r=rows[-1]
    if e<=0:raise ValueError('No material transitions')
    return {'mode':mode,'calls':c,'materialTransitions':e,'diffuseBinds':b,'sameDiffuseTransitions':r,'bindsPerTransition':b/e,
        'scope':'Measured diffuse binds at material transition only; excludes final unbind and all other texture units; last partial block omitted.'}

def compare(rows):
    result={'passed':False,'candidateForFurtherReview':False,'automaticPromotion':False,'productionQualified':False,'delta':None}
    try:
        if len(rows)!=2 or [r['textureCache'] for r in rows]!=[0,1] or not rows[0]['fixtureSha256'] or rows[0]['fixtureSha256']!=rows[1]['fixtureSha256']:raise ValueError('Invalid pair')
        for row in rows:
            e=row['textureEvidence']
            if row['renderSize']!='1280x720' or row['shadowSize']!=2048 or row['shadowEvidence']!={'width':2048,'height':2048,'observed':True} or e['mode']!=row['textureCache'] or e['calls']<256 or not math.isfinite(e['bindsPerTransition']) or not 0<e['bindsPerTransition']<=1:raise ValueError('Missing evidence')
        a,b=map(metrics,rows)
        saving=1-rows[1]['textureEvidence']['bindsPerTransition']/rows[0]['textureEvidence']['bindsPerTransition']
        result.update(passed=True,delta={k:b[k]-a[k] for k in a},bindRateSavingFraction=saving,
            candidateForFurtherReview=bool(saving>=.05 and b['swapRate']>=.95*a['swapRate'] and b['repeatedFraction']<=a['repeatedFraction']+.02 and b['dropFraction']<=.01))
    except (ValueError,KeyError,TypeError,AttributeError,ZeroDivisionError) as e:result['failureType']=type(e).__name__
    return result

def main():
    from native_av_attack_comparison import run_one
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runtime',type=Path);p.add_argument('fixture',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='tribun-texture-cache-') as t:
        root=Path(t);fixture=root/'fixture.json';fixture.write_bytes(a.fixture.read_bytes())
        rows=[run_one(a.runtime.resolve(),fixture,root/str(mode),'baseline',render_size='1280x720',shadow_size=2048,texture_cache=mode) for mode in (0,1)]
        result=compare(rows)
    result.update(rows=rows,candidateCommit=candidate(),runtime=runtime_identity(a.runtime),scope='One sequential matched AV pair. Bind counts are not GPU timing, actual FPS or proof of pixel equivalence.')
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
