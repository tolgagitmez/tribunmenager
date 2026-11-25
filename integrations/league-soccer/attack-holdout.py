"""Single-runtime held-out attack retest. Never selects or enables production.

One shared control per held-out fixture, each eligible profile isolated. Existing
historical reports only nominate candidates; no pooling of their match metrics.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m
review=load("attack_review",ROOT/"tools/native-attack-review.py")
fixed=load("fixed",HERE/"fixed-duration.py")
box=load("box_metrics",HERE/"box-runs-benchmark.py")
SCENARIOS={"holdout-high-press":91001,"holdout-low-block":91002,"holdout-direct":91003}
FLAGS={"control":(False,False,False),"retention":(True,False,False),
       "boxRuns":(False,True,False),"timedAttack":(False,False,True)}

def digest(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def identity(runtime):
    return {k:digest(Path(runtime)/v) for k,v in (("binarySha256","gameplayfootball"),("manifestSha256","tribun-runtime.json"))}

def contacts(frames):
    previous=[[0,0,0],[0,0,0]]
    keys=("passes","receipts","shots")
    for frame in frames:
        counters=frame.get("timedAttacks")
        if not isinstance(counters,list) or len(counters)!=2:
            raise ValueError("Missing timed attack counters")
        for team,c in enumerate(counters):
            v=[c[k] for k in keys]
            if any(type(x) is not int or x<y for x,y in zip(v,previous[team])) or not v[0]>=v[1]>=v[2]:
                raise ValueError("Invalid actual contacts")
            previous[team]=v
    return {k:sum(r[i] for r in previous) for i,k in enumerate(keys)}

def assess(rows,candidates,build):
    if not candidates or any(p not in review.PROFILES for p in candidates) or len(set(candidates))!=len(candidates):
        raise ValueError("Invalid candidate selection")
    if not isinstance(build,dict) or set(build)!={"binarySha256","manifestSha256"} or any(not isinstance(v,str) or len(v)!=64 or any(c not in "0123456789abcdef" for c in v) for v in build.values()):
        raise ValueError("Invalid runtime identity")
    seen=set()
    for r in rows:
        if r.get("scenario") not in SCENARIOS or r["scenario"] in seen or r.get("seed")!=SCENARIOS[r["scenario"]]:
            raise ValueError("Unexpected held-out fixture")
        seen.add(r["scenario"])
        for p in ("control",*candidates):
            if r.get(p+"Runtime")!=build:raise ValueError("Mixed runtime identity")
            if r.get(p+"FixtureSha256")!=r.get("fixtureSha256"):raise ValueError("Mixed frozen fixture")
            if r.get(p+"Fixed") is not True:raise ValueError("Missing exact native clock verification")
    results={}
    for p in candidates:
        if not rows:
            results[p]={"status":"missing"}
            continue
        report={"authoritative":False,"pairCount":len(rows),"rows":rows}
        results[p]=review.assess(report,p,SCENARIOS)
    selected=[p for p,r in results.items() if r["status"]=="retest-candidate"]
    status="incomplete" if seen!=set(SCENARIOS) else "interaction-test-required" if len(selected)>1 else "single-policy-review-required" if selected else "blocked"
    return {"schema":1,"authoritative":False,"productionEnabled":False,"combinedEnabled":False,
            "runtime":build,"status":status,"heldOutPairs":len(rows),"profiles":results,
            "interactionCandidates":selected,"rows":rows,
            "note":"Shared controls on held-out seeds, sequential actual matches. No automatic combination or promotion. Interaction tests require additional held-out fixtures."}

def run_match(runtime,fixture,prefix,profile,build,fixture_sha):
    if identity(runtime)!=build or digest(fixture)!=fixture_sha:raise ValueError("Inputs changed before match")
    t=fixed.timing.run(runtime,str(fixture),prefix,(profile,"1.0","0"),"short-match",True,*FLAGS[profile])
    trace=Path(prefix+"."+profile+".ndjson")
    with trace.open() as f:frames=[json.loads(line) for line in f]
    clock=fixed.verify(frames)
    c=contacts(frames)
    if profile!="timedAttack" and any(c.values()):raise ValueError("Timed attack flag leaked")
    del frames
    attack=json.loads(Path(str(trace)+".attack.json").read_text())
    ep=Path(str(trace)+".episodes.json")
    subprocess.run(["node",str(ROOT/"tools/native-attack-bottlenecks.cjs"),str(trace),str(ep)],check=True)
    if identity(runtime)!=build or digest(fixture)!=fixture_sha:raise ValueError("Inputs changed during match")
    return {profile:box.metric(attack,json.loads(ep.read_text())),
            profile+"Contacts":c,profile+"WallMs":t["observedWallMs"],
            profile+"Runtime":build,profile+"FixtureSha256":fixture_sha,
            profile+"Fixed":clock["exactNativeDuration"],profile+"TraceSha256":digest(trace)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime");p.add_argument("fixtures");p.add_argument("out")
    p.add_argument("--retention",type=Path);p.add_argument("--box-runs",type=Path);p.add_argument("--timed-attack",type=Path)
    a=p.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    inputs={"retention":a.retention,"boxRuns":a.box_runs,"timedAttack":a.timed_attack}
    original=review.review({k:json.loads(v.read_text()) for k,v in inputs.items() if v is not None})
    (out/"historical-review.json").write_text(json.dumps(original,indent=2,allow_nan=False)+"\n")
    candidates=original["retestCandidates"]
    if not candidates:
        print("No candidate passed historical screening; no matches started")
        return
    build=identity(a.runtime)
    rows=[]
    for name,seed in SCENARIOS.items():
        fixture=Path(a.fixtures).resolve()/(name+".json")
        if json.loads(fixture.read_text())["seed"]!=seed:raise ValueError("Unexpected seed")
        fixture_sha=digest(fixture)
        row={"scenario":name,"seed":seed,"fixtureSha256":fixture_sha}
        prefix=str(out/name)
        for profile in ("control",*candidates):
            row.update(run_match(a.runtime,fixture,prefix,profile,build,fixture_sha))
            print(json.dumps({"scenario":name,"profile":profile,"metrics":row[profile]}),flush=True)
        rows.append(row)
        result=assess(rows,candidates,build)
        (out/"holdout-review.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result),flush=True)
if __name__=="__main__":main()
