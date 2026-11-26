"""Stage 76: mirrored attribute contrasts and actual native attribute delivery.
Synthetic team-wide interventions. Match outcomes remain noisy, not individual skill causality."""
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
AXES={
    "dribbling":("technical_dribble","technical_ballcontrol","physical_balance","physical_agility"),
    "passing":("technical_shortpass","technical_highpass"),
    "shooting":("technical_shot","technical_volley","physical_shotpower"),
    "pace":("physical_velocity","physical_acceleration"),
    "decisions":("mental_vision","mental_calmness","mental_resilience")}
ATTRS={k for keys in AXES.values() for k in keys}
def identity(runtime,fixtures):
    paths=[runtime/"gameplayfootball",runtime/"tribun-runtime.json",runtime/"native-match.config",
           *(fixtures/(f"{axis}-{side}.json") for axis in AXES for side in range(2))]
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
def verify_attributes(frame,manifest,axis,high_team):
    expected={(t["team"],p["nativeId"]):p for t in manifest["teams"] for p in t["players"]}
    players=frame["players"]
    actual={(p["team"],p["databaseId"]):p for p in players}
    if len(players)!=22 or set(actual)!=set(expected):
        raise ValueError("Kickoff player identity mismatch")
    counts=[0,0]
    for key,p in actual.items():
        native=p.get("nativeAttributes",{})
        if set(native)!=ATTRS:raise ValueError("Missing runtime attributes")
        exp=expected[key]
        for name,value in native.items():
            if type(value) not in (int,float) or not math.isfinite(value) or abs(value-exp["stats"][name])>0.0002:
                raise ValueError("Native attribute mismatch "+str(key)+" "+name)
        if not p["goalkeeper"]:
            target=.9 if key[0]==high_team else .55
            if any(abs(native[k]-target)>0.0002 for k in AXES[axis]):
                raise ValueError("Intended attribute contrast did not reach engine")
            counts[key[0]]+=1
    if counts!=[10,10]:raise ValueError("Invalid outfield coverage")
    return counts
def read_trace(trace,axis,high_team):
    manifest=json.loads(Path(str(trace)+".fixture.json").read_text())
    verified=None;frames=0
    speed_sum=[0.0,0.0];speed_count=[0,0];sprints=[0,0]
    controlled=[0,0];forward=[0.0,0.0]
    for line in trace.open():
        frame=json.loads(line)
        clock=frame["fixedClock"]
        if not clock["started"]:continue
        if clock["elapsedMs"]==0:
            if verified is not None:raise ValueError("Duplicate kickoff")
            verified=verify_attributes(frame,manifest,axis,high_team)
        if not frame["inPlay"] or frame["setPiece"]:continue
        frames+=1
        for p in frame["players"]:
            if p["goalkeeper"]:continue
            t=p["team"];vx,vy,*_=p["velocity"];speed=math.hypot(vx,vy)
            if not math.isfinite(speed):raise ValueError("Invalid speed sample")
            speed_sum[t]+=speed;speed_count[t]+=1;sprints[t]+=int(speed>=6)
            if p["uniquePossession"]:
                controlled[t]+=1
                forward[t]+=vx*frame["attackDirection"][t]
    if verified is None or min(speed_count)<=0 or min(controlled)<=0:
        raise ValueError("Missing kickoff or motion/control observations")
    return {"verifiedOutfield":verified,"openPlayFrames":frames,
        "meanSpeed":[speed_sum[t]/speed_count[t] for t in range(2)],
        "sprintShare":[sprints[t]/speed_count[t] for t in range(2)],
        "controlledForwardSpeed":[forward[t]/controlled[t] for t in range(2)],
        "controlSamples":controlled}
def rates(row):
    m=row["gameplay"]
    return {"passAccuracy":[m["completed"][t]/max(1,m["passes"][t]) for t in range(2)],
        "shotAccuracy":[m["onTarget"][t]/max(1,m["shots"][t]) for t in range(2)],
        "goals":m["score"],"shots":m["shots"],"passes":m["passes"],
        "boxEntries":m["controlledBoxCrossings"],
        **{k:row["movement"][k] for k in ("meanSpeed","sprintShare","controlledForwardSpeed","controlSamples")}}
def compare(axis,legs):
    if set(legs)!={0,1}:raise ValueError("Both mirrored sides required")
    deltas={};per_leg=[]
    for side,row in sorted(legs.items()):
        if row.get("creativeCarry") is not (axis=="dribbling") or not integrated.wall_ok(row):
            raise ValueError("Wrong policy or clock")
        if row["movement"]["verifiedOutfield"]!=[10,10]:raise ValueError("Unverified native attributes")
        values=rates(row)
        delta={k:v[side]-v[1-side] for k,v in values.items()}
        per_leg.append(delta)
        for key,value in delta.items():deltas[key]=deltas.get(key,0)+value/2
    if axis=="dribbling":
        attempts=sum(row["carryProbe"]["technical"][side] for side,row in legs.items())
        low_attempts=sum(row["carryProbe"]["technical"][1-side] for side,row in legs.items())
        exposure=attempts>0 and low_attempts==0
    else:
        attempts=low_attempts=None
        exposure=True
    metrics={"dribbling":"controlledForwardSpeed","passing":"passAccuracy","shooting":"shotAccuracy",
             "pace":"meanSpeed","decisions":"passAccuracy"}
    key=metrics[axis]
    # Decision quality has no direct label: pass accuracy is an exploratory proxy only.
    opportunity=all(min(row["gameplay"]["shots" if axis=="shooting" else "passes"])>0 for row in legs.values()) if axis in ("shooting","passing","decisions") else True
    checks={"nativeAttributeDelivery":True,"delivery":True,"technicalCoverage":exposure,"opportunity":opportunity,
        "positiveMeanContrast":deltas[key]>0,"positiveBothSides":all(d[key]>0 for d in per_leg)}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"primaryMetric":key,
        "meanHighMinusLow":deltas,"perLegHighMinusLow":per_leg,
        "technicalAttemptsHigh":attempts,"technicalAttemptsLow":low_attempts}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    frozen=identity(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,"status":"incomplete",
        "identity":frozen,"scenarios":{},"completedRuns":[],
        "note":"Synthetic 90 vs 55 attribute bundles, same overall 80 and 4-4-2 lineup; one mirrored pair per axis, same seed within pair. Opposing teams differ in treatment so interference and stochastic outcomes remain. Pass accuracy is not a direct decision quality measure. Not individual duel or production proof."}
    def checkpoint():
        if identity(a.runtime,a.fixtures)!=frozen:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"attribute-contrast.json",stamp(report,a.runtime,"attribute-contrast"))
    checkpoint()
    for idx,axis in enumerate(AXES):
        legs={}
        for high in ((0,1) if idx%2==0 else (1,0)):
            prefix=a.out/f"{axis}-{high}"
            row=integrated.run(a.runtime,a.fixtures/(f"{axis}-{high}.json"),prefix,True,creative_carry=axis=="dribbling")
            trace=Path(str(prefix)+".candidate.ndjson")
            row["movement"]=read_trace(trace,axis,high)
            legs[high]=row
            report["completedRuns"].append({"axis":axis,"highTeam":high,"match":row,"traceSha256":hashlib.sha256(trace.read_bytes()).hexdigest()})
            checkpoint()
        report["scenarios"][axis]=compare(axis,legs);checkpoint()
    report["status"]="manual-review-required" if all(r["diagnosticPassed"] for r in report["scenarios"].values()) else "blocked"
    checkpoint()
    print(json.dumps({"status":report["status"],"scenarios":report["scenarios"],"productionEnabled":False}),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
