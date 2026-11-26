"""Stage 97 paired match pace diagnostic. No production promotion."""
import argparse, hashlib, importlib.util, json
from pathlib import Path
from release_evidence import stamp
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("integrated",HERE/"integrated-profile.py")
I=importlib.util.module_from_spec(spec);spec.loader.exec_module(I)
SCENARIOS=("balanced","counter-possession","possession-counter")
def evaluate(rows):
    if set(rows)!={"reference","pace"}:raise ValueError("Both modes required")
    a,b=rows["reference"],rows["pace"]
    if a["hardwareThreads"]!=b["hardwareThreads"]:raise ValueError("Host changed")
    for mode,r in rows.items():
        if not I.mode_ok(r,True) or not I.stats_ok(r) or not I.resource_ok(r):raise ValueError("Invalid match")
        if r.get("matchPace") is not (mode=="pace"):raise ValueError("Invalid policy")
        if any(r.get(k) is not False for k in ("collectiveAI","lineBreak","runLanes","triangle","creativeCarry","duel","holdUp","finish","keeperAI","defenseShape","transition","roleProfile","closeTouch","motionSmooth","determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact")):raise ValueError("Other policy active")
        if not I.metric_pair(r["paceProbe"]["outlets"]):raise ValueError("Missing outlet evidence")
        if mode=="reference" and any(r["paceProbe"]["outlets"]):raise ValueError("Reference active")
        if any(type(r[k]) is not int or r[k]<0 for k in ("openPlayMs","setPieceMs","deadBallMs")):raise ValueError("Invalid clock")
    m,n=a["gameplay"],b["gameplay"]
    acc=lambda v:sum(v["completed"])/max(1,sum(v["passes"]))
    delta={k:[y-x for x,y in zip(m[k],n[k])] for k in I.METRICS}
    return {"deliveryPassed":I.wall_ok(a) and I.wall_ok(b),"outletEvaluations":sum(b["paceProbe"]["outlets"]),"gameplayDelta":delta,
     "shotsDelta":sum(delta["shots"]),"onTargetDelta":sum(delta["onTarget"]),"boxEntriesDelta":sum(delta["controlledBoxCrossings"]),
     "accuracyDelta":acc(n)-acc(m),"openPlayMsDelta":b["openPlayMs"]-a["openPlayMs"],"deadBallMsDelta":b["deadBallMs"]-a["deadBallMs"],
     "setPieceMsDelta":b["setPieceMs"]-a["setPieceMs"],"cpuSecondsDelta":I.cpu(b)-I.cpu(a)}
def aggregate(scenarios):
    if set(scenarios)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    rows=list(scenarios.values());total=lambda k:sum(r[k] for r in rows)
    checks={"delivery":all(r["deliveryPassed"] for r in rows),"policyExercised":total("outletEvaluations")>0,
      "moreBoxEntries":total("boxEntriesDelta")>0,"moreShots":total("shotsDelta")>0,
      "onTargetProtected":total("onTargetDelta")>=0,"accuracyProtected":all(r["accuracyDelta"]>=-.06 for r in rows),
      "openPlayProtected":total("openPlayMsDelta")>=0}
    return {"checks":checks,"diagnosticPassed":all(checks.values())}
def main():
    p=argparse.ArgumentParser();p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=I.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,"status":"incomplete","completedRuns":[],"scenarios":{},"note":"Both teams use same isolated policy. Outlet evaluations are NOT actual selected/completed passes. Shorter ordinary ball-out preparation and chance preference are tested together; effect cannot be attributed to one change."}
    def checkpoint():
        if I.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        I.save(a.out/"match-pace.json",stamp(report,a.runtime,"match-pace"))
    checkpoint()
    for i,s in enumerate(SCENARIOS):
        rows={}
        for mode in (("reference","pace") if i%2==0 else ("pace","reference")):
            prefix=a.out/f"{s}-{mode}"
            row=I.run(a.runtime,a.fixtures/(s+".json"),prefix,True,match_pace=mode=="pace")
            trace=Path(str(prefix)+".candidate.ndjson");rows[mode]=row
            report["completedRuns"].append({"scenario":s,"mode":mode,"match":row,"traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest()});checkpoint()
        report["scenarios"][s]=evaluate(rows);checkpoint()
    report["aggregate"]=aggregate(report["scenarios"]);report["status"]="manual-review-required" if report["aggregate"]["diagnosticPassed"] else "blocked"
    checkpoint();print(json.dumps({"status":report["status"],"aggregate":report["aggregate"],"scenarios":report["scenarios"],"productionEnabled":False}),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
