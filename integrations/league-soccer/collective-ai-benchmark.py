"""Stage 96: coordinated four-layer policy vs identical short-match reference."""
import argparse, hashlib, importlib.util, json
from pathlib import Path
from release_evidence import stamp
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("integrated",HERE/"integrated-profile.py")
I=importlib.util.module_from_spec(spec);spec.loader.exec_module(I)
SCENARIOS=("balanced","counter-possession","possession-counter")
KEYS={"runLaneProbe":("attempts","primary","secondary"),"triangleProbe":("started","received","passed","completed"),"defenseProbe":("targets","suppressed","samples","exposed"),"transitionProbe":("wins","losses","counters","presses","retreats","forward","regains")}
def evaluate(rows):
    if set(rows)!={"reference","collective"}:raise ValueError("Both modes required")
    a,b=rows["reference"],rows["collective"]
    if a["hardwareThreads"]!=b["hardwareThreads"]:raise ValueError("Host changed")
    for mode,row in rows.items():
        enabled=mode=="collective"
        if not I.mode_ok(row,True) or not I.stats_ok(row) or not I.resource_ok(row):raise ValueError("Invalid profile evidence")
        if any(row.get(k) is not enabled for k in ("collectiveAI","runLanes","triangle","defenseShape","transition")):raise ValueError("Unexpected collective modes")
        if any(row.get(k) is not False for k in ("lineBreak","creativeCarry","duel","holdUp","finish","keeperAI","roleProfile","closeTouch","motionSmooth","matchPace","determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact")):raise ValueError("Non-collective policy active")
        for group,keys in KEYS.items():
            p=row[group]
            if not all(I.metric_pair(p.get(k)) for k in keys):raise ValueError("Invalid probe")
            if not enabled and any(n for k in keys if not (group=="defenseProbe" and k in ("samples","exposed")) for n in p[k]):raise ValueError("Reference decisions active")
        for i in range(2):
            l,t,d,x=(row[k] for k in KEYS)
            if l["primary"][i]+l["secondary"][i]>l["attempts"][i] or not t["started"][i]>=t["received"][i]>=t["passed"][i]>=t["completed"][i] or d["exposed"][i]>d["samples"][i] or x["counters"][i]>x["wins"][i] or x["presses"][i]+x["retreats"][i]!=x["losses"][i] or x["regains"][i]>x["presses"][i]:raise ValueError("Inconsistent probe")
    m,n=a["gameplay"],b["gameplay"]
    accuracy=lambda v:sum(v["completed"])/max(1,sum(v["passes"]))
    delta={k:[y-x for x,y in zip(m[k],n[k])] for k in I.METRICS}
    return {"deliveryPassed":I.wall_ok(a) and I.wall_ok(b),"gameplayDelta":delta,
      "passAccuracyDelta":accuracy(n)-accuracy(m),"cpuSecondsDelta":I.cpu(b)-I.cpu(a),
      "referenceProbes":{k:a[k] for k in KEYS},"candidateProbes":{k:b[k] for k in KEYS},
      "shotsDelta":sum(delta["shots"]),"onTargetDelta":sum(delta["onTarget"]),"boxEntriesDelta":sum(delta["controlledBoxCrossings"])}
def aggregate(scenarios):
    if set(scenarios)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    rows=list(scenarios.values())
    total=lambda group,key:sum(sum(r["candidateProbes"][group][key]) for r in rows)
    checks={"delivery":all(r["deliveryPassed"] for r in rows),
       "laneObserved":total("runLaneProbe","primary")+total("runLaneProbe","secondary")>0,
       "triangleCompleted":total("triangleProbe","completed")>0,
       "coverObserved":total("defenseProbe","targets")>0,
       "counterObserved":total("transitionProbe","counters")>0,
       "recoveryObserved":total("transitionProbe","presses")+total("transitionProbe","retreats")>0,
       "shotsNotReduced":sum(r["shotsDelta"] for r in rows)>=0,
       "boxEntriesNotReduced":sum(r["boxEntriesDelta"] for r in rows)>=0,
       "accuracyProtected":all(r["passAccuracyDelta"]>=-.08 for r in rows)}
    return {"checks":checks,"diagnosticPassed":all(checks.values())}
def main():
    p=argparse.ArgumentParser();p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=I.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,"status":"incomplete","completedRuns":[],"scenarios":{},"note":"Both teams use same experimental collective profile. Counts are observations; no guaranteed improvement or causal attribution. Six fixed-duration matches."}
    def checkpoint():
        if I.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        I.save(a.out/"collective-ai.json",stamp(report,a.runtime,"collective-ai"))
    checkpoint()
    for i,s in enumerate(SCENARIOS):
        rows={}
        for mode in (("reference","collective") if i%2==0 else ("collective","reference")):
            prefix=a.out/f"{s}-{mode}"
            row=I.run(a.runtime,a.fixtures/(s+".json"),prefix,True,collective_ai=mode=="collective")
            trace=Path(str(prefix)+".candidate.ndjson");rows[mode]=row
            report["completedRuns"].append({"scenario":s,"mode":mode,"match":row,"traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest()});checkpoint()
        report["scenarios"][s]=evaluate(rows);checkpoint()
    report["aggregate"]=aggregate(report["scenarios"])
    report["status"]="manual-review-required" if report["aggregate"]["diagnosticPassed"] else "blocked"
    checkpoint()
    print(json.dumps({"status":report["status"],"aggregate":report["aggregate"],"scenarios":report["scenarios"],"productionEnabled":False}),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
