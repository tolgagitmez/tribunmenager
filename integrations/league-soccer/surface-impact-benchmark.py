"""Stage 57: isolate accidental body impact response, not intentional kicks or catches."""
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
    if set(rows)!={"legacy","surface"}:raise ValueError("Both modes required")
    a,b=rows["legacy"],rows["surface"]
    if a.get("hardwareThreads")!=b.get("hardwareThreads"):raise ValueError("Host changed")
    for mode,row in rows.items():
        p=row.get("impactProbe",{})
        if (not integrated.mode_ok(row,True) or not integrated.resource_ok(row) or not integrated.stats_ok(row)
            or any(row.get(k) is not True for k in ("determinismProbe","orderedPose","collisionPose"))
            or row.get("contactIntervalMs")!=10 or row.get("adaptiveContact") is not False
            or row.get("surfaceImpact") is not (mode=="surface")
            or any(type(p.get(k)) is not int or p[k]<0 for k in ("legacy","surface","rejected","energyViolations"))
            or not isinstance(p.get("regions"),list) or len(p["regions"])!=6
            or any(type(n) is not int or n<0 for n in p["regions"])
            or sum(p["regions"])!=p["surface"]
            or any(type(p.get(k)) not in (int,float) or not math.isfinite(p[k]) or p[k]<0 for k in ("relativeSpeedBeforeSum","relativeSpeedAfterSum"))
            or (mode=="legacy" and any(p[k] for k in ("surface","rejected","energyViolations","relativeSpeedBeforeSum","relativeSpeedAfterSum")))
            or (mode=="surface" and p["legacy"])):
            raise ValueError("Invalid impact evidence")
    x,y=a["impactProbe"],b["impactProbe"]
    checks={"delivery":all(integrated.wall_ok(r) for r in rows.values()),
            "contactsObserved":x["legacy"]>0 and y["surface"]>0,
            "relativeEnergyBound":y["energyViolations"]==0 and y["relativeSpeedAfterSum"]<=y["relativeSpeedBeforeSum"]+0.0001,
            "contactFreshness":all(r["adaptiveContactProbe"]["missingQueries"]==0 and r["adaptiveContactProbe"]["staleQueries"]==0 for r in rows.values())}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),
            "regionNames":["foot","leg","torso","head","arm","other"],
            "impactProbe":y,"cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
            "gameplayDelta":{k:[v-u for u,v in zip(a["gameplay"][k],b["gameplay"][k])] for k in integrated.METRICS},
            "observedGameplayEqual":a["gameplay"]==b["gameplay"]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"Approximate axis-aligned contact normals, player center velocity, region coefficients are provisional. Relative-speed sum is not total kinetic energy. No angular impulse, continuous collision detection, handball or catch logic added. One pair per fixture is not a realism verdict."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"surface-impact.json",stamp(report,a.runtime,"surface-impact"))
    checkpoint()
    for index,scenario in enumerate(integrated.SCENARIOS):
        rows={}
        for mode in (("legacy","surface") if index==0 else ("surface","legacy")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,determinism_probe=True,
                ordered_pose=True,collision_pose=True,contact_interval_ms=10,surface_impact=mode=="surface")
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
