"""Paired two-worker full-copy/shared asset pilot; no production promotion."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading

HERE=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
layout=load("runtime-layout")
fixed=load("fixed-duration")

def evaluate(groups):
    if set(groups)!={"copy","shared"}:raise ValueError("Both modes required")
    def summary(rows,shared):
        if len(rows)!=2 or any(r.get("sharedAssets") is not shared or r.get("nullRenderer") is not True or
            r.get("exactNativeDuration") is not True or r.get("nativeElapsedMs")!=300000 for r in rows):
            raise ValueError("Invalid paired group")
        overlap=min(r["finalObservedMonotonic"] for r in rows)-max(r["firstObservedMonotonic"] for r in rows)
        if overlap<240:raise ValueError("Insufficient real concurrency")
        # Sampled native-process PSS peaks, not simultaneous host aggregate.
        return {"sumIndividualPeakPssKiB":sum(r["nativeMemory"]["peakPssKiB"] for r in rows),
                "sumIndividualPeakPrivateDirtyKiB":sum(r["nativeMemory"]["peakPrivateDirtyKiB"] for r in rows),
                "overlapMs":round(overlap*1000),
                "withinOneSecond":all(abs(r["observedWallMs"]-300000)<=1000 for r in rows),
                "cpuSeconds":sum(r["resources"]["userSeconds"]+r["resources"]["systemSeconds"] for r in rows)}
    a,b=summary(groups["copy"],False),summary(groups["shared"],True)
    return {"schema":1,"authoritative":False,"productionEnabled":False,
            "copy":a,"shared":b,"matches":groups,
            "sumIndividualPeakPssDeltaKiB":b["sumIndividualPeakPssKiB"]-a["sumIndividualPeakPssKiB"],
            "note":"File-backed sharing does not share decoded CPU models. PSS samples are per process; summed peaks are not aggregate host peak."}

def run_group(runtime,fixture,out,name,shared):
    barrier=threading.Barrier(2)
    def work(i):
        prefix=str(out/f"{name}-{i}")
        barrier.wait(timeout=15)
        row=fixed.timing.run(str(runtime),str(fixture),prefix,("fixed","1.0","0"),"short-match",True,
            render_threads=1,render_interval_ms=100,no_draw=True,no_upload=True,null_renderer=True,
            shared_assets=shared,sample_pss=True)
        with Path(prefix+".fixed.ndjson").open() as f:
            row.update(fixed.verify(json.loads(line) for line in f))
        return row
    with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(work,range(2)))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixture",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    pinned=layout.identity(a.runtime)
    def fixture_hash():return hashlib.sha256(a.fixture.read_bytes()).hexdigest()
    frozen_fixture=fixture_hash()
    with tempfile.TemporaryDirectory(prefix="tribun-assets-") as tmp:
        snapshot=Path(tmp)/"runtime"
        layout.freeze(a.runtime,snapshot)
        groups={}
        for name,shared in (("copy",False),("shared",True)):
            groups[name]=run_group(snapshot if shared else a.runtime,a.fixture,a.out,name,shared)
            if layout.identity(a.runtime)!=pinned or layout.identity(snapshot)!=pinned or fixture_hash()!=frozen_fixture:
                raise ValueError("Frozen inputs changed")
            for item in layout.SHARED:list(layout.inspect(snapshot/item,readonly=True))
            (a.out/(name+".json")).write_text(json.dumps(groups[name],indent=2,allow_nan=False)+"\n")
        result=evaluate(groups)
        result["sharedAssetManifestSha256"]=hashlib.sha256(json.dumps(pinned,sort_keys=True).encode()).hexdigest()
        result["fixtureSha256"]=frozen_fixture
        (a.out/"shared-assets-comparison.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
        print(json.dumps({k:v for k,v in result.items() if k!="matches"}),flush=True)
if __name__=="__main__":main()
