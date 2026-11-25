"""Verify exact native tick budget separately from observed wall-clock delivery."""
import argparse
import importlib.util
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("timing",HERE/"timing-benchmark.py")
timing=importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)

def verify(frames):
    first=half=last=None
    prev=-1
    for f in frames:
        c=f.get("fixedClock")
        if not isinstance(c,dict):raise ValueError("Missing fixed-clock telemetry")
        if not c["started"]:
            if first is not None or f["done"]:raise ValueError("Clock reset")
            continue
        if first is None:
            first=c["startMs"]
            if f["elapsedMs"]!=first or c["elapsedMs"]!=0 or not f["inPlay"]:raise ValueError("Missing exact kickoff")
        elapsed=c["elapsedMs"]
        if c["startMs"]!=first or elapsed!=f["elapsedMs"]-first or not prev<=elapsed<=300000:
            raise ValueError("Fixed clock inconsistent")
        if f["matchMs"]!=elapsed*18:raise ValueError("Incorrect nominal clock")
        if c["half"] and half is None:half=elapsed
        if c["half"]!=(elapsed>=150000):raise ValueError("Half transition mismatch")
        if c["finished"]!=f["done"] or f["done"]!=(elapsed==300000):raise ValueError("Final deadline mismatch")
        if last is not None:raise ValueError("Frames after deadline")
        if f["done"]:last=elapsed
        prev=elapsed
    if first is None or half!=150000 or last!=300000:raise ValueError("Incomplete fixed-duration match")
    return {"nativeElapsedMs":last,"halfMs":half,"exactNativeDuration":True}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime");p.add_argument("fixture");p.add_argument("out")
    a=p.parse_args()
    r=timing.run(a.runtime,a.fixture,a.out,("fixed","1.0","0"),"short-match",True)
    trace=Path(a.out+".fixed.ndjson")
    with trace.open() as f:clock=verify(json.loads(line) for line in f)
    report={**r,**clock,"exactObservedWallDuration":r["observedWallMs"]==300000,
        "authoritative":False,"note":"Exact simulation ticks do not prove exact delivery wall time; no promotion."}
    from release_evidence import stamp
    report=stamp(report,a.runtime,"fixed-duration")
    Path(a.out+".fixed-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report),flush=True)

if __name__=="__main__":main()
