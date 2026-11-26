"""Stage 67: closing-defender evasion vs unchanged short-match policy."""
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
    if set(rows)!={"reference","duel"}:raise ValueError("Both modes required")
    a,b=rows["reference"],rows["duel"]
    if a["hardwareThreads"]!=b["hardwareThreads"]:raise ValueError("Host changed")
    for mode,row in rows.items():
        if not integrated.mode_ok(row,True) or not integrated.stats_ok(row) or not integrated.resource_ok(row):
            raise ValueError("Invalid profile evidence")
        if row.get("duel") is not (mode=="duel") or any(row.get(k) is not False for k in
            ("determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact","lineBreak","runLanes","triangle","creativeCarry")):
            raise ValueError("Policy is not isolated")
        p=row["duelProbe"]
        keys=("attempts","beaten","lost","cancelled")
        if not all(integrated.metric_pair(p.get(k)) for k in keys):
            raise ValueError("Invalid duel counters")
        for attempts,beaten,lost,cancelled in zip(*(p[k] for k in keys)):
            if not 0<=attempts-beaten-lost-cancelled<=1:
                raise ValueError("Inconsistent duel outcomes")
        if mode=="reference" and any(x for k in keys for x in p[k]):raise ValueError("Reference policy active")
    m,n=a["gameplay"],b["gameplay"]
    def accuracy(v):return sum(v["completed"])/max(1,sum(v["passes"]))
    delta={k:[v-u for u,v in zip(m[k],n[k])] for k in integrated.METRICS}
    return {"deliveryPassed":all(integrated.wall_ok(r) for r in rows.values()),
        "policySelected":sum(b["duelProbe"]["attempts"])>0,
        "beatenDefenders":sum(b["duelProbe"]["beaten"]),"decisionProbe":b["duelProbe"],
        "gameplayDelta":delta,"passAccuracyDelta":accuracy(n)-accuracy(m),
        "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
        "boxCrossingsDelta":sum(delta["controlledBoxCrossings"]),"shotsDelta":sum(delta["shots"]),
        "onTargetDelta":sum(delta["onTarget"])}
def aggregate(scenarios):
    if set(scenarios)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    rows=list(scenarios.values())
    checks={"delivery":all(r["deliveryPassed"] for r in rows),
        "policyExercised":all(r["policySelected"] for r in rows),
        "defenderPassedObserved":sum(r["beatenDefenders"] for r in rows)>0,
        "boxEntriesImproved":sum(r["boxCrossingsDelta"] for r in rows)>0,
        "shotsNotReduced":sum(r["shotsDelta"] for r in rows)>=0,
        "onTargetNotReduced":sum(r["onTargetDelta"] for r in rows)>=0,
        "accuracyProtected":all(r["passAccuracyDelta"]>=-0.08 for r in rows)}
    return {"checks":checks,"diagnosticPassed":all(checks.values())}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"Named defender initially ahead and closing; success proxy requires same carrier control, 2m advance and 1m beyond tracked defender. Not animation validation or causal proof. No production activation."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"duel.json",stamp(report,a.runtime,"duel"))
    checkpoint()
    for index,scenario in enumerate(SCENARIOS):
        rows={}
        for mode in (("reference","duel") if index%2==0 else ("duel","reference")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,duel=mode=="duel")
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
