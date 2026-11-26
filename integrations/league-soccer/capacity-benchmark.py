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

def host_limits(root=Path("/sys/fs/cgroup")):
    """Best effort Linux cgroup v2 snapshot; unknown limits remain unknown."""
    def read(name):
        try:return (root/name).read_text().strip()
        except OSError:return None
    def quota():
        v=read("cpu.max")
        if not v:return None
        try:
            maximum,period=v.split()
            if maximum=="max":return None
            maximum,period=int(maximum),int(period)
            return maximum/period if maximum>0 and period>0 else None
        except (ValueError,ZeroDivisionError):return None
    def memory():
        v=read("memory.max")
        try:return int(v) if v is not None and v!="max" and int(v)>0 else None
        except ValueError:return None
    return {"logicalCpus":os.cpu_count(),
        "affinityCpus":len(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else None,
        "cgroupCpuQuotaCores":quota(),"cgroupMemoryLimitBytes":memory(),
        "cgroupCpuStat":read("cpu.stat"),"cgroupCpuset":read("cpuset.cpus.effective")}

def run_group(runtime,fixtures,out,n,render_threads=2):
    before=host_limits()
    barrier=threading.Barrier(n)
    def work(index):
        name=SCENARIOS[index]
        prefix=str(out/("n"+str(n)+"-"+name))
        try:
            barrier.wait(timeout=15)
            row=fixed.timing.run(runtime,str(fixtures/(name+".json")),prefix,("fixed","1.0","0"),"short-match",True,render_threads=render_threads)
            with Path(prefix+".fixed.ndjson").open() as f:row.update(fixed.verify(json.loads(line) for line in f))
            return {"scenario":name,"ok":True,**row}
        except Exception as exc:
            return {"scenario":name,"ok":False,"error":type(exc).__name__,"detail":str(exc)}
    with ThreadPoolExecutor(max_workers=n) as pool:
        result=evaluate(list(pool.map(work,range(n))),n)
    return {**result,"softwareRenderThreads":render_threads,"hostBefore":before,"hostAfter":host_limits()}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime");p.add_argument("fixtures");p.add_argument("out")
    p.add_argument("--render-threads",type=int,choices=(1,2,3,4),default=2)
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    fixtures=Path(a.fixtures).resolve()
    groups=[]
    for n in (1,2,3):
        groups.append(run_group(a.runtime,fixtures,out,n,a.render_threads))
        report={"schema":1,"authoritative":False,"host":host_limits(),"softwareRenderThreads":a.render_threads,
            "groups":groups,"largestPassingGroup":max((g["concurrency"] for g in groups if g["diagnosticPassed"]),default=0),
            "note":"One sample per concurrency level. Peak RSS sum is not simultaneous aggregate memory; no production throughput/FPS guarantee."}
        from release_evidence import stamp
        report=stamp(report,a.runtime,"capacity")
        (out/"capacity.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
        print(json.dumps(groups[-1]),flush=True)
    # Fail the diagnostic job when any simulated match cannot finish/validate.
    if any(not g["checks"]["allMatchesValidated"] for g in groups):raise SystemExit("One or more concurrent matches failed")

if __name__=="__main__":main()
