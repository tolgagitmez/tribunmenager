"""Stage 60: split first native ball integration interval at predicted body contact."""
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
    if set(rows)!={"early","split"}:raise ValueError("Both modes required")
    a,b=rows["early"],rows["split"]
    if a.get("hardwareThreads")!=b.get("hardwareThreads"):raise ValueError("Host changed")
    for mode,row in rows.items():
        p=row.get("splitProbe",{})
        if (not integrated.mode_ok(row,True) or not integrated.stats_ok(row) or not integrated.resource_ok(row)
            or any(row.get(k) is not True for k in ("determinismProbe","orderedPose","collisionPose","surfaceImpact","angularImpact","sweptImpact"))
            or row.get("adaptiveContact") is not False or row.get("contactIntervalMs")!=10
            or row.get("splitImpact") is not (mode=="split")
            or any(type(p.get(k)) is not int or p[k]<0 for k in ("queued","applied","cancelled"))
            or p["queued"]!=p["applied"]+p["cancelled"]
            or any(type(p.get(k)) not in (int,float) or not math.isfinite(p[k]) or p[k]<0 for k in ("beforeMs","afterMs"))
            or abs(p["beforeMs"]+p["afterMs"]-10*p["applied"])>0.001
            or (mode=="early" and any(p.values()))
            or (mode=="split" and p["applied"]!=row["sweptProbe"]["applied"])):
            raise ValueError("Invalid split timing evidence")
    y=b["splitProbe"]
    checks={"delivery":all(integrated.wall_ok(r) for r in rows.values()),
            "bothModesContactObserved":a["sweptProbe"]["applied"]>0 and y["applied"]>0,
            "splitTimeConserved":abs(y["beforeMs"]+y["afterMs"]-10*y["applied"])<=0.001,
            "combinedEnergyBound":all(r["angularProbe"]["energyViolations"]==0 for r in rows.values()),
            "contactFreshness":all(r["adaptiveContactProbe"]["missingQueries"]==0 and r["adaptiveContactProbe"]["staleQueries"]==0 for r in rows.values())}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"splitProbe":y,
            "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
            "gameplayDelta":{k:[v-u for u,v in zip(a["gameplay"][k],b["gameplay"][k])] for k in integrated.METRICS}}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"One predicted body impact per tick. Existing force integrator runs before and after contact; impulse recalculated with intermediate momentum and spin. Linear predicted TOI and translating AABB approximate actual trajectory. Referee runs before contact query in split mode. No recursive collisions or calibrated realism claim."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"split-impact.json",stamp(report,a.runtime,"split-impact"))
    checkpoint()
    for index,scenario in enumerate(integrated.SCENARIOS):
        rows={}
        for mode in (("early","split") if index==0 else ("split","early")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,determinism_probe=True,
                ordered_pose=True,collision_pose=True,contact_interval_ms=10,surface_impact=True,
                angular_impact=True,swept_impact=True,split_impact=mode=="split")
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
