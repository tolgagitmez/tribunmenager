"""Sequential private native resolution experiment; no automatic quality selection."""
import argparse
import json
import math
from pathlib import Path
import tempfile
from native_av_attack_comparison import run_one
from native_release_gate import candidate,runtime_identity
SIZES=('1280x720','960x540')

def metrics(row):
    if row.get('passed') is not True:raise ValueError('Incomplete recording')
    p=row['quality']['presentation'];r=row['renderProbe']
    values={'wallSeconds':p['realMatchSeconds'],'repeatedFraction':p['repeatedReducedImageFraction'],
        'longestIdenticalSeconds':p['longestIdenticalImageSeconds'],'swapRate':r['averageSwapsPerSecond'],
        'swapP95GapMs':r['p95GapMs'],'dropFraction':p['droppedFraction'],'coverage':p['browserCoverage']}
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in values.values()):raise ValueError('Invalid measurements')
    if not 295<=values['wallSeconds']<=305 or not .95<=values['coverage']<=1.01:raise ValueError('Invalid playback duration')
    if not 0<=values['repeatedFraction']<=1 or not 0<=values['dropFraction']<=1 or values['swapRate']<=0:raise ValueError('Invalid frame metrics')
    return values

def compare(rows):
    result={'passed':False,'candidateForFurtherReview':False,'productionQualified':False,'automaticPromotion':False,'rows':rows,'delta':None}
    try:
        if len(rows)!=2 or tuple(r['renderSize'] for r in rows)!=SIZES or not rows[0]['fixtureSha256'] or rows[0]['fixtureSha256']!=rows[1]['fixtureSha256']:
            raise ValueError('Invalid matched pair')
        a,b=map(metrics,rows)
        delta={k:b[k]-a[k] for k in a}
        result.update(passed=True,delta=delta,candidateForFurtherReview=bool(
            delta['repeatedFraction']<=-.05 and delta['longestIdenticalSeconds']<=0 and
            b['swapRate']>=1.10*a['swapRate'] and b['swapP95GapMs']<=a['swapP95GapMs']
            and b['dropFraction']<=.01))
    except (KeyError,ValueError,TypeError,AttributeError) as exc:result['failureType']=type(exc).__name__
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runtime',type=Path);p.add_argument('fixture',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='tribun-native-resolution-') as t:
        root=Path(t);fixture=root/'fixture.json';fixture.write_bytes(a.fixture.read_bytes())
        rows=[run_one(a.runtime.resolve(),fixture,root/size,'baseline',render_size=size) for size in SIZES]
        result=compare(rows)
    result.update(candidateCommit=candidate(),runtime=runtime_identity(a.runtime),scope='720p25 output for both; 960x540 native window upscaled. One sequential pair, swap calls not unique frames; image quality and performance not production qualified.')
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
