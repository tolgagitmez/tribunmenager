"""Stage 77: observed close-control contacts and sampled ball separation."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from release_evidence import stamp
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("integrated",HERE/"integrated-profile.py")
integrated=importlib.util.module_from_spec(spec);spec.loader.exec_module(integrated)
SCENARIOS=("balanced","counter-possession","possession-counter")
def motion(trace):
    count=far=0;gap_sum=0.0;advance=0.0
    with trace.open() as f:
        for line in f:
            frame=json.loads(line)
            if not frame["fixedClock"]["started"] or not frame["inPlay"] or frame["setPiece"]:continue
            ball=frame["ball"]
            if ball[2]>.35:continue
            owners=[p for p in frame["players"] if p["uniquePossession"] and not p["goalkeeper"]]
            if len(owners)!=1:continue
            p=owners[0]
            gap=math.hypot(ball[0]-p["position"][0],ball[1]-p["position"][1])
            if not math.isfinite(gap):raise ValueError("Invalid separation sample")
            count+=1;far+=int(gap>1.5);gap_sum+=gap
            advance+=p["velocity"][0]*frame["attackDirection"][p["team"]]
    if count<10:raise ValueError("Too few possession observations")
    return {"samples":count,"far":far,"meanGap":gap_sum/count,"forwardSpeed":advance/count}
def evaluate(rows):
    if set(rows)!={"reference","close"}:raise ValueError("Both modes required")
    a,b=rows["reference"],rows["close"]
    for mode,row in rows.items():
        if not all((integrated.mode_ok(row,True),integrated.stats_ok(row),integrated.resource_ok(row))):
            raise ValueError("Invalid evidence")
        if row.get("closeTouch") is not (mode=="close") or any(row.get(k) is not False for k in
          ("determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact","lineBreak","runLanes","triangle","creativeCarry","duel","holdUp","finish","keeperAI","defenseShape","transition","roleProfile")):
            raise ValueError("Policy not isolated")
        p=row["closeTouchProbe"]
        if not all(integrated.metric_pair(p[k]) for k in ("contacts","adjusted")):raise ValueError("Invalid counters")
        for n,c,x,y in zip(p["contacts"],p["adjusted"],p["before"],p["after"]):
            if not math.isfinite(x+y) or not 0<=c<=n or not 0<=y<=x+.00001 or y<x*.72-.00001:
                raise ValueError("Invalid contact energy proxy")
            if mode=="reference" and (c or abs(x-y)>.00001):raise ValueError("Reference changed")
    def accuracy(m):return sum(m["completed"])/max(1,sum(m["passes"]))
    m,n=a["gameplay"],b["gameplay"]
    return {"delivery":all(integrated.wall_ok(x) for x in rows.values()),
        "adjusted":sum(b["closeTouchProbe"]["adjusted"]),"reference":a["motion"],"candidate":b["motion"],
        "shotsDelta":sum(n["shots"])-sum(m["shots"]),"onTargetDelta":sum(n["onTarget"])-sum(m["onTarget"]),
        "boxDelta":sum(n["controlledBoxCrossings"])-sum(m["controlledBoxCrossings"]),
        "accuracyDelta":accuracy(n)-accuracy(m)}
def aggregate(rows):
    if set(rows)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    values=list(rows.values())
    def far(mode):return sum(r[mode]["far"] for r in values)/sum(r[mode]["samples"] for r in values)
    checks={"delivery":all(r["delivery"] for r in values),"actualContactAdjusted":all(r["adjusted"]>0 for r in values),
        "excessGapReduced":far("candidate")<far("reference"),
        "gapNotIncreased":sum(r["candidate"]["meanGap"]-r["reference"]["meanGap"] for r in values)<=0,
        "forwardSpeedProtected":all(r["candidate"]["forwardSpeed"]>=r["reference"]["forwardSpeed"]-.5 for r in values),
        "attackProtected":all(sum(r[k] for r in values)>=0 for k in ("shotsDelta","onTargetDelta","boxDelta")),
        "passAccuracyProtected":all(r["accuracyDelta"]>=-.08 for r in values)}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"referenceFarShare":far("reference"),"candidateFarShare":far("candidate")}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    frozen=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"productionEnabled":False,"authoritative":False,"status":"incomplete","identity":frozen,
      "scenarios":{},"completedRuns":[],"note":"Actual low-ball controlled contact only. Separation samples are conditional on unique possession and may miss lost control; no foot-bone trajectory or visual animation validation. Single pair per scenario, no promotion."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=frozen:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"close-touch.json",stamp(report,a.runtime,"close-touch"))
    checkpoint()
    for idx,scenario in enumerate(SCENARIOS):
        rows={}
        for mode in (("reference","close") if idx%2==0 else ("close","reference")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,close_touch=mode=="close")
            trace=Path(str(prefix)+".candidate.ndjson")
            row["motion"]=motion(trace);rows[mode]=row
            report["completedRuns"].append({"scenario":scenario,"mode":mode,"match":row,
                "traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest()});checkpoint()
        report["scenarios"][scenario]=evaluate(rows);checkpoint()
    report["aggregate"]=aggregate(report["scenarios"])
    report["status"]="manual-review-required" if report["aggregate"]["diagnosticPassed"] else "blocked"
    checkpoint();print(json.dumps({"status":report["status"],"aggregate":report["aggregate"],"scenarios":report["scenarios"]}),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
