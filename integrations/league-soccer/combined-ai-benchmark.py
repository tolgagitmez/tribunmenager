"""Stage 102: isolated combination diagnostic; no release or production approval."""
import argparse, importlib.util, json, statistics
from pathlib import Path
from release_evidence import stamp, fingerprint, sha
HERE=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
I=load("integrated-profile")
SCENARIOS=("balanced","counter-possession","possession-counter")
MODES=("reference","combined")
ENABLED=("combinedAI","keeperAI","collectiveAI","matchPace","runLanes","triangle","defenseShape","transition")
DISABLED=("lineBreak","creativeCarry","duel","holdUp","finish","roleProfile","closeTouch","motionSmooth","determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact")
PROBES={"keeperProbe":("narrows","intercepts","touches","controls","closed"),"runLaneProbe":("attempts","primary","secondary"),"triangleProbe":("started","received","passed","completed"),"defenseProbe":("targets","suppressed","samples","exposed"),"transitionProbe":("wins","losses","counters","presses","retreats","forward","regains"),"paceProbe":("outlets",)}
def validate(r,enabled):
    if not I.mode_ok(r,True) or not I.stats_ok(r) or not I.resource_ok(r):raise ValueError("Invalid match evidence")
    if any(r.get(k) is not enabled for k in ENABLED) or any(r.get(k) is not False for k in DISABLED):raise ValueError("Policy modes differ")
    if any(type(r.get(k)) is not int or r[k]<0 for k in ("openPlayMs","deadBallMs","setPieceMs")):raise ValueError("Invalid play clock")
    for group,keys in PROBES.items():
        p=r[group]
        if not all(I.metric_pair(p.get(k)) for k in keys):raise ValueError("Invalid probe")
        if not enabled and any(v for k in keys if not(group=="defenseProbe" and k in ("samples","exposed")) for v in p[k]):raise ValueError("Reference active")
    for i in range(2):
        k,l,t,d,x,p=(r[group] for group in PROBES)
        if not 0<=k["narrows"][i]+k["intercepts"][i]-k["closed"][i]<=1 or not k["controls"][i]<=k["touches"][i]<=k["closed"][i]:raise ValueError("Keeper outcomes inconsistent")
        if l["primary"][i]+l["secondary"][i]>l["attempts"][i] or not t["started"][i]>=t["received"][i]>=t["passed"][i]>=t["completed"][i] or d["exposed"][i]>d["samples"][i] or x["counters"][i]>x["wins"][i] or x["presses"][i]+x["retreats"][i]!=x["losses"][i] or x["regains"][i]>x["presses"][i]:raise ValueError("Collective outcomes inconsistent")
def evaluate(rows):
    if set(rows)!=set(MODES):raise ValueError("Both modes required")
    a,b=rows["reference"],rows["combined"]
    validate(a,False);validate(b,True)
    if a["hardwareThreads"]!=b["hardwareThreads"]:raise ValueError("Host changed")
    m,n=a["gameplay"],b["gameplay"]
    delta={k:sum(n[k])-sum(m[k]) for k in I.METRICS}
    acc=lambda v:sum(v["completed"])/max(1,sum(v["passes"]))
    if I.cpu(a)<=0:raise ValueError("Invalid CPU baseline")
    return {"deliveryPassed":I.wall_ok(a) and I.wall_ok(b),"delta":delta,
        "passAccuracyDelta":acc(n)-acc(m),"openPlayDelta":b["openPlayMs"]-a["openPlayMs"],
        "cpuRatio":I.cpu(b)/I.cpu(a),"pssRatio":b["nativeMemory"]["peakPssKiB"]/a["nativeMemory"]["peakPssKiB"],
        "candidateProbes":{k:b[k] for k in PROBES},"referenceProbes":{k:a[k] for k in PROBES},
        "referenceShots":sum(m["shots"]),"candidateShots":sum(n["shots"]),"referenceOnTarget":sum(m["onTarget"]),"candidateOnTarget":sum(n["onTarget"])}
def aggregate(scenarios):
    if set(scenarios)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    rows=list(scenarios.values())
    total=lambda group,key:sum(sum(r["candidateProbes"][group][key]) for r in rows)
    delta=lambda k:sum(r["delta"][k] for r in rows)
    checks={"delivery":all(r["deliveryPassed"] for r in rows),
        "keeperObserved":total("keeperProbe","narrows")+total("keeperProbe","intercepts")>0 and total("keeperProbe","touches")>0,
        "lanesObserved":total("runLaneProbe","primary")+total("runLaneProbe","secondary")>0,
        "triangleCompleted":total("triangleProbe","completed")>0,
        "coverObserved":total("defenseProbe","targets")>0,
        "counterObserved":total("transitionProbe","counters")>0,
        "recoveryObserved":total("transitionProbe","presses")+total("transitionProbe","retreats")>0,
        "paceObserved":total("paceProbe","outlets")>0,
        "moreShots":delta("shots")>0,"moreBoxEntries":delta("controlledBoxCrossings")>0,
        "onTargetProtected":delta("onTarget")>=0,
        "noBoxCollapse":all(r["delta"]["controlledBoxCrossings"]>=-2 for r in rows),
        "passAccuracyProtected":all(r["passAccuracyDelta"]>=-.06 for r in rows),
        "openPlayProtected":sum(r["openPlayDelta"] for r in rows)>=0,
        "cpuBudget":statistics.median(r["cpuRatio"] for r in rows)<=1.15,
        "memoryBudget":max(r["pssRatio"] for r in rows)<=1.10}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"gameplayDelta":{k:delta(k) for k in I.METRICS}}
def main():
    p=argparse.ArgumentParser();p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=I.capacity.fingerprint(a.runtime,a.fixtures)
    report=stamp({"schema":1,"authoritative":False,"productionEnabled":False,"combinedQualified":False,
      "identity":identity,"status":"incomplete","completedRuns":[],"scenarios":{},
      "note":"Six matches, both teams use the same candidate. New thresholds are engineering diagnostics, not verified football norms. Does not replace isolated qualification or live and capacity checks."},a.runtime,"combined-ai")
    def checkpoint():
        if I.capacity.fingerprint(a.runtime,a.fixtures)!=identity or fingerprint()!=report["evidence"]["candidateSha256"]:raise ValueError("Frozen inputs changed")
        I.save(a.out/"combined-ai.json",report)
    checkpoint()
    for i,s in enumerate(SCENARIOS):
        rows={}
        for mode in (MODES if i%2==0 else MODES[::-1]):
            prefix=a.out/f"{s}-{mode}"
            row=I.run(a.runtime,a.fixtures/(s+".json"),prefix,True,combined_ai=mode=="combined")
            trace=Path(str(prefix)+".candidate.ndjson")
            rows[mode]=row;report["completedRuns"].append({"scenario":s,"mode":mode,"match":row,"traceSha256":sha(trace)});checkpoint()
        report["scenarios"][s]=evaluate(rows);checkpoint()
    report["aggregate"]=aggregate(report["scenarios"])
    report["status"]="manual-review-required" if report["aggregate"]["diagnosticPassed"] else "blocked"
    checkpoint();print(json.dumps(report["aggregate"],indent=2),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
