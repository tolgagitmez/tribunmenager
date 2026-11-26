"""Stage 61: bounded chain after first predicted split contact."""
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
    if set(rows)!={"single","chain"}:raise ValueError("Both modes required")
    a,b=rows["single"],rows["chain"]
    if a.get("hardwareThreads")!=b.get("hardwareThreads"):raise ValueError("Host changed")
    for mode,row in rows.items():
        p=row.get("chainProbe",{})
        if (not integrated.mode_ok(row,True) or not integrated.stats_ok(row) or not integrated.resource_ok(row)
            or any(row.get(k) is not True for k in ("determinismProbe","orderedPose","collisionPose","surfaceImpact","angularImpact","sweptImpact","splitImpact"))
            or row.get("adaptiveContact") is not False or row.get("contactIntervalMs")!=10
            or row.get("chainImpact") is not (mode=="chain")
            or any(type(p.get(k)) is not int or p[k]<0 for k in ("ticks","extra","rejected","cap","maxContacts"))
            or type(p.get("lastMs")) not in (int,float) or not math.isfinite(p["lastMs"]) or not 0<=p["lastMs"]<=10.000001
            or p["maxContacts"]>3 or p["extra"]>2*p["ticks"] or p["cap"]>p["ticks"]
            or (mode=="single" and any(p.values()))
            or (mode=="chain" and p["ticks"]!=row["splitProbe"]["applied"])):
            raise ValueError("Invalid chain evidence")
    y=b["chainProbe"]
    checks={"delivery":all(integrated.wall_ok(r) for r in rows.values()),
            "chainExecuted":y["extra"]>0 and y["maxContacts"]>=2,
            "bounded":y["maxContacts"]<=3,
            "combinedEnergyBound":all(r["angularProbe"]["energyViolations"]==0 for r in rows.values()),
            "contactFreshness":all(r["adaptiveContactProbe"]["missingQueries"]==0 and r["adaptiveContactProbe"]["staleQueries"]==0 for r in rows.values())}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"chainProbe":y,
            "cpuSecondsDelta":integrated.cpu(b)-integrated.cpu(a),
            "gameplayDelta":{k:[v-u for u,v in zip(a["gameplay"][k],b["gameplay"][k])] for k in integrated.METRICS}}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","completedRuns":[],"scenarios":{},
        "note":"Only after a positive-time first predicted split. Up to three distinct players per tick, translating snapshot AABBs, original eligibility at tick start, no recursive referee decision or rotating limb sweep. No production or calibrated realism claim."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"chain-impact.json",stamp(report,a.runtime,"chain-impact"))
    checkpoint()
    for index,scenario in enumerate(integrated.SCENARIOS):
        rows={}
        for mode in (("single","chain") if index==0 else ("chain","single")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,determinism_probe=True,
                ordered_pose=True,collision_pose=True,contact_interval_ms=10,surface_impact=True,
                angular_impact=True,swept_impact=True,split_impact=True,chain_impact=mode=="chain")
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
