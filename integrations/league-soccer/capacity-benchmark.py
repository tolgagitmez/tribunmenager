"""Measure actual concurrent CPU matches; no claim of production capacity."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import threading
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("fixed",HERE/"fixed-duration.py")
fixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixed)
SCENARIOS=("counter-possession","balanced","possession-counter")
def evaluate(rows,expected):
    if expected not in (1,2,3) or len(rows)!=expected:
        raise ValueError("Invalid concurrency sample")
    passed=[r for r in rows if r.get("ok")]
    overlap=0
    if len(passed)==expected:
        overlap=max(0,round((min(r["finalObservedMonotonic"] for r in passed)-max(r["firstObservedMonotonic"] for r in passed))*1000))
    resources=all(isinstance(r.get("resources"),dict) for r in passed) and len(passed)==expected
    checks={"allMatchesValidated":len(passed)==expected,
            "actualOverlap":overlap>=240000,
            "exactNativeTicks":len(passed)==expected and all(r["exactNativeDuration"] for r in passed),
            "wallWithinOneSecond":len(passed)==expected and all(abs(r["observedWallMs"]-300000)<=1000 for r in passed),
            "observedTraceGapBelowOneSecond":len(passed)==expected and all(r["maxObservedGapMs"]<=1000 for r in passed),
            "resourceMeasurements":resources}
    return {"concurrency":expected,"checks":checks,"diagnosticPassed":all(checks.values()),
            "commonObservedOverlapMs":overlap,
            "totalCpuSeconds":sum(r["resources"]["userSeconds"]+r["resources"]["systemSeconds"] for r in passed) if resources else None,
            "sumIndividualPeakRssKiB":sum(r["resources"]["maxRssKiB"] for r in passed) if resources else None,
            "matches":rows}

def run_group(runtime,fixtures,out,n):
    barrier=threading.Barrier(n)
    def work(index):
        name=SCENARIOS[index]
        prefix=str(out/("n"+str(n)+"-"+name))
        try:
            barrier.wait(timeout=15)
            row=fixed.timing.run(runtime,str(fixtures/(name+".json")),prefix,("fixed","1.0","0"),"short-match",True)
            with Path(prefix+".fixed.ndjson").open() as f:row.update(fixed.verify(json.loads(line) for line in f))
            return {"scenario":name,"ok":True,**row}
        except Exception as exc:
            return {"scenario":name,"ok":False,"error":type(exc).__name__,"detail":str(exc)}
    with ThreadPoolExecutor(max_workers=n) as pool:
        return evaluate(list(pool.map(work,range(n))),n)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime");p.add_argument("fixtures");p.add_argument("out")
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    fixtures=Path(a.fixtures).resolve()
    groups=[]
    for n in (1,2,3):
        groups.append(run_group(a.runtime,fixtures,out,n))
        report={"schema":1,"authoritative":False,"host":{"logicalCpus":os.cpu_count(),
            "affinityCpus":len(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else None},
            "groups":groups,"largestPassingGroup":max((g["concurrency"] for g in groups if g["diagnosticPassed"]),default=0),
            "note":"One sample per concurrency level. Peak RSS sum is not simultaneous aggregate memory; no production throughput/FPS guarantee."}
        (out/"capacity.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
        print(json.dumps(groups[-1]),flush=True)
    # Fail the diagnostic job when any simulated match cannot finish/validate.
    if any(not g["checks"]["allMatchesValidated"] for g in groups):raise SystemExit("One or more concurrent matches failed")

if __name__=="__main__":main()
