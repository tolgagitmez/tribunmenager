"""Stage 52: repeated fixed-grid observations with visual RNG isolated in both modes."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("integrated",HERE/"integrated-profile.py")
integrated=importlib.util.module_from_spec(spec);spec.loader.exec_module(integrated)
from release_evidence import stamp

REPEATS=2
# Compare only observable simulation state, never absolute startup or host timestamps.
FRAME_FIELDS=("matchMs","done","score","ball","ballVelocity","stats","phaseCode",
              "setPiece","inPlay","attackDirection","combinations","rebounds","timedAttacks")
PLAYER_FIELDS=("databaseId","team","position","velocity","direction","formationRole",
               "formationTarget","goalkeeper","uniquePossession")
def digest_frames(frames):
    rows={}
    for frame in frames:
        clock=frame["fixedClock"]
        if not clock["started"]:continue
        tick=clock["elapsedMs"]
        if tick in rows:raise ValueError("Repeated native clock sample")
        players=sorted(({k:p[k] for k in PLAYER_FIELDS} for p in frame["players"]),
                       key=lambda p:(p["team"],p["databaseId"]))
        if len({(p["team"],p["databaseId"]) for p in players})!=len(players):
            raise ValueError("Duplicate player identity")
        state={**{k:frame[k] for k in FRAME_FIELDS},"players":players}
        rows[tick]=hashlib.sha256(json.dumps(state,sort_keys=True,separators=(",",":"),
                                            allow_nan=False).encode()).hexdigest()
    if set(rows)!=set(range(0,300001,100)):
        raise ValueError("Incomplete fixed 100 ms sampling grid")
    return rows

def compare(a,b):
    common=set(a)&set(b)
    different=sorted(t for t in common if a[t]!=b[t])
    return {"samplesA":len(a),"samplesB":len(b),"commonSamples":len(common),
            "sampleGridsEqual":set(a)==set(b),"differentCommonSamples":len(different),
            "firstDifferentCommonMs":different[0] if different else None,
            "firstUnmatchedSampleMs":min(set(a)^set(b),default=None),
            "observedTraceEqual":bool(common) and set(a)==set(b) and not different}

def evaluate_scenario(runs):
    if set(runs)!={"reference","candidate"} or any(len(v)!=REPEATS for v in runs.values()):
        raise ValueError("Two independent process launches per mode required")
    for mode,rows in runs.items():
        candidate=mode=="candidate"
        for row in rows:
            if row["match"].get("determinismProbe") is not True or not integrated.mode_ok(row["match"],candidate) or not integrated.stats_ok(row["match"]) or not integrated.resource_ok(row["match"]):
                raise ValueError("Invalid mode or resource evidence")
    allrows=runs["reference"]+runs["candidate"]
    if len({x["runId"] for x in allrows})!=4 or len({x["match"]["hardwareThreads"] for x in allrows})!=1:
        raise ValueError("Duplicate run ID or host changed")
    def repeated(mode):
        a,b=runs[mode]
        result=compare(a["digests"],b["digests"])
        result["finalMetricsEqual"]=a["match"]["gameplay"]==b["match"]["gameplay"]
        return result
    within={m:repeated(m) for m in runs}
    cross=[]
    for a in runs["reference"]:
        for b in runs["candidate"]:
            cross.append({**compare(a["digests"],b["digests"]),
                        "referenceRun":a["runId"],"candidateRun":b["runId"],
                        "finalMetricsEqual":a["match"]["gameplay"]==b["match"]["gameplay"]})
    def summary(mode):
        matches=[x["match"] for x in runs[mode]]
        return {"medianCpuSeconds":statistics.median(integrated.cpu(x) for x in matches),
                "medianPeakPssKiB":statistics.median(x["nativeMemory"]["peakPssKiB"] for x in matches),
                "metricRanges":{k:[[min(x["gameplay"][k][t] for x in matches),max(x["gameplay"][k][t] for x in matches)] for t in (0,1)] for k in integrated.METRICS},
                "deliveryPassed":all(integrated.wall_ok(x) for x in matches)}
    summaries={m:summary(m) for m in runs}
    same=lambda x:x["observedTraceEqual"] and x["finalMetricsEqual"]
    checks={"referenceRepeatable":same(within["reference"]),
            "candidateRepeatable":same(within["candidate"]),
            "crossModeObservedParity":all(same(x) for x in cross),
            "delivery":all(x["deliveryPassed"] for x in summaries.values())}
    return {"withinMode":within,"crossMode":cross,"summaries":summaries,"checks":checks,
            "observedParityGatePassed":all(checks.values()),
            "medianCpuSecondsDelta":summaries["candidate"]["medianCpuSeconds"]-summaries["reference"]["medianCpuSeconds"],
            "medianPeakPssKiBDelta":summaries["candidate"]["medianPeakPssKiB"]-summaries["reference"]["medianPeakPssKiB"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    identity=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"status":"incomplete",
            "identity":identity,"scenarios":{},"completedRuns":[],
            "note":"Both modes isolate audited visual RNG consumers and use kickoff-relative samples. Full-scene null reference is not OpenGL. Remaining RNG consumers and task scheduling are not proven deterministic. No release authorization."}
    target=a.out/"profile-repeatability.json"
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        integrated.save(target,stamp(report,a.runtime,"profile-repeatability"))
    checkpoint()
    for scenario in integrated.SCENARIOS:
        runs={"reference":[],"candidate":[]}
        # ABBA balances some warm-cache/order effects without mixing processes.
        for idx,mode in enumerate(("reference","candidate","candidate","reference")):
            run_id=f"{scenario}-{idx}-{mode}"
            prefix=a.out/run_id
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,mode=="candidate",determinism_probe=True)
            trace=Path(str(prefix)+"."+mode+".ndjson")
            with trace.open() as f:digests=digest_frames(json.loads(line) for line in f)
            runs[mode].append({"runId":run_id,"match":row,"digests":digests})
            report["completedRuns"].append({"runId":run_id,"scenario":scenario,"mode":mode,
                      "traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest(),"match":row})
            checkpoint()
        report["scenarios"][scenario]=evaluate_scenario(runs)
        checkpoint()
    report["status"]="manual-review-required" if all(x["observedParityGatePassed"] for x in report["scenarios"].values()) else "blocked"
    checkpoint()
    print(json.dumps({"status":report["status"],"productionEnabled":False,
        "scenarios":{k:v["checks"] for k,v in report["scenarios"].items()}}),flush=True)
    # Collection success is distinct from passing a release gate.
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
