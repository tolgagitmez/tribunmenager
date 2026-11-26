"""Conservative paired diagnostic selection; no production activation."""
import argparse
import json
import math
from pathlib import Path
from statistics import median

def finite(v,lo=0,hi=math.inf):
    return type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi

def pair_key(r):
    return (r['hostIdentity'],r['profile'],r['filterThreads'],r['cpuPartition'],r['cpuGroups'],r['requestedMatches'],
            [m['fixtureSha256'] for m in r['matches']])

def metrics(r,workers):
    if r.get('passed') is not True or r.get('renderEvidenceComplete') is not True or r.get('renderProbeRequested') is not True or r.get('glWorkers')!=workers:
        raise ValueError('Incomplete profile evidence')
    n=r['requestedMatches']
    if n!=2 or len(r['matches'])!=n or not finite(r['overlapSeconds'],285,310):raise ValueError('Invalid concurrent trial')
    rates=[];gaps=[];maxgaps=[];drops=[];video_gaps=[];stalls=[]
    for m in r['matches']:
        if m.get('passed') is not True or m.get('softwareGLWorkers')!=workers or not finite(m['coverage'],.95,1.01):
            raise ValueError('Incomplete match evidence')
        if m['nativeClockMs']!=300000 or not finite(m['observedWallSeconds'],295,305):raise ValueError('Invalid match clock')
        p=m['renderProbe']
        if p.get('observed') is not True:raise ValueError('Missing swap evidence')
        rate=p['averageSwapsPerSecond']; gap=p['p95GapMs']; maxgap=p['maxGapMs']
        decoded,dropped=m['decodedFrames'],m['droppedFrames']
        vg=m['encodedVideoMaxGapSeconds'];stall=m['browserLongestProgressIntervalMs']
        if not all(finite(v) for v in (rate,gap,maxgap,decoded,dropped,vg,stall)) or decoded<=0 or dropped>decoded:raise ValueError('Invalid cadence counters')
        rates.append(rate);gaps.append(gap);maxgaps.append(maxgap);drops.append(dropped/decoded);video_gaps.append(vg);stalls.append(stall)
    roles=r['processProfile']['roles']
    cpu=roles['engine_with_software_gl']['observedCpuSecondsLowerBound']
    total=sum(v['observedCpuSecondsLowerBound'] for v in roles.values())
    if not finite(cpu,1) or not finite(total,cpu):raise ValueError('Missing CPU evidence')
    return {'minSwapsPerSecond':min(rates),'worstP95SwapGapMs':max(gaps),'worstMaxSwapGapMs':max(maxgaps),
            'maxDroppedFraction':max(drops),'maxEncodedVideoGapSeconds':max(video_gaps),'maxBrowserProgressIntervalMs':max(stalls),
            'engineCpuSeconds':cpu,'totalObservedCpuSeconds':total}

def acceptable(m):
    # Conservative provisional thresholds for selection, not a claim of visual quality.
    return (m['minSwapsPerSecond']>=25 and m['worstP95SwapGapMs']<=80 and m['worstMaxSwapGapMs']<=500
        and m['maxDroppedFraction']<=.01 and m['maxEncodedVideoGapSeconds']<=.12 and m['maxBrowserProgressIntervalMs']<=3000)

def compare(pairs):
    report={'productionQualified':False,'recommendedGLWorkers':None,'status':'insufficient-evidence','pairs':[],
            'note':'Swap cadence is not unique animation frames; subjective quality and production capacity remain unverified.'}
    if len(pairs)<2:return report
    try:
        trials=[r['trialId'] for pair in pairs for r in pair]
        if not all(isinstance(x,str) and len(x)==32 for x in trials) or len(set(trials))!=len(trials):raise ValueError('Repeated or invalid trial identity')
        context=pair_key(pairs[0][0])
        for baseline,candidate in pairs:
            if pair_key(baseline)!=context or pair_key(candidate)!=context:raise ValueError('Mismatched host or fixtures')
            a,b=metrics(baseline,2),metrics(candidate,1)
            report['pairs'].append({'baseline':a,'candidate':b,'baselineQualityPassed':acceptable(a),'candidateQualityPassed':acceptable(b),
                'engineCpuSavingFraction':1-b['engineCpuSeconds']/a['engineCpuSeconds'],
                'totalCpuSavingFraction':1-b['totalObservedCpuSeconds']/a['totalObservedCpuSeconds'],
                'relativeCadencePassed':b['minSwapsPerSecond']>=.95*a['minSwapsPerSecond'] and b['worstP95SwapGapMs']<=1.10*a['worstP95SwapGapMs']})
    except (KeyError,ValueError,TypeError,ZeroDivisionError,AttributeError) as e:
        report['reason']=type(e).__name__;return report
    rows=report['pairs']
    if not all(x['baselineQualityPassed'] for x in rows):
        report['status']='baseline-quality-inconclusive';return report
    report['medianEngineCpuSavingFraction']=median(x['engineCpuSavingFraction'] for x in rows)
    report['medianTotalCpuSavingFraction']=median(x['totalCpuSavingFraction'] for x in rows)
    if all(x['candidateQualityPassed'] and x['relativeCadencePassed'] and x['engineCpuSavingFraction']>=.05 and x['totalCpuSavingFraction']>=0 for x in rows):
        report.update(status='candidate-for-further-validation',recommendedGLWorkers=1)
    else:
        report.update(status='retain-baseline-for-diagnostics',recommendedGLWorkers=2)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--pair',nargs=2,action='append',type=Path,required=True)
    a=p.parse_args()
    try:pairs=[tuple(json.loads(f.read_text()) for f in pair) for pair in a.pair]
    except (OSError,ValueError):
        pairs=[]
    result=compare(pairs)
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=='__main__':main()
