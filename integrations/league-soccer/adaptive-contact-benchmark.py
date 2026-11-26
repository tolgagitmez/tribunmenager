"""Stage 56: compare uniform 10 ms and adaptive per-player poses; no automatic release."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from release_evidence import stamp
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("repeat",HERE/"profile-repeatability.py")
repeat=importlib.util.module_from_spec(spec);spec.loader.exec_module(repeat)
integrated=repeat.integrated
KEYS=("playerUpdates","highUpdates","mediumUpdates","lowUpdates","queries","missingQueries","staleQueries","maxQueryAgeTicks")
def evaluate(rows):
    if set(rows)!={"uniform","adaptive"}:raise ValueError("Both modes required")
    a,b=rows["uniform"],rows["adaptive"]
    if a.get("hardwareThreads")!=b.get("hardwareThreads"):raise ValueError("Host changed")
    for mode,row in rows.items():
        p=row.get("adaptiveContactProbe",{})
        if (not integrated.mode_ok(row,True) or not integrated.resource_ok(row) or not integrated.stats_ok(row)
            or any(row.get(k) is not True for k in ("determinismProbe","orderedPose","collisionPose"))
            or row.get("contactIntervalMs")!=10 or row.get("adaptiveContact") is not (mode=="adaptive")
            or any(type(p.get(k)) is not int or p[k]<0 for k in KEYS)
            or p["playerUpdates"]<=0 or p["missingQueries"]+p["staleQueries"]>p["queries"]):
            raise ValueError("Invalid adaptive contact evidence")
        total=sum(p[k] for k in ("highUpdates","mediumUpdates","lowUpdates"))
        if total!=(p["playerUpdates"] if mode=="adaptive" else 0):
            raise ValueError("Inconsistent update counters")
    x,y=a["adaptiveContactProbe"],b["adaptiveContactProbe"]
    checks={"delivery":all(integrated.wall_ok(r) for r in rows.values()),
            "queriesObserved":x["queries"]>0 and y["queries"]>0,
            "uniformFresh":x["missingQueries"]==0 and x["staleQueries"]==0 and x["maxQueryAgeTicks"]<=1,
            "adaptiveFresh":y["missingQueries"]==0 and y["staleQueries"]==0 and y["maxQueryAgeTicks"]<=1,
            "allTiersUsed":all(y[k]>0 for k in ("highUpdates","mediumUpdates","lowUpdates")),
            "fewerUpdates":y["playerUpdates"]<x["playerUpdates"]}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),
            "playerUpdateReduction":1-y["playerUpdates"]/x["playerUpdates"],
            "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
            "peakPssDeltaKiB":b["nativeMemory"]["peakPssKiB"]-a["nativeMemory"]["peakPssKiB"],
            "gameplayDelta":{k:[v-u for u,v in zip(a["gameplay"][k],b["gameplay"][k])] for k in integrated.METRICS},
            "observedGameplayEqual":a["gameplay"]==b["gameplay"]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
            "status":"incomplete","completedRuns":[],"scenarios":{},
            "note":"Per-player pose cadence changes only. Actual geometry-query age is measured, not distinct successful contacts. One pair per scenario is not proof of parity or realism."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"adaptive-contact.json",stamp(report,a.runtime,"adaptive-contact"))
    checkpoint()
    for index,scenario in enumerate(integrated.SCENARIOS):
        rows={}
        for mode in (("uniform","adaptive") if index==0 else ("adaptive","uniform")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,determinism_probe=True,
                ordered_pose=True,collision_pose=True,contact_interval_ms=10,adaptive_contact=mode=="adaptive")
            trace=Path(str(prefix)+".candidate.ndjson")
            with trace.open() as f:repeat.digest_frames(json.loads(line) for line in f)
            rows[mode]=row
            report["completedRuns"].append({"scenario":scenario,"mode":mode,"match":row,
                "traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest()})
            checkpoint()
        report["scenarios"][scenario]=evaluate(rows)
        checkpoint()
    report["status"]="manual-review-required" if all(v["diagnosticPassed"] for v in report["scenarios"].values()) else "blocked"
    checkpoint()
    print(json.dumps({"status":report["status"],"scenarios":report["scenarios"],"productionEnabled":False}),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
