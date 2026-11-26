"""Stage 58: compare retained spin with coupled friction/angular impulse."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from release_evidence import stamp
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("repeat",HERE/"profile-repeatability.py")
repeat=importlib.util.module_from_spec(spec);spec.loader.exec_module(repeat)
integrated=repeat.integrated
def evaluate(rows):
    if set(rows)!={"retained","angular"}:raise ValueError("Both modes required")
    a,b=rows["retained"],rows["angular"]
    if a.get("hardwareThreads")!=b.get("hardwareThreads"):raise ValueError("Host changed")
    for mode,row in rows.items():
        p=row.get("angularProbe",{})
        if (not integrated.mode_ok(row,True) or not integrated.stats_ok(row) or not integrated.resource_ok(row)
            or any(row.get(k) is not True for k in ("determinismProbe","orderedPose","collisionPose","surfaceImpact"))
            or row.get("adaptiveContact") is not False or row.get("contactIntervalMs")!=10
            or row.get("angularImpact") is not (mode=="angular")
            or any(type(p.get(k)) is not int or p[k]<0 for k in ("impacts","spinChanges","energyViolations"))
            or any(type(p.get(k)) not in (int,float) or not math.isfinite(p[k]) or p[k]<0 for k in
                ("energyBeforePerMassSum","energyAfterPerMassSum","maxSpinDeltaRadPerSec"))
            or p["spinChanges"]>p["impacts"] or (mode=="retained" and any(p.values()))
            or (mode=="angular" and p["impacts"]!=row["impactProbe"]["surface"])):
            raise ValueError("Invalid angular evidence")
    x,y=a["angularProbe"],b["angularProbe"]
    checks={"delivery":all(integrated.wall_ok(r) for r in rows.values()),
            "contactsObserved":a["impactProbe"]["surface"]>0 and y["impacts"]>0,
            "spinChanged":y["spinChanges"]>0 and y["maxSpinDeltaRadPerSec"]>0,
            "combinedRelativeEnergyBound":y["energyViolations"]==0 and y["energyAfterPerMassSum"]<=y["energyBeforePerMassSum"]+0.0001*max(1,y["energyBeforePerMassSum"]),
            "contactFreshness":all(r["adaptiveContactProbe"]["missingQueries"]==0 and r["adaptiveContactProbe"]["staleQueries"]==0 for r in rows.values())}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"angularProbe":y,
            "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
            "gameplayDelta":{k:[v-u for u,v in zip(a["gameplay"][k],b["gameplay"][k])] for k in integrated.METRICS}}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"Thin-shell ball, approximate AABB normal and body center velocity, provisional friction. Combined energy per mass in translating body frame, not total match energy. Existing aerodynamic and ground formulas unchanged; no claim of calibrated realism."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"angular-impact.json",stamp(report,a.runtime,"angular-impact"))
    checkpoint()
    for index,scenario in enumerate(integrated.SCENARIOS):
        rows={}
        for mode in (("retained","angular") if index==0 else ("angular","retained")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,determinism_probe=True,
                ordered_pose=True,collision_pose=True,contact_interval_ms=10,surface_impact=True,angular_impact=mode=="angular")
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
