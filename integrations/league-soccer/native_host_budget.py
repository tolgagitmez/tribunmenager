"""Summarize host diagnostic trials without claiming capacity from engine exit alone."""
import argparse
import json
from pathlib import Path

def summarize(reports):
    rows=[]
    for label,r in reports.items():
        matches=r.get('matches',[])
        rows.append({'trial':label,'requestedMatches':r.get('requestedMatches'),
            'passed':r.get('passed') is True,'realMatchSeconds':[m.get('observedWallSeconds') for m in matches],
            'browserExits':[m.get('browserExit') for m in matches],
            'cpuP95':r.get('resourceSummary',{}).get('cpuP95Percent'),
            'engineCpuSeconds':r.get('processProfile',{}).get('roles',{}).get('engine_with_software_gl',{}).get('observedCpuSecondsLowerBound')})
    return {'trials':rows,'productionQualified':False,
            'scope':'One runner, baseline and experimental diagnostic trials; no guaranteed capacity.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    reports={}
    for label in ('single','dual-baseline','dual-bounded'):
        f=a.root/label/'capacity-report.json'
        if f.is_file():reports[label]=json.loads(f.read_text())
    a.output.write_text(json.dumps(summarize(reports),indent=2)+'\n')
