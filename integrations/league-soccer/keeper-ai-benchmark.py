"""Stage 70: keeper angle narrowing and interception vs unchanged short-match policy."""
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
    if set(rows)!={"reference","keeper"}:raise ValueError("Both modes required")
    a,b=rows["reference"],rows["keeper"]
    if a["hardwareThreads"]!=b["hardwareThreads"]:raise ValueError("Host changed")
    for mode,row in rows.items():
        if not integrated.mode_ok(row,True) or not integrated.stats_ok(row) or not integrated.resource_ok(row):
            raise ValueError("Invalid profile evidence")
        if row.get("keeperAI") is not (mode=="keeper") or any(row.get(k) is not False for k in
            ("determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact","lineBreak","runLanes","triangle","creativeCarry","duel","holdUp","finish","defenseShape","transition","roleProfile","closeTouch","motionSmooth","collectiveAI","matchPace")):
            raise ValueError("Policy is not isolated")
        p=row["keeperProbe"]
        keys=("narrows","intercepts","touches","controls","closed")
        if not all(integrated.metric_pair(p.get(k)) for k in keys):
            raise ValueError("Invalid keeper counters")
        for narrow,intercept,touches,controls,closed in zip(*(p[k] for k in keys)):
            if not 0<=narrow+intercept-closed<=1 or not controls<=touches<=closed:
                raise ValueError("Inconsistent keeper outcomes")
        if mode=="reference" and any(x for k in keys for x in p[k]):raise ValueError("Reference policy active")
    m,n=a["gameplay"],b["gameplay"]
    def accuracy(v):return sum(v["completed"])/max(1,sum(v["passes"]))
    delta={k:[v-u for u,v in zip(m[k],n[k])] for k in integrated.METRICS}
    return {"deliveryPassed":all(integrated.wall_ok(r) for r in rows.values()),
        "policySelected":sum(b["keeperProbe"]["narrows"]+b["keeperProbe"]["intercepts"])>0,
        "narrows":sum(b["keeperProbe"]["narrows"]),"intercepts":sum(b["keeperProbe"]["intercepts"]),
        "touches":sum(b["keeperProbe"]["touches"]),"controls":sum(b["keeperProbe"]["controls"]),
        "decisionProbe":b["keeperProbe"],
        "referenceGoals":sum(m["score"]),"candidateGoals":sum(n["score"]),
        "gameplayDelta":delta,"passAccuracyDelta":accuracy(n)-accuracy(m),
        "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
        "boxCrossingsDelta":sum(delta["controlledBoxCrossings"]),"shotsDelta":sum(delta["shots"]),
        "onTargetDelta":sum(delta["onTarget"])}
def aggregate(scenarios):
    if set(scenarios)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    rows=list(scenarios.values())
    checks={"delivery":all(r["deliveryPassed"] for r in rows),
        "policyExercised":any(r["policySelected"] for r in rows),
        "narrowObserved":sum(r["narrows"] for r in rows)>0,
        "interceptObserved":sum(r["intercepts"] for r in rows)>0,
        "keeperTouchObserved":sum(r["touches"] for r in rows)>0,
        "goalsNotIncreased":sum(r["candidateGoals"] for r in rows)<=sum(r["referenceGoals"] for r in rows)}
    return {"checks":checks,"diagnosticPassed":all(checks.values())}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"Both teams use the same experimental goalkeeper policy. Contacts within 1300ms are observations, not verified saves or causal attribution. Goals conceded proxy is descriptive, not a controlled per-shot save test. No changes to hand contacts, save animation or catch/parry selection."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"keeper-ai.json",stamp(report,a.runtime,"keeper-ai"))
    checkpoint()
    for index,scenario in enumerate(SCENARIOS):
        rows={}
        for mode in (("reference","keeper") if index%2==0 else ("keeper","reference")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,keeper_ai=mode=="keeper")
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
