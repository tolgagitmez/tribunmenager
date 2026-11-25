"""Diagnostic acceptance gates. Passing never authorizes a production engine switch."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from statistics import mean
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("timing",HERE/"timing-benchmark.py")
timing=importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)
SCENARIOS=("counter-possession","balanced","possession-counter")
TARGET=300000
# Provisional acceptance targets, not claims about real-world football.
MIN_PAIRS=3
MIN_SHOTS=6
MIN_CONTROLLED_BOX=3
DURATION_TOLERANCE_MS=1000

def pair_sum(v):
    if not isinstance(v,list) or len(v)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in v):
        raise ValueError("Missing/invalid pair metric")
    return sum(v)

def metrics(report):
    if report.get("engine")!="league-soccer" or report.get("schema")!=1:raise ValueError("Invalid report")
    sampled=report["sampled"]
    return {"shots":pair_sum(report["shots"]),"onTarget":pair_sum(report["onTarget"]),
        "goals":pair_sum(report["score"]),"controlledBox":pair_sum(sampled["controlledBoxCrossings"]),
        "finalThirdMs":pair_sum(sampled["controlledFinalThirdMs"]),
        "combinations":pair_sum(report["combinations"]["completed"]),
        "reboundShots":pair_sum(report["rebounds"]["followupShots"])}

def evaluate(rows):
    if len({r["seed"] for r in rows})!=len(rows) or len({r["fixtureHash"] for r in rows})!=len(rows):
        raise ValueError("Duplicate experiment")
    if len({r["scenario"] for r in rows})!=len(rows) or any(r["scenario"] not in SCENARIOS for r in rows):
        raise ValueError("Unexpected scenario")
    for r in rows:
        if not isinstance(r["calibratedMs"],int) or r["calibratedMs"]<=0:raise ValueError("Invalid timing")
    if not rows: return {"schema":1,"status":"blocked","authoritative":False,"checks":{"sampleSize":False}}
    averages={side:{k:mean(r[side][k] for r in rows) for k in rows[0][side]} for side in ("baseline","candidate","calibrated")}
    b,c,d=(averages[k] for k in ("baseline","candidate","calibrated"))
    checks={
        "sampleSize":len(rows)>=MIN_PAIRS and set(r["scenario"] for r in rows)==set(SCENARIOS),
        "candidateShotVolume":c["shots"]>=MIN_SHOTS and c["shots"]>=b["shots"],
        "candidateBoxEntries":c["controlledBox"]>=MIN_CONTROLLED_BOX and c["controlledBox"]>=b["controlledBox"],
        "calibratedShotVolume":d["shots"]>=MIN_SHOTS,
        "calibratedBoxEntries":d["controlledBox"]>=MIN_CONTROLLED_BOX,
        "calibratedDuration":all(abs(r["calibratedMs"]-TARGET)<=DURATION_TOLERANCE_MS for r in rows),
        "observedCombination":sum(r["candidate"]["combinations"]+r["calibrated"]["combinations"] for r in rows)>0,
        "observedReboundShot":sum(r["candidate"]["reboundShots"]+r["calibrated"]["reboundShots"] for r in rows)>0,
    }
    return {"schema":1,"authoritative":False,"status":"expanded-validation-eligible" if all(checks.values()) else "blocked",
        "thresholds":{"minimumPairs":MIN_PAIRS,"meanShots":MIN_SHOTS,"meanControlledBoxEntries":MIN_CONTROLLED_BOX,"durationTargetMs":TARGET,"durationToleranceMs":DURATION_TOLERANCE_MS},
        "checks":checks,"means":averages,"rows":rows,
        "note":"Diagnostic only. A 1-second tolerance is not an exact 300-second live clock. No promotion, concurrency, restart or season certification."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("runtime")
    parser.add_argument("fixtures")
    parser.add_argument("out")
    args=parser.parse_args()
    out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name in SCENARIOS:
        fixture=Path(args.fixtures).resolve()/(name+".json")
        blob=fixture.read_bytes()
        seed=json.loads(blob)["seed"]
        prefix=str(out/name)
        row={"scenario":name,"seed":seed,"fixtureHash":hashlib.sha256(blob).hexdigest()}
        for key,scale,quick,attack in (("baseline","1.0","0","baseline"),("candidate","1.0","0","short-match"),("calibrated","1.10","1","short-match")):
            elapsed=timing.run(args.runtime,str(fixture),prefix,(key,scale,quick),attack)
            result=json.loads(Path(prefix+"."+key+".ndjson.attack.json").read_text())
            season=json.loads(Path(prefix+"."+key+".ndjson.season.json").read_text())
            manifest=json.loads(Path(prefix+"."+key+".ndjson.fixture.json").read_text())
            if manifest["seed"]!=seed or season.get("done") is not True or season.get("authoritative") is not False or season["score"]!=result["score"]:
                raise ValueError("Fixture/season identity mismatch")
            row[key]=metrics(result)
            row[key+"WallMs"]=elapsed["observedWallMs"]
            print(json.dumps({"scenario":name,"profile":key,"timing":elapsed,"metrics":row[key]}),flush=True)
        row["calibratedMs"]=row["calibratedWallMs"]
        rows.append(row)
        report=evaluate(rows)
        (out/"readiness.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps(report),flush=True)

if __name__=="__main__":main()
