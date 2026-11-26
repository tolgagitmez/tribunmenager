"""Stage 72: confirmed-turnover counter and recovery vs unchanged short-match policy."""
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
    if set(rows)!={"reference","transition"}:raise ValueError("Both modes required")
    a,b=rows["reference"],rows["transition"]
    if a["hardwareThreads"]!=b["hardwareThreads"]:raise ValueError("Host changed")
    for mode,row in rows.items():
        if not integrated.mode_ok(row,True) or not integrated.stats_ok(row) or not integrated.resource_ok(row):
            raise ValueError("Invalid profile evidence")
        if row.get("transition") is not (mode=="transition") or any(row.get(k) is not False for k in
            ("determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact","lineBreak","runLanes","triangle","creativeCarry","duel","holdUp","finish","keeperAI","defenseShape")):
            raise ValueError("Policy is not isolated")
        p=row["transitionProbe"]
        keys=("wins","losses","counters","presses","retreats","forward","regains")
        if not all(integrated.metric_pair(p.get(k)) for k in keys):
            raise ValueError("Invalid transition counters")
        for wins,losses,counters,presses,retreats,forward,regains in zip(*(p[k] for k in keys)):
            if counters>wins or presses+retreats!=losses or regains>presses:
                raise ValueError("Inconsistent transition counters")
        if mode=="reference" and any(x for k in keys for x in p[k]):raise ValueError("Reference policy active")
    m,n=a["gameplay"],b["gameplay"]
    def accuracy(v):return sum(v["completed"])/max(1,sum(v["passes"]))
    delta={k:[v-u for u,v in zip(m[k],n[k])] for k in integrated.METRICS}
    return {"deliveryPassed":all(integrated.wall_ok(r) for r in rows.values()),
        "policySelected":sum(b["transitionProbe"]["wins"]+b["transitionProbe"]["losses"])>0,
        "counters":sum(b["transitionProbe"]["counters"]),"presses":sum(b["transitionProbe"]["presses"]),
        "retreats":sum(b["transitionProbe"]["retreats"]),"forward":sum(b["transitionProbe"]["forward"]),
        "regains":sum(b["transitionProbe"]["regains"]),"decisionProbe":b["transitionProbe"],
        "gameplayDelta":delta,"passAccuracyDelta":accuracy(n)-accuracy(m),
        "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
        "boxCrossingsDelta":sum(delta["controlledBoxCrossings"]),"shotsDelta":sum(delta["shots"]),
        "onTargetDelta":sum(delta["onTarget"])}
def aggregate(scenarios):
    if set(scenarios)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    rows=list(scenarios.values())
    checks={"delivery":all(r["deliveryPassed"] for r in rows),
        "policyExercised":all(r["policySelected"] for r in rows),
        "counterObserved":sum(r["counters"] for r in rows)>0,
        "counterPassContactObserved":sum(r["forward"] for r in rows)>0,
        "recoveryModesObserved":sum(r["presses"] for r in rows)>0 and sum(r["retreats"] for r in rows)>0,
        "shotsNotReduced":sum(r["shotsDelta"] for r in rows)>=0,
        "boxEntriesNotReduced":sum(r["boxCrossingsDelta"] for r in rows)>=0,
        "accuracyProtected":all(r["passAccuracyDelta"]>=-.08 for r in rows)}
    return {"checks":checks,"diagnosticPassed":all(checks.values())}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"Confirmed control changes exclude brief loose balls. Forward counter passes are actual contacts toward advanced teammates, not verified receptions. Recovery events are choices; regains are temporal observations, not causal proof. Both teams use the same policy; no production activation."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"transition.json",stamp(report,a.runtime,"transition"))
    checkpoint()
    for index,scenario in enumerate(SCENARIOS):
        rows={}
        for mode in (("reference","transition") if index%2==0 else ("transition","reference")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,transition=mode=="transition")
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
