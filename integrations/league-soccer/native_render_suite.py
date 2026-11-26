"""Same-build native renderer suite. Select diagnostic candidates only, never a release."""
import argparse
import json
import math
from pathlib import Path
import tempfile
from native_render_resolution_comparison import metrics
from native_release_gate import candidate,runtime_identity
from native_scheduler_policy import fingerprint

KEYS=('skinCache','vaoCache','textureCache')
EVIDENCE=('skinEvidence','vaoEvidence','textureEvidence')
BASE=(0,0,0)

def modes(row):
    vals=tuple(row.get(k) for k in KEYS)
    if any(type(v) is not int or v not in (0,1) for v in vals):raise ValueError('Invalid mode')
    return vals

def validate(row,expected,fixture):
    if row.get('renderSuite') is not True or modes(row)!=expected or not fixture or row.get('fixtureSha256')!=fixture or row.get('renderSize')!='1280x720' or row.get('shadowSize')!=2048:
        raise ValueError('Mismatched suite context')
    if row.get('windowGeometry')!={'width':1280,'height':720,'requested':'1280x720','verified':True} or row.get('shadowEvidence')!={'width':2048,'height':2048,'observed':True}:
        raise ValueError('Missing geometry evidence')
    for k,v in zip(EVIDENCE,expected):
        e=row[k]
        if e.get('mode')!=v:raise ValueError('Missing observed mode')
        count=e.get('sampledCalls' if k=='skinEvidence' else 'calls')
        if type(count) is not int or count<256:raise ValueError('Insufficient samples')
    costs=(row['skinEvidence']['meanCallMs'],row['vaoEvidence']['bindsPerEntry'],row['textureEvidence']['bindsPerTransition'])
    if any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in costs) or any(x>1 for x in costs[1:]):
        raise ValueError('Invalid costs')
    return metrics(row),costs

def no_regression(a,b):
    return (b['swapRate']>=.95*a['swapRate'] and b['swapP95GapMs']<=1.10*a['swapP95GapMs']
        and b['repeatedFraction']<=a['repeatedFraction']+.02
        and b['longestIdenticalSeconds']<=a['longestIdenticalSeconds']+.1 and b['dropFraction']<=.01)

def assess_individual(rows):
    result={'selected':[0,0,0],'individual':{},'baselineValid':False}
    if not rows:return result
    fixture=rows[0].get('fixtureSha256')
    try:a,ac=validate(rows[0],BASE,fixture)
    except (ValueError,KeyError,TypeError,AttributeError):return result
    result['baselineValid']=True
    for i,key in enumerate(KEYS):
        expected=tuple(int(j==i) for j in range(3))
        try:
            b,bc=validate(rows[i+1],expected,fixture)
            saving=1-bc[i]/ac[i]
            accepted=saving>=.05 and no_regression(a,b)
            result['selected'][i]=int(accepted)
            result['individual'][key]={'eligible':accepted,'costSavingFraction':saving,'swapRateDelta':b['swapRate']-a['swapRate']}
        except (IndexError,ValueError,KeyError,TypeError,AttributeError,ZeroDivisionError) as e:
            result['individual'][key]={'eligible':False,'failureType':type(e).__name__}
    return result

def assess_combined(rows,selection,combined,repeat):
    result={'combinedReviewEligible':False,'productionQualified':False,'automaticPromotion':False,'reason':'no-selected-options'}
    selected=tuple(selection['selected'])
    if not any(selected):return result
    if combined is None or repeat is None:
        result['reason']='missing-combined-or-repeat-baseline'
        return result
    try:
        fixture=rows[0]['fixtureSha256']
        a,ac=validate(rows[0],BASE,fixture)
        b,bc=validate(combined,selected,fixture)
        c,cc=validate(repeat,BASE,fixture)
        # Bracket candidates with a second baseline to reject obvious drift.
        drift=abs(c['swapRate']/a['swapRate']-1)<=.10 and abs(c['repeatedFraction']-a['repeatedFraction'])<=.05
        savings=[1-bc[i]/max(ac[i],cc[i]) for i in range(3)]
        # Demand improvement versus both baselines, not just lower command counts.
        visual=all(b['swapRate']>=1.05*x['swapRate'] and b['repeatedFraction']<=x['repeatedFraction']-.02 and no_regression(x,b) for x in (a,c))
        accepted=drift and visual and all(savings[i]>=.05 for i in range(3) if selected[i])
        result.update(combinedReviewEligible=accepted,reason='candidate-for-repeated-review' if accepted else 'drift-or-insufficient-gain',
            baselineStable=drift,relativeCostSavingFractions=savings,visualScreenPassed=visual)
    except (ValueError,KeyError,TypeError,AttributeError,ZeroDivisionError) as e:result['reason']=type(e).__name__
    return result

def main():
    from native_av_attack_comparison import run_one
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path);p.add_argument('fixture',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args();runtime=a.runtime.resolve()
    identity=runtime_identity(runtime);host=fingerprint(runtime);commit=candidate()
    with tempfile.TemporaryDirectory(prefix='tribun-render-suite-') as t:
        root=Path(t);fixture=root/'fixture.json';fixture.write_bytes(a.fixture.read_bytes())
        def run(name,m):
            return run_one(runtime,fixture,root/name,'baseline',render_size='1280x720',shadow_size=2048,
                skin_cache=m[0],vao_cache=m[1],texture_cache=m[2],render_suite=True)
        rows=[run('baseline',BASE)]
        if rows[0].get('passed') is True:
            for i in range(3):rows.append(run(KEYS[i],tuple(int(j==i) for j in range(3))))
        selection=assess_individual(rows)
        combined=repeat=None
        if any(selection['selected']):
            combined=run('combined',tuple(selection['selected']))
            repeat=run('repeat-baseline',BASE)
        verdict=assess_combined(rows,selection,combined,repeat)
    stable=identity==runtime_identity(runtime) and host==fingerprint(runtime) and commit==candidate()
    if not stable:verdict.update(combinedReviewEligible=False,reason='build-or-host-changed')
    result={'schema':1,'candidateCommit':commit,'runtime':identity,'host':host,'contextStable':stable,
        'rows':rows,'selection':selection,'combined':combined,'repeatBaseline':repeat,'verdict':verdict,
        'passed':bool(stable and selection['baselineValid'] and len(rows)==4 and all(x.get('passed') is True for x in rows)
            and (not any(selection['selected']) or (combined and combined.get('passed') is True and repeat and repeat.get('passed') is True))),
        'productionQualified':False,'automaticPromotion':False,
        'scope':'Private full AV diagnostic with one fixture/seed, software rendering, 720p native window, 2048 shadows. Bracketed baseline not deterministic, no pixel equivalence, no public or concurrent capacity qualification.'}
    a.report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2,allow_nan=False))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
