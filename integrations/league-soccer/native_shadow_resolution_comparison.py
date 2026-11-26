"""Private native shadow/window experiment; no automatic selection."""
import argparse
import json
from pathlib import Path
import re
import tempfile
from native_render_resolution_comparison import compare as compare_window,metrics
from native_release_gate import candidate,runtime_identity

def shadow_evidence(text,expected):
    if type(expected) is not int or expected not in (1024,2048):raise ValueError('Invalid requested size')
    found=re.findall(r'^\[tribun-render\] shadow-viewport=(\d+)x(\d+)\s*$',text,re.MULTILINE)
    if found!=[(str(expected),str(expected))]:raise ValueError('Missing or mismatched actual shadow viewport')
    return {'width':expected,'height':expected,'observed':True}

def compare_shadow(rows):
    result={'passed':False,'candidateForFurtherReview':False,'automaticPromotion':False,'productionQualified':False,'delta':None}
    try:
        if len(rows)!=2 or [r['shadowSize'] for r in rows]!=[2048,1024] or any(r['renderSize']!='1280x720' for r in rows) or not rows[0]['fixtureSha256'] or rows[0]['fixtureSha256']!=rows[1]['fixtureSha256']:
            raise ValueError('Mismatched comparison')
        for row in rows:
            n=row['shadowSize']
            if row['shadowEvidence']!={'width':n,'height':n,'observed':True}:raise ValueError('Missing actual viewport')
        a,b=map(metrics,rows)
        delta={k:b[k]-a[k] for k in a}
        result.update(passed=True,delta=delta,candidateForFurtherReview=bool(delta['repeatedFraction']<=-.05 and delta['longestIdenticalSeconds']<=0 and b['swapRate']>=1.10*a['swapRate'] and b['swapP95GapMs']<=a['swapP95GapMs'] and b['dropFraction']<=.01))
    except (ValueError,KeyError,TypeError,AttributeError) as e:result['failureType']=type(e).__name__
    return result

def main():
    from native_av_attack_comparison import run_one
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runtime',type=Path);p.add_argument('fixture',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='tribun-shadow-resolution-') as t:
        root=Path(t);fixture=root/'fixture.json';fixture.write_bytes(a.fixture.read_bytes())
        rows=[run_one(a.runtime.resolve(),fixture,root/name,'baseline',render_size=window,shadow_size=shadow)
              for name,window,shadow in [('baseline','1280x720',2048),('shadow','1280x720',1024),('window','960x540',2048)]]
        shadow=compare_shadow(rows[:2]);window=compare_window([rows[0],rows[2]])
    result={'passed':shadow['passed'] and window['passed'],'rows':rows,'shadowComparison':shadow,'windowComparison':window,'productionQualified':False,'automaticPromotion':False,'candidateCommit':candidate(),'runtime':runtime_identity(a.runtime),'scope':'Three sequential full matches; shared baseline, not deterministic or replicated. Reduced shadow detail possible; 960x540 upscaled.'}
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
