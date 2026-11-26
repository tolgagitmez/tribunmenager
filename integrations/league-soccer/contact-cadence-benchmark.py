"""Stage 55: collision pose cadence sweep; no claim that overlaps equal successful actions."""
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
INTERVALS=(100,50,20,10)
COUNTERS=("poseUpdates","maxAgeTicks","missingPoseChecks","ballOverlaps","keeperOverlaps","tackleOverlaps","controlledRequests")
def evaluate(rows):
    if set(rows)!=set(INTERVALS):raise ValueError("All four intervals required")
    if len({r.get("hardwareThreads") for r in rows.values()})!=1:raise ValueError("Host changed")
    base=rows[100]
    out={}
    for ms,row in rows.items():
        p=row.get("contactProbe",{})
        if (not integrated.mode_ok(row,True) or not integrated.resource_ok(row) or not integrated.stats_ok(row)
            or any(row.get(k) is not True for k in ("determinismProbe","orderedPose","collisionPose"))
            or row.get("contactIntervalMs")!=ms or p.get("intervalMs")!=ms
            or any(type(p.get(k)) is not int or p[k]<0 for k in COUNTERS)
            or p["poseUpdates"]==0 or p["keeperOverlaps"]>p["ballOverlaps"]
            or p["controlledRequests"]>p["ballOverlaps"]):
            raise ValueError("Invalid contact cadence evidence")
        checks={"delivery":integrated.wall_ok(row),"noMissingPose":p["missingPoseChecks"]==0,
                "maxPoseAgeWithinInterval":p["maxAgeTicks"]*10<=ms}
        out[str(ms)]={"checks":checks,"cadenceGatePassed":all(checks.values()),
            "maxObservedPoseAgeMs":p["maxAgeTicks"]*10,
            "cpuSecondsDelta":integrated.cpu(row)-integrated.cpu(base),
            "peakPssDeltaKiB":row["nativeMemory"]["peakPssKiB"]-base["nativeMemory"]["peakPssKiB"],
            "contactCounterDelta":{k:p[k]-base["contactProbe"][k] for k in COUNTERS},
            "gameplayDelta":{k:[b-a for a,b in zip(base["gameplay"][k],row["gameplay"][k])] for k in integrated.METRICS}}
    return out
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
        "status":"incomplete","scenarios":{},"completedRuns":[],
        "note":"All modes have 10 ms physics, 100 ms trace grid and 300000 ms native deadline. Counts are geometry intersections/requests, not distinct touches, tackles or saves. Single run per interval and fixture; no realism or deterministic parity claim."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"contact-cadence.json",stamp(report,a.runtime,"contact-cadence"))
    checkpoint()
    for index,scenario in enumerate(integrated.SCENARIOS):
        rows={}
        for ms in (INTERVALS if index==0 else INTERVALS[::-1]):
            prefix=a.out/f"{scenario}-{ms}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,
                    determinism_probe=True,ordered_pose=True,collision_pose=True,contact_interval_ms=ms)
            trace=Path(str(prefix)+".candidate.ndjson")
            with trace.open() as f:repeat.digest_frames(json.loads(line) for line in f)
            rows[ms]=row
            report["completedRuns"].append({"scenario":scenario,"intervalMs":ms,"match":row,
                "traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest()})
            checkpoint()
        report["scenarios"][scenario]=evaluate(rows)
        checkpoint()
    eligible=[ms for ms in INTERVALS if all(v[str(ms)]["cadenceGatePassed"] for v in report["scenarios"].values())]
    report["eligibleIntervalsMs"]=eligible
    report["status"]="manual-review-required" if eligible else "blocked"
    checkpoint()
    print(json.dumps({"status":report["status"],"eligibleIntervalsMs":eligible,"productionEnabled":False}),flush=True)
    if not eligible:raise SystemExit(2)
if __name__=="__main__":main()
