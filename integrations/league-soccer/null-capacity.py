"""Bounded, display-free native worker capacity pilot. Never writes league state."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import tempfile
import threading
import time

HERE=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+".py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
capacity=load("capacity-benchmark")
fixed=capacity.fixed
SCENARIOS=capacity.SCENARIOS
MAX_WORKERS=10

def evaluate(rows,n):
    if type(n) is not int or not 1<=n<=MAX_WORKERS or len(rows)!=n:
        raise ValueError("Invalid capacity group")
    if len({r["job"] for r in rows})!=n:
        raise ValueError("Duplicate worker jobs")
    good=[r for r in rows if r.get("ok") is True]
    complete=len(good)==n
    def valid(r):
        return (r.get("nullRenderer") is True and r.get("noDraw") is True and
                r.get("noUpload") is True and r.get("exactNativeDuration") is True and
                r.get("nativeElapsedMs")==300000 and r.get("configuredRenderIntervalMs")==100)
    modes=complete and all(valid(r) for r in good)
    def resource(r):
        values=r.get("resources")
        return isinstance(values,dict) and all(type(values.get(k)) in (int,float) and
            math.isfinite(values[k]) and values[k]>=0 for k in ("userSeconds","systemSeconds","maxRssKiB"))
    measured=complete and all(resource(r) for r in good)
    overlap=max(0,round((min(r["finalObservedMonotonic"] for r in good)-
                        max(r["firstObservedMonotonic"] for r in good))*1000)) if complete else 0
    checks={"allMatchesValidated":complete,"isolatedNullMode":modes,
            "commonOverlapAtLeast240Seconds":complete and overlap>=240000,
            "wallWithinOneSecond":complete and all(abs(r["observedWallMs"]-300000)<=1000 for r in good),
            "traceGapBelowOneSecond":complete and all(r["maxObservedGapMs"]<=1000 for r in good),
            "resourceMeasurements":measured}
    return {"concurrency":n,"checks":checks,"diagnosticPassed":all(checks.values()),
            "commonObservedOverlapMs":overlap,"matches":rows,
            "totalCpuSeconds":sum(r["resources"]["userSeconds"]+r["resources"]["systemSeconds"] for r in good) if measured else None,
            "sumIndividualPeakRssKiB":sum(r["resources"]["maxRssKiB"] for r in good) if measured else None}

def fingerprint(runtime,fixtures):
    paths=[runtime/"gameplayfootball",runtime/"tribun-runtime.json",
           runtime/"native-match.config",*(fixtures/(name+".json") for name in SCENARIOS)]
    return {str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def disk_budget(runtime,out,n):
    # run-frozen copies writable runtime data per fixture, possibly across filesystems.
    size=sum(p.stat().st_size for p in runtime.rglob("*") if p.is_file())
    temp=Path(tempfile.gettempdir())
    traces=n*120*1024*1024
    copies=n*size+512*1024*1024
    if temp.stat().st_dev==out.stat().st_dev:
        if shutil.disk_usage(temp).free<copies+traces:raise RuntimeError("Insufficient disk for isolated workers")
    elif shutil.disk_usage(temp).free<copies or shutil.disk_usage(out).free<traces:
        raise RuntimeError("Insufficient disk for isolated workers")

def run_group(runtime,fixtures,out,n,runner=None,check_disk=True):
    if type(n) is not int or not 1<=n<=MAX_WORKERS:raise ValueError("Invalid worker bound")
    if check_disk:disk_budget(runtime,out,n)
    before=capacity.host_limits()
    barrier=threading.Barrier(n)
    def work(index):
        scenario=SCENARIOS[index%len(SCENARIOS)]
        job=f"n{n}-{index:02d}-{scenario}"
        prefix=str(out/job)
        try:
            barrier.wait(timeout=15)
            if runner is None:
                row=fixed.timing.run(str(runtime),str(fixtures/(scenario+".json")),prefix,
                    ("fixed","1.0","0"),"short-match",True,render_threads=1,
                    render_interval_ms=100,no_draw=True,no_upload=True,null_renderer=True)
                with Path(prefix+".fixed.ndjson").open() as f:
                    row.update(fixed.verify(json.loads(line) for line in f))
            else:
                row=runner(index,scenario)
            return {**row,"job":job,"scenario":scenario,"ok":True}
        except Exception as exc:
            return {"job":job,"scenario":scenario,"ok":False,
                    "error":type(exc).__name__,"detail":str(exc)}
    started=time.monotonic()
    with ThreadPoolExecutor(max_workers=n,thread_name_prefix="native-null") as pool:
        rows=list(pool.map(work,range(n)))
    return {**evaluate(rows,n),"hostBefore":before,"hostAfter":capacity.host_limits(),
            "groupWallMs":round((time.monotonic()-started)*1000)}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("runtime",type=Path);parser.add_argument("fixtures",type=Path)
    parser.add_argument("out",type=Path)
    parser.add_argument("--levels",nargs="+",type=int,default=[1,2,4])
    a=parser.parse_args()
    if a.levels[0]!=1 or a.levels!=sorted(set(a.levels)) or any(n<1 or n>MAX_WORKERS for n in a.levels):
        parser.error("Levels must ascend uniquely from 1 to at most 10")
    a.out.mkdir(parents=True,exist_ok=False)
    pinned=fingerprint(a.runtime,a.fixtures)
    groups=[]
    for n in a.levels:
        if fingerprint(a.runtime,a.fixtures)!=pinned:raise ValueError("Frozen inputs changed")
        group=run_group(a.runtime,a.fixtures,a.out,n)
        if fingerprint(a.runtime,a.fixtures)!=pinned:raise ValueError("Frozen inputs changed during run")
        groups.append(group)
        report={"schema":1,"authoritative":False,"productionEnabled":False,
                "requestedLevels":a.levels,"groups":groups,"identity":pinned,
                "largestPassingGroup":max((g["concurrency"] for g in groups if g["diagnosticPassed"]),default=0),
                "note":"One isolated sample per level; peak RSS sum is not simultaneous memory. Reused fixtures are not independent gameplay samples."}
        target=a.out/"null-capacity.json"
        temp=target.with_suffix(".tmp")
        temp.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
        temp.replace(target)
        print(json.dumps(group),flush=True)
        if not group["diagnosticPassed"]:
            raise SystemExit("Capacity gate failed; larger groups not launched")
if __name__=="__main__":main()
