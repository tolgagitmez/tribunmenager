"""Offline comparative review of independent attack trials, never automatic activation.

Reports from different builds are not pooled. Recompute metrics from the actual
per-fixture paired rows; ignore claimed mean deltas and labels in report files.
"""
import argparse
import json
from pathlib import Path
from statistics import mean

SCENARIOS={"counter-possession":2026,"balanced":2027,"possession-counter":2028}
PROFILES=("retention","boxRuns","timedAttack")
FIELDS=("shots","onTarget","goals","controlledBox","finalThirdMs",
        "sameTeamRecovery","opponentRecovery","unresolved")
def integer(v):
    return type(v) is int and v>=0

def read_rows(report,profile):
    if not isinstance(report,dict) or report.get("authoritative") is not False:
        raise ValueError("Expected non-authoritative experiment report")
    rows=report.get("rows")
    if not isinstance(rows,list) or not rows or len(rows)>len(SCENARIOS):
        raise ValueError("Missing or invalid pairs")
    if type(report.get("pairCount")) is not int or report["pairCount"]!=len(rows):
        raise ValueError("Pair count mismatch")
    seen=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError("Malformed paired row")
        scenario=row.get("scenario")
        if scenario not in SCENARIOS or scenario in seen or row.get("seed")!=SCENARIOS[scenario]:
            raise ValueError("Unexpected or duplicate scenario/seed")
        seen.add(scenario)
        for side in ("control",profile):
            m=row.get(side)
            fields=FIELDS+(("twoBoxAttackersMs",) if profile=="boxRuns" else ())
            if not isinstance(m,dict) or any(not integer(m.get(k)) for k in fields):
                raise ValueError("Incomplete or negative match metrics")
            if m["onTarget"]>m["shots"] or m["finalThirdMs"]>300000:
                raise ValueError("Impossible sampled metrics")
            if profile=="boxRuns" and m["twoBoxAttackersMs"]>300000:
                raise ValueError("Invalid box support duration")
            if not integer(row.get(side+"WallMs")) or not row[side+"WallMs"]:
                raise ValueError("Missing wall-clock observation")
            if profile=="timedAttack":
                c=row.get(side+"Contacts")
                if not isinstance(c,dict) or any(not integer(c.get(k)) for k in ("passes","receipts","shots")) or not c["passes"]>=c["receipts"]>=c["shots"] or c["shots"]>m["shots"]:
                    raise ValueError("Invalid actual contact counters")
                if side=="control" and any(c[k] for k in ("passes","receipts","shots")):
                    raise ValueError("Experimental flag leaked into control")
    return rows,seen

def recovery(rows,side):
    same=sum(r[side]["sameTeamRecovery"] for r in rows)
    opp=sum(r[side]["opponentRecovery"] for r in rows)
    unresolved=sum(r[side]["unresolved"] for r in rows)
    total=same+opp
    return {"same":same,"opponent":opp,"unresolved":unresolved,
            "rate":same/total if total else None,
            "resolvedFraction":total/(total+unresolved) if total+unresolved else None}

def assess(report,profile):
    rows,seen=read_rows(report,profile)
    fields=FIELDS+(("twoBoxAttackersMs",) if profile=="boxRuns" else ())
    avg={s:{k:mean(r[s][k] for r in rows) for k in fields} for s in ("control",profile)}
    delta={k:avg[profile][k]-avg["control"][k] for k in fields}
    recover={s:recovery(rows,s) for s in ("control",profile)}
    a,b=recover["control"],recover[profile]
    rate_delta=None if a["rate"] is None or b["rate"] is None else b["rate"]-a["rate"]
    resolved_delta=None if a["resolvedFraction"] is None or b["resolvedFraction"] is None else b["resolvedFraction"]-a["resolvedFraction"]
    # Conservative provisional screening, not a significance test. No invented xG.
    checks={
      "threeDistinctPairs":seen==set(SCENARIOS),
      "shotVolumeNotLower":delta["shots"]>=0,
      "onTargetNotLower":delta["onTarget"]>=0,
      "controlledEntriesNotLower":delta["controlledBox"]>=0,
      "recoveryRateNotMateriallyLower":rate_delta is not None and rate_delta>=-.05-1e-9,
      "resolvedCoverageNotMateriallyLower":resolved_delta is not None and resolved_delta>=-.05-1e-9,
      "someAttackingImprovement":delta["shots"]>0 or delta["onTarget"]>0 or delta["controlledBox"]>0,
    }
    contacts=None
    if profile=="retention":
        checks["intendedEffect"]=rate_delta is not None and rate_delta>=.05-1e-9
    elif profile=="boxRuns":
        checks["intendedEffect"]=delta["twoBoxAttackersMs"]>0 and delta["controlledBox"]>0
    else:
        contacts={k:sum(r[profile+"Contacts"][k] for r in rows) for k in ("passes","receipts","shots")}
        checks["intendedEffect"]=contacts["receipts"]>0 and contacts["shots"]>0
    # Report individual worst cases so averaging cannot hide all scenario regressions.
    individual=[{"scenario":r["scenario"],
                 "shotsDelta":r[profile]["shots"]-r["control"]["shots"],
                 "boxDelta":r[profile]["controlledBox"]-r["control"]["controlledBox"],
                 "onTargetDelta":r[profile]["onTarget"]-r["control"]["onTarget"],
                 "wallMs":{"control":r["controlWallMs"],profile:r[profile+"WallMs"]}}
                for r in rows]
    checks["noScenarioLosesAllObservedShots"]=all(r["control"]["shots"]==0 or r[profile]["shots"]>0 for r in rows)
    checks["noScenarioLosesAllControlledEntries"]=all(r["control"]["controlledBox"]==0 or r[profile]["controlledBox"]>0 for r in rows)
    status="needs-more-pairs" if not checks["threeDistinctPairs"] else "retest-candidate" if all(checks.values()) else "not-selected"
    return {"status":status,"pairCount":len(rows),"checks":checks,"means":avg,
            "meanDelta":delta,"recovery":recover,"recoveryRateDelta":rate_delta,
            "actualContacts":contacts,"individual":individual}

def review(reports):
    results={}
    for profile in PROFILES:
        if profile not in reports:
            results[profile]={"status":"missing"}
        else:
            try:results[profile]=assess(reports[profile],profile)
            except (ValueError,TypeError,KeyError) as e:results[profile]={"status":"invalid","error":str(e)}
    candidates=[p for p,r in results.items() if r["status"]=="retest-candidate"]
    return {"schema":1,"authoritative":False,"productionEnabled":False,
            "combinedEnabled":False,"profiles":results,"retestCandidates":candidates,
            "status":"same-build-retest-required" if candidates else "blocked",
            "note":"Independent historical reports are descriptive only; they do not establish common executable identity or causality. Retest selected profiles on one pinned runtime, then test interactions on held-out seeds. No automatic combination or deployment."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--retention",type=Path)
    p.add_argument("--box-runs",type=Path)
    p.add_argument("--timed-attack",type=Path)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    inputs={"retention":a.retention,"boxRuns":a.box_runs,"timedAttack":a.timed_attack}
    reports={k:json.loads(v.read_text()) for k,v in inputs.items() if v is not None}
    result=review(reports)
    output=json.dumps(result,indent=2,allow_nan=False)+"\n"
    if a.out:a.out.write_text(output)
    print(output,end="")
if __name__=="__main__":main()
