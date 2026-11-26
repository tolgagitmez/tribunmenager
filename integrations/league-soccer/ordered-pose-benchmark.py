"""Stage 53: test pose scheduling in otherwise identical candidate profiles."""
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
def evaluate(runs):
    if set(runs)!={"async","ordered"} or any(len(x)!=2 for x in runs.values()):
        raise ValueError("Two runs per scheduling mode required")
    flat=runs["async"]+runs["ordered"]
    if len({r["runId"] for r in flat})!=4:
        raise ValueError("Duplicate run")
    for name,rows in runs.items():
        for row in rows:
            match=row["match"]
            if (not integrated.mode_ok(match,True) or not integrated.stats_ok(match) or not integrated.resource_ok(match)
                or match.get("determinismProbe") is not True or match.get("orderedPose") is not (name=="ordered")):
                raise ValueError("Invalid pose schedule evidence")
    result={}
    for name,rows in runs.items():
        a,b=rows
        compared=repeat.compare(a["digests"],b["digests"])
        compared["finalMetricsEqual"]=a["match"]["gameplay"]==b["match"]["gameplay"]
        compared["deliveryPassed"]=all(integrated.wall_ok(r["match"]) for r in rows)
        result[name]=compared
    cross=repeat.compare(runs["async"][0]["digests"],runs["ordered"][0]["digests"])
    return {"withinMode":result,"firstCrossModeComparison":cross,
            "orderedObservedRepeatability":all(result["ordered"][k] for k in ("observedTraceEqual","finalMetricsEqual","deliveryPassed")),
            "asyncObservedRepeatability":all(result["async"][k] for k in ("observedTraceEqual","finalMetricsEqual","deliveryPassed")),
            "productionEnabled":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"identity":identity,
            "completedRuns":[],"scenarios":{},"status":"incomplete",
            "note":"Both modes use integrated candidate settings. Only scheduling differs. Sampled equality is not full deterministic proof."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"ordered-pose.json",stamp(report,a.runtime,"ordered-pose"))
    checkpoint()
    for scenario in integrated.SCENARIOS:
        runs={"async":[],"ordered":[]}
        for idx,name in enumerate(("async","ordered","ordered","async")):
            key=f"{scenario}-{idx}-{name}"
            prefix=a.out/key
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,
                determinism_probe=True,ordered_pose=name=="ordered")
            trace=Path(str(prefix)+".candidate.ndjson")
            with trace.open() as f:digests=repeat.digest_frames(json.loads(line) for line in f)
            runs[name].append({"runId":key,"match":row,"digests":digests})
            report["completedRuns"].append({"runId":key,"scenario":scenario,"schedule":name,"match":row,
                                            "traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest()})
            checkpoint()
        report["scenarios"][scenario]=evaluate(runs)
        checkpoint()
    report["status"]="manual-review-required" if all(x["orderedObservedRepeatability"] for x in report["scenarios"].values()) else "blocked"
    checkpoint()
    print(json.dumps({"status":report["status"],"productionEnabled":False,"scenarios":report["scenarios"]}),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
