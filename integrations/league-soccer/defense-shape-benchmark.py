"""Stage 71: staggered defensive cover vs unchanged short-match policy."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from release_evidence import stamp
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("integrated",HERE/"integrated-profile.py")
integrated=importlib.util.module_from_spec(spec);spec.loader.exec_module(integrated)
SCENARIOS=("balanced","counter-possession","possession-counter")
def evaluate(rows):
    if set(rows)!={"reference","shape"}:raise ValueError("Both modes required")
    a,b=rows["reference"],rows["shape"]
    if a["hardwareThreads"]!=b["hardwareThreads"]:raise ValueError("Host changed")
    for mode,row in rows.items():
        if not integrated.mode_ok(row,True) or not integrated.stats_ok(row) or not integrated.resource_ok(row):
            raise ValueError("Invalid profile evidence")
        if row.get("defenseShape") is not (mode=="shape") or any(row.get(k) is not False for k in
            ("determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact","lineBreak","runLanes","triangle","creativeCarry","duel","holdUp","finish","keeperAI")):
            raise ValueError("Policy is not isolated")
        p=row["defenseProbe"]
        keys=("targets","suppressed","samples","exposed")
        if not all(integrated.metric_pair(p.get(k)) for k in keys):
            raise ValueError("Invalid defensive shape counters")
        if any(e>s for e,s in zip(p["exposed"],p["samples"])):
            raise ValueError("Exposed sample exceeds sample count")
        if mode=="reference" and any(p["targets"]+p["suppressed"]):raise ValueError("Reference policy active")
    m,n=a["gameplay"],b["gameplay"]
    def accuracy(v):return sum(v["completed"])/max(1,sum(v["passes"]))
    delta={k:[v-u for u,v in zip(m[k],n[k])] for k in integrated.METRICS}
    return {"deliveryPassed":all(integrated.wall_ok(r) for r in rows.values()),
        "policySelected":sum(b["defenseProbe"]["targets"])>0,
        "huntsSuppressed":sum(b["defenseProbe"]["suppressed"]),
        "referenceSamples":sum(a["defenseProbe"]["samples"]),"candidateSamples":sum(b["defenseProbe"]["samples"]),
        "referenceExposed":sum(a["defenseProbe"]["exposed"]),"candidateExposed":sum(b["defenseProbe"]["exposed"]),
        "decisionProbe":b["defenseProbe"],
        "referenceGoals":sum(m["score"]),"candidateGoals":sum(n["score"]),
        "gameplayDelta":delta,"passAccuracyDelta":accuracy(n)-accuracy(m),
        "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
        "boxCrossingsDelta":sum(delta["controlledBoxCrossings"]),"shotsDelta":sum(delta["shots"]),
        "onTargetDelta":sum(delta["onTarget"])}
def aggregate(scenarios):
    if set(scenarios)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    rows=list(scenarios.values())
    reference=sum(r["referenceSamples"] for r in rows)
    candidate=sum(r["candidateSamples"] for r in rows)
    before=sum(r["referenceExposed"] for r in rows)/max(1,reference)
    after=sum(r["candidateExposed"] for r in rows)/max(1,candidate)
    checks={"delivery":all(r["deliveryPassed"] for r in rows),
        "policyExercised":all(r["policySelected"] for r in rows),
        "huntSuppressionObserved":sum(r["huntsSuppressed"] for r in rows)>0,
        "shapeSamples":all(min(r["referenceSamples"],r["candidateSamples"])>=10 for r in rows),
        "exposedShareReduced":after<before,
        "goalsNotIncreased":sum(r["candidateGoals"] for r in rows)<=sum(r["referenceGoals"] for r in rows),
        "attackNotEliminated":sum(r["shotsDelta"] for r in rows)>=-6}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"referenceExposedShare":before,"candidateExposedShare":after}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"Both teams use identical experimental policy. Exposed shape is a heuristic on actual back-line depth spread, adjacent lateral gaps and goal-side count; samples are not independent or matched shot situations. No production approval."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"defense-shape.json",stamp(report,a.runtime,"defense-shape"))
    checkpoint()
    for index,scenario in enumerate(SCENARIOS):
        rows={}
        for mode in (("reference","shape") if index%2==0 else ("shape","reference")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,defense_shape=mode=="shape")
            trace=Path(str(prefix)+".candidate.ndjson")
            rows[mode]=row
            report["completedRuns"].append({"scenario":scenario,"mode":mode,"match":row,
                "traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest()})
            checkpoint()
        report["scenarios"][scenario]=evaluate(rows)
        checkpoint()
    report["aggregate"]=aggregate(report["scenarios"])
    report["status"]="manual-review-required" if report["aggregate"]["diagnosticPassed"] else "blocked"
    checkpoint()
    print(json.dumps({"status":report["status"],"aggregate":report["aggregate"],"scenarios":report["scenarios"],"productionEnabled":False}),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
