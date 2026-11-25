"""Isolate final-third pass ranking using the same fixed clock and initial seeds."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
from statistics import mean
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("fixed",HERE/"fixed-duration.py")
fixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixed)
SCENARIOS=("counter-possession","balanced","possession-counter")

def metric(attack,episodes):
    tr=episodes["controlTransitions"]
    if not isinstance(tr,list) or len(tr)!=2:raise ValueError("Missing transition evidence")
    total=lambda key:sum(r[key] for r in tr)
    reacquired=total("sameTeam")+total("opponent")
    return {"shots":sum(attack["shots"]),"onTarget":sum(attack["onTarget"]),"goals":sum(attack["score"]),
        "controlledBox":sum(attack["sampled"]["controlledBoxCrossings"]),
        "finalThirdMs":sum(attack["sampled"]["controlledFinalThirdMs"]),
        "sameTeamRecovery":total("sameTeam"),"opponentRecovery":total("opponent"),
        "unresolved":total("unresolved"),"observedRecoveryRate":total("sameTeam")/reacquired if reacquired else None}

def evaluate(rows):
    keys=("shots","onTarget","goals","controlledBox","finalThirdMs","sameTeamRecovery","opponentRecovery","unresolved")
    if not rows:return {"pairCount":0,"status":"incomplete","authoritative":False}
    if len({r["scenario"] for r in rows})!=len(rows):raise ValueError("Duplicate scenario")
    deltas={k:mean(r["retention"][k]-r["control"][k] for r in rows) for k in keys}
    def recovery(side):
        same=sum(r[side]["sameTeamRecovery"] for r in rows)
        opp=sum(r[side]["opponentRecovery"] for r in rows)
        return same/(same+opp) if same+opp else None
    a,b=recovery("control"),recovery("retention")
    return {"pairCount":len(rows),"status":"descriptive-complete" if set(r["scenario"] for r in rows)==set(SCENARIOS) else "incomplete",
        "authoritative":False,"meanDelta":deltas,"resolvedRecoveryRate":{"control":a,"retention":b},
        "rows":rows,"note":"Descriptive matched initial seeds, not deterministic or statistical proof. Unresolved outcomes excluded from recovery ratio; no promotion."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime");p.add_argument("fixtures");p.add_argument("out")
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name in SCENARIOS:
        fixture=Path(a.fixtures).resolve()/(name+".json")
        prefix=str(out/name)
        row={"scenario":name,"seed":json.loads(fixture.read_text())["seed"]}
        for key,enabled in (("control",False),("retention",True)):
            timing=fixed.timing.run(a.runtime,str(fixture),prefix,(key,"1.0","0"),"short-match",True,enabled)
            trace=Path(prefix+"."+key+".ndjson")
            with trace.open() as f:fixed.verify(json.loads(line) for line in f)
            attack=json.loads(Path(str(trace)+".attack.json").read_text())
            episodes=Path(str(trace)+".episodes.json")
            subprocess.run(["node",str(HERE.parents[1]/"tools/native-attack-bottlenecks.cjs"),str(trace),str(episodes)],check=True)
            row[key]=metric(attack,json.loads(episodes.read_text()))
            row[key+"WallMs"]=timing["observedWallMs"]
            print(json.dumps({"scenario":name,"profile":key,"metrics":row[key]}),flush=True)
        rows.append(row)
        result=evaluate(rows)
        (out/"retention.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result),flush=True)
if __name__=="__main__":main()
