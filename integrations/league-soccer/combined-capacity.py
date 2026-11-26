"""Stage 103: concurrent combined AI load diagnostic, not production capacity."""
import argparse
from bisect import bisect_left
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import math
from pathlib import Path
import json
import threading
import time
from release_evidence import stamp, fingerprint, sha
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("combined",HERE/"combined-ai-benchmark.py")
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
I=C.I
LEVELS=(1,2,3)

def aligned_pss(rows):
    """One-second grid in common observed play interval; nearest sample <=0.75s.
    Missing data is not zero. This is sampled native PSS, not host total RAM."""
    start=max(r["firstObservedMonotonic"] for r in rows)
    end=min(r["finalObservedMonotonic"] for r in rows)
    tracks=[]
    for r in rows:
        samples=r["nativeMemory"]["samples"]
        times=[s["monotonic"] for s in samples]
        if (not times or any(type(t) not in (int,float) or not math.isfinite(t) for t in times)
                or any(a>=b for a,b in zip(times,times[1:]))
                or any(type(s.get("Pss")) is not int or s["Pss"]<=0 for s in samples)):
            raise ValueError("Invalid PSS time series")
        tracks.append((times,samples))
    expected=0; totals=[]
    for t in range(math.ceil(start),math.floor(end)+1):
        expected+=1; total=0
        for times,samples in tracks:
            j=bisect_left(times,t)
            choices=[i for i in (j-1,j) if 0<=i<len(times)]
            i=min(choices,key=lambda i:abs(times[i]-t))
            if abs(times[i]-t)>.75:break
            total+=samples[i]["Pss"]
        else:totals.append(total)
    return {"expectedSamples":expected,"alignedSamples":len(totals),
            "coverage":len(totals)/expected if expected else 0,
            "peakAlignedPssKiB":max(totals,default=None),
            "note":"Nearest samples within 0.75s, not exact simultaneous or host memory."}

def evaluate(rows,n,budget_kib=None):
    if type(n) is not int or n not in LEVELS or len(rows)!=n or len({r["job"] for r in rows})!=n:
        raise ValueError("Invalid distinct worker group")
    complete=all(r.get("ok") is True for r in rows)
    valid=complete
    if complete:
        try:
            for r in rows:C.validate(r,True)
            valid=len({r["hardwareThreads"] for r in rows})==1
        except (KeyError,TypeError,ValueError):valid=False
    overlap=round(max(0,min(r["finalObservedMonotonic"] for r in rows)-max(r["firstObservedMonotonic"] for r in rows))*1000) if valid else 0
    memory={"expectedSamples":0,"alignedSamples":0,"coverage":0,"peakAlignedPssKiB":None}
    if valid:
        try:memory=aligned_pss(rows)
        except (KeyError,TypeError,ValueError):pass
    checks={"allMatchesValidated":bool(valid),"overlap240Seconds":overlap>=240000,
            "delivery":bool(valid and all(I.wall_ok(r) for r in rows)),
            "memoryCoverage":memory["coverage"]>=.90 and memory["peakAlignedPssKiB"] is not None,
            "memoryBudget":bool(memory["peakAlignedPssKiB"] is not None and (budget_kib is None or memory["peakAlignedPssKiB"]<=budget_kib))}
    return {"concurrency":n,"checks":checks,"diagnosticPassed":all(checks.values()),
            "commonObservedOverlapMs":overlap,"nativePss":memory,"memoryBudgetKiB":budget_kib,
            "sumIndividualPeakPssKiB":sum(r["nativeMemory"]["peakPssKiB"] for r in rows) if valid else None,
            "totalCpuSeconds":sum(I.cpu(r) for r in rows) if valid else None,"matches":rows}

def run_group(runtime,fixtures,out,n,runner=None,check_disk=True,budget_kib=None):
    if type(n) is not int or n not in LEVELS:raise ValueError("Invalid worker bound")
    if check_disk:I.capacity.disk_budget(runtime,out,n)
    barrier=threading.Barrier(n)
    before=I.capacity.capacity.host_limits()
    def work(i):
        scenario=C.SCENARIOS[i%len(C.SCENARIOS)]
        job=f"combined-n{n}-{i:02d}-{scenario}"
        prefix=out/job
        try:
            barrier.wait(timeout=15)
            if runner is None:
                row=I.run(runtime,fixtures/(scenario+".json"),prefix,True,combined_ai=True)
                trace=Path(str(prefix)+".candidate.ndjson")
                row["traceSha256"]=sha(trace)
            else:row=runner(i,scenario)
            return {**row,"job":job,"scenario":scenario,"ok":True}
        except Exception as exc:
            return {"job":job,"scenario":scenario,"ok":False,"error":type(exc).__name__,"detail":str(exc)}
    start=time.monotonic()
    with ThreadPoolExecutor(max_workers=n,thread_name_prefix="combined-native") as pool:
        rows=list(pool.map(work,range(n)))
    return {**evaluate(rows,n,budget_kib),"hostBefore":before,"hostAfter":I.capacity.capacity.host_limits(),
            "groupWallMs":round((time.monotonic()-start)*1000)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    p.add_argument("--native-pss-budget-mib",type=int)
    a=p.parse_args()
    if a.native_pss_budget_mib is not None and a.native_pss_budget_mib<=0:p.error("Positive PSS budget required")
    a.out.mkdir(parents=True,exist_ok=False)
    identity=I.capacity.fingerprint(a.runtime,a.fixtures)
    report=stamp({"schema":1,"authoritative":False,"productionEnabled":False,
      "identity":identity,"status":"incomplete","groups":[],"requestedLevels":list(LEVELS),
      "largestPassingGroup":0,"note":"Single group per level on this host. No player/network load, full host RAM, sustained production or game-quality claim."},a.runtime,"combined-capacity")
    def save():
        if I.capacity.fingerprint(a.runtime,a.fixtures)!=identity or fingerprint()!=report["evidence"]["candidateSha256"]:raise ValueError("Frozen inputs changed")
        I.save(a.out/"combined-capacity.json",report)
    save()
    for n in LEVELS:
        group=run_group(a.runtime,a.fixtures,a.out,n,budget_kib=a.native_pss_budget_mib*1024 if a.native_pss_budget_mib else None)
        report["groups"].append(group)
        if group["diagnosticPassed"]:report["largestPassingGroup"]=n
        else:report["status"]="blocked"
        save()
        print(json.dumps({k:v for k,v in group.items() if k!="matches"}),flush=True)
        if not group["diagnosticPassed"]:raise SystemExit(2)
    report["status"]="manual-review-required";save()
if __name__=="__main__":main()
