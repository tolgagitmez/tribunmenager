"""Stage 73: attribute-derived off-ball profiles vs unchanged short-match policy."""
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
    if set(rows)!={"reference","roles"}:raise ValueError("Both modes required")
    a,b=rows["reference"],rows["roles"]
    if a["hardwareThreads"]!=b["hardwareThreads"]:raise ValueError("Host changed")
    for mode,row in rows.items():
        if not integrated.mode_ok(row,True) or not integrated.stats_ok(row) or not integrated.resource_ok(row):
            raise ValueError("Invalid profile evidence")
        if row.get("roleProfile") is not (mode=="roles") or any(row.get(k) is not False for k in
            ("determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact","lineBreak","runLanes","triangle","creativeCarry","duel","holdUp","finish","keeperAI","defenseShape","transition")):
            raise ValueError("Policy is not isolated")
        p=row["roleProbe"]
        if len(p)!=24 or {(v["team"],v["profile"]) for v in p}!={(t,k) for t in range(2) for k in range(1,13)}:
            raise ValueError("Invalid role profile rows")
        for v in p:
            if any(type(v[k]) is not int for k in ("targets","samples","forwardMm","wideMm")) or min(v["targets"],v["samples"])<0:
                raise ValueError("Invalid role profile counters")
            if not v["samples"] and (v["forwardMm"] or v["wideMm"]):raise ValueError("Invalid sample totals")
            if mode=="reference" and v["targets"]:raise ValueError("Reference policy active")
    m,n=a["gameplay"],b["gameplay"]
    def accuracy(v):return sum(v["completed"])/max(1,sum(v["passes"]))
    delta={k:[v-u for u,v in zip(m[k],n[k])] for k in integrated.METRICS}
    return {"deliveryPassed":all(integrated.wall_ok(r) for r in rows.values()),
        "policySelected":any(v["targets"] for v in b["roleProbe"]),
        "profilesUsed":sorted({v["profile"] for v in b["roleProbe"] if v["targets"]}),
        "referenceProfiles":a["roleProbe"],"candidateProfiles":b["roleProbe"],
        "gameplayDelta":delta,"passAccuracyDelta":accuracy(n)-accuracy(m),
        "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
        "boxCrossingsDelta":sum(delta["controlledBoxCrossings"]),"shotsDelta":sum(delta["shots"]),
        "onTargetDelta":sum(delta["onTarget"])}
def aggregate(scenarios):
    if set(scenarios)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    rows=list(scenarios.values())
    def means(key):
        result={}
        for profile in range(1,13):
            samples=[v for row in rows for v in row[key] if v["profile"]==profile]
            n=sum(v["samples"] for v in samples)
            if n>=20:result[profile]={"n":n,"advance":sum(v["forwardMm"] for v in samples)/n/1000,
                "width":sum(v["wideMm"] for v in samples)/n/1000}
        return result
    before,after=means("referenceProfiles"),means("candidateProfiles")
    # Report actual movement changes; require at least one directionally consistent pair.
    expected=((1,2,"advance"),(4,3,"width"),(5,6,"advance"),(8,7,"advance"),(9,10,"advance"),(11,12,"advance"))
    pairs=[]
    for a,b,k in expected:
        if all(profile in data for data in (before,after) for profile in (a,b)):
            delta=(after[a][k]-after[b][k])-(before[a][k]-before[b][k])
            pairs.append({"profiles":[a,b],"dimension":k,"differenceInDifferenceMetres":delta})
    checks={"delivery":all(r["deliveryPassed"] for r in rows),
        "policyExercised":all(r["policySelected"] for r in rows),
        "distinctProfiles":len({p for r in rows for p in r["profilesUsed"]})>=2,
        "roleContrastObserved":any(p["differenceInDifferenceMetres"]>.1 for p in pairs),
        "shotsNotReduced":sum(r["shotsDelta"] for r in rows)>=0,
        "accuracyProtected":all(r["passAccuracyDelta"]>=-.08 for r in rows)}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"roleContrasts":pairs,"referenceMeans":before,"candidateMeans":after}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"Automatic profile classification uses current native stats and static position family. Actual off-ball positions are sampled relative to adapted formation; differences are exploratory and not controlled equal-OVR player experiments. No explicit UI role setting or new animations."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"role-profile.json",stamp(report,a.runtime,"role-profile"))
    checkpoint()
    for index,scenario in enumerate(SCENARIOS):
        rows={}
        for mode in (("reference","roles") if index%2==0 else ("roles","reference")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,role_profile=mode=="roles")
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
