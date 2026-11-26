"""Stage 62: compare root translation and measured body-part translation."""
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
    if set(rows)!={"root","limb"}:raise ValueError("Both modes required")
    a,b=rows["root"],rows["limb"]
    if a.get("hardwareThreads")!=b.get("hardwareThreads"):raise ValueError("Host changed")
    for mode,row in rows.items():
        p=row.get("limbProbe",{})
        if (not integrated.mode_ok(row,True) or not integrated.stats_ok(row) or not integrated.resource_ok(row)
            or any(row.get(k) is not True for k in ("determinismProbe","orderedPose","collisionPose","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact"))
            or row.get("adaptiveContact") is not False or row.get("contactIntervalMs")!=10
            or row.get("limbImpact") is not (mode=="limb")
            or any(type(p.get(k)) is not int or p[k]<0 for k in ("samples","queries","used","fallback"))
            or p["queries"]!=p["used"]+p["fallback"]
            or type(p.get("maxRelativeMps")) not in (float,int) or not math.isfinite(p["maxRelativeMps"])
            or not 0<=p["maxRelativeMps"]<=25.00001 or (mode=="root" and any(p.values()))):
            raise ValueError("Invalid limb evidence")
    y=b["limbProbe"]
    checks={"delivery":all(integrated.wall_ok(r) for r in rows.values()),
            "measuredVelocityUsed":y["samples"]>0 and y["used"]>0 and y["maxRelativeMps"]>0,
            "combinedEnergyBound":all(r["angularProbe"]["energyViolations"]==0 for r in rows.values()),
            "contactFreshness":all(r["adaptiveContactProbe"]["missingQueries"]==0 and r["adaptiveContactProbe"]["staleQueries"]==0 for r in rows.values())}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"limbProbe":y,
            "measuredQueryFraction":y["used"]/max(1,y["queries"]),
            "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
            "gameplayDelta":{k:[v-u for u,v in zip(a["gameplay"][k],b["gameplay"][k])] for k in integrated.METRICS}}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"Consecutive AABB center differences estimate limb translation, not angular velocity or exact surface motion. Duplicate names, nonconsecutive samples and large discontinuities fall back to root motion. Experimental only."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"limb-impact.json",stamp(report,a.runtime,"limb-impact"))
    checkpoint()
    for index,scenario in enumerate(integrated.SCENARIOS):
        rows={}
        for mode in (("root","limb") if index==0 else ("limb","root")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,determinism_probe=True,
                ordered_pose=True,collision_pose=True,contact_interval_ms=10,surface_impact=True,
                angular_impact=True,swept_impact=True,split_impact=True,chain_impact=True,limb_impact=mode=="limb")
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
