"""Stage 74: repeated paired AI quality qualification, not production approval."""
import argparse
import hashlib
import importlib.util
import json
import math
import statistics
from pathlib import Path
from release_evidence import stamp
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("carry",HERE/"creative-carry-benchmark.py")
carry=importlib.util.module_from_spec(spec);spec.loader.exec_module(carry)
integrated=carry.integrated
SCENARIOS=carry.SCENARIOS
REPEATS=2
def identity(runtime,fixtures):
    paths=[runtime/"gameplayfootball",runtime/"tribun-runtime.json",runtime/"native-match.config",
           *(fixtures/(s+".json") for s in SCENARIOS)]
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
def evaluate_pair(rows):
    result=carry.evaluate(rows)
    a,b=rows["reference"],rows["carry"]
    result.update(referenceCpu=integrated.cpu(a),candidateCpu=integrated.cpu(b),
                  referencePss=a["nativeMemory"]["peakPssKiB"],candidatePss=b["nativeMemory"]["peakPssKiB"],
                  referenceShots=sum(a["gameplay"]["shots"]),candidateShots=sum(b["gameplay"]["shots"]),
                  referenceOnTarget=sum(a["gameplay"]["onTarget"]),candidateOnTarget=sum(b["gameplay"]["onTarget"]))
    return result
def aggregate(scenarios):
    if set(scenarios)!=set(SCENARIOS) or any(len(v)!=REPEATS for v in scenarios.values()):
        raise ValueError("Two independent pairs in each of three scenarios required")
    rows=[r for v in scenarios.values() for r in v]
    for r in rows:
        if any(not math.isfinite(r[k]) for k in ("referenceCpu","candidateCpu","referencePss","candidatePss","passAccuracyDelta")):
            raise ValueError("Nonfinite metrics")
        if min(r["referenceCpu"],r["referencePss"])<=0:raise ValueError("Invalid resource baseline")
    total=lambda k:sum(r[k] for r in rows)
    baseShots,newShots=total("referenceShots"),total("candidateShots")
    baseAccuracy=total("referenceOnTarget")/max(1,baseShots)
    newAccuracy=total("candidateOnTarget")/max(1,newShots)
    cpuRatio=statistics.median(r["candidateCpu"]/r["referenceCpu"] for r in rows)
    pssRatio=max(r["candidatePss"]/r["referencePss"] for r in rows)
    attempts=sum(sum(r["decisionProbe"]["attempts"]) for r in rows)
    technical=sum(sum(r["decisionProbe"]["technical"]) for r in rows)
    lost=sum(sum(r["decisionProbe"]["lost"]) for r in rows)
    # Pair consistency guards against one spectacular but unstable game driving the result.
    checks={"delivery":all(r["deliveryPassed"] for r in rows),
        "allPairsExercised":all(r["policySelected"] and r["controlledCarries"]>0 for r in rows),
        "boxEntriesImproved":total("boxCrossingsDelta")>0,
        "boxEntriesConsistent":sum(r["boxCrossingsDelta"]>=0 for r in rows)>=4,
        "noScenarioBoxCollapse":all(sum(r["boxCrossingsDelta"] for r in v)>=-2 for v in scenarios.values()),
        "shotsNotReduced":total("shotsDelta")>=0,
        "shotsConsistent":sum(r["shotsDelta"]>=0 for r in rows)>=4,
        "onTargetNotReduced":total("onTargetDelta")>=0,
        "shotAccuracyProtected":newAccuracy>=baseAccuracy-.05,
        "passAccuracyProtected":all(r["passAccuracyDelta"]>=-.08 for r in rows),
        "cpuBudget":cpuRatio<=1.10,"memoryBudget":pssRatio<=1.10}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),
        "pairs":len(rows),"attempts":attempts,"controlledCarries":total("controlledCarries"),
        "lost":lost,"technicalAttempts":technical,"technicalCoverageObserved":technical>0,
        "boxCrossingsDelta":total("boxCrossingsDelta"),"shotsDelta":total("shotsDelta"),
        "onTargetDelta":total("onTargetDelta"),"referenceShotAccuracy":baseAccuracy,
        "candidateShotAccuracy":newAccuracy,"medianCpuRatio":cpuRatio,"maxPssRatio":pssRatio}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    frozen=identity(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"combinedQualified":False,
        "status":"incomplete","identity":frozen,"policy":"creative_carry",
        "historicalAudit":json.loads((HERE/"quality-audit.json").read_text()),
        "completedRuns":[],"scenarios":{},
        "note":"Two process launches per mode per scenario, ABBA or BAAB order. Same three fixture seeds, not independent new seeds. No claim of determinism or causal proof. Technical-grade coverage is reported separately; combined policies remain prohibited."}
    def checkpoint():
        if identity(a.runtime,a.fixtures)!=frozen:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"quality-qualification.json",stamp(report,a.runtime,"quality-qualification"))
    checkpoint()
    for index,scenario in enumerate(SCENARIOS):
        report["scenarios"][scenario]=[]
        for repeat in range(REPEATS):
            modes=("reference","carry") if (index+repeat)%2==0 else ("carry","reference")
            rows={}
            for mode in modes:
                prefix=a.out/f"{scenario}-{repeat}-{mode}"
                row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,creative_carry=mode=="carry")
                trace=Path(str(prefix)+".candidate.ndjson")
                rows[mode]=row
                report["completedRuns"].append({"scenario":scenario,"repeat":repeat,"mode":mode,
                    "match":row,"traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest()})
                checkpoint()
            report["scenarios"][scenario].append(evaluate_pair(rows))
            checkpoint()
    report["aggregate"]=aggregate(report["scenarios"])
    report["status"]="manual-review-required" if report["aggregate"]["diagnosticPassed"] else "blocked"
    checkpoint()
    print(json.dumps({"status":report["status"],"aggregate":report["aggregate"],
          "combinedQualified":False,"productionEnabled":False}),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
