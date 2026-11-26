"""Compare current native graphics cadence with a 100 ms scheduled interval.

This is not headless. OpenGL context, mesh assets, collision geometry, animation
updates and game scheduler remain intact. One actual pair is descriptive only.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("fixed",HERE/"fixed-duration.py")
fixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixed)
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def measure(runtime,fixture,out,interval):
    name="control" if interval==0 else "capped"
    r=fixed.timing.run(runtime,fixture,out,(name,"1.0","0"),"short-match",True,
                       render_threads=2,render_interval_ms=interval)
    with Path(out+"."+name+".ndjson").open() as f:
        return {**r,**fixed.verify(json.loads(line) for line in f)}
def evaluate(rows):
    if set(rows)!={"control","capped"}:raise ValueError("Require both observed matches")
    a,b=rows["control"],rows["capped"]
    for r,interval in ((a,0),(b,100)):
        if r.get("configuredRenderIntervalMs")!=interval or r.get("softwareRenderThreads")!=2 or r.get("exactNativeDuration") is not True or r.get("nativeElapsedMs")!=300000:
            raise ValueError("Mixed render settings or invalid clock")
        if not isinstance(r.get("resources"),dict):raise ValueError("Missing CPU evidence")
        if r.get("retention") or r.get("boxRuns") or r.get("timedAttack"):
            raise ValueError("Attack policy contamination")
    cpu=lambda r:r["resources"]["userSeconds"]+r["resources"]["systemSeconds"]
    return {"schema":1,"authoritative":False,"productionEnabled":False,
            "status":"descriptive-pair-complete","matches":rows,
            "cpuSeconds":{"control":cpu(a),"capped":cpu(b)},
            "cpuSecondsDelta":cpu(b)-cpu(a),
            "wallDeltaMs":b["observedWallMs"]-a["observedWallMs"],
            "maxGapDeltaMs":b["maxObservedGapMs"]-a["maxObservedGapMs"],
            "rssDeltaKiB":b["resources"]["maxRssKiB"]-a["resources"]["maxRssKiB"],
            "note":"Same executable/fixture and thread cap. Scheduled graphics interval is not measured FPS. One pair cannot prove equivalent play or production throughput."}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime");p.add_argument("fixture");p.add_argument("out")
    a=p.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    paths=[Path(a.runtime)/"gameplayfootball",Path(a.runtime)/"tribun-runtime.json",Path(a.fixture)]
    identity=lambda:[sha(x) for x in paths]
    pinned=identity()
    rows={}
    for key,interval in (("control",0),("capped",100)):
        if identity()!=pinned:raise ValueError("Inputs changed before match")
        rows[key]=measure(a.runtime,a.fixture,str(out/"cadence"),interval)
        if identity()!=pinned:raise ValueError("Inputs changed during match")
        (out/(key+".json")).write_text(json.dumps(rows[key],indent=2,allow_nan=False)+"\n")
        print(json.dumps(rows[key]),flush=True)
    result={**evaluate(rows),"identity":dict(zip(("binarySha256","manifestSha256","fixtureSha256"),pinned))}
    (out/"render-comparison.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result),flush=True)
if __name__=="__main__":main()
