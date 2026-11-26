"""Stage 78: sampled locomotion acceleration and fast-turn discontinuities."""
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
def motion_frames(frames):
    previous={};last=None
    samples=spikes=turns=turnSamples=0
    speedSum=0.0
    for frame in frames:
        clock=frame["fixedClock"]
        if not clock["started"] or not frame["inPlay"] or frame["setPiece"]:
            previous={};last=None;continue
        tick=clock["elapsedMs"]
        current={}
        for p in frame["players"]:
            if p["goalkeeper"]:continue
            key=(p["team"],p["databaseId"])
            v=tuple(p["velocity"][:2]);pos=tuple(p["position"][:2])
            if len(v)!=2 or len(pos)!=2 or not all(math.isfinite(a) for a in v+pos):
                raise ValueError("Invalid motion sample")
            current[key]=(v,pos)
            if key not in previous or last is None or not 80<=tick-last<=120:continue
            old,oldPos=previous[key]
            dt=(tick-last)/1000
            if math.dist(pos,oldPos)>2.0:continue
            speed=math.hypot(*v);oldSpeed=math.hypot(*old)
            samples+=1;speedSum+=speed
            spikes+=int(math.dist(v,old)/dt>14.0)
            if min(speed,oldSpeed)>=3:
                turnSamples+=1
                cosine=sum(a*b for a,b in zip(v,old))/(speed*oldSpeed)
                turns+=int(cosine<.5)
        previous=current;last=tick
    if samples<100 or turnSamples<10:raise ValueError("Insufficient continuous motion samples")
    return {"samples":samples,"spikes":spikes,"turnSamples":turnSamples,"turns":turns,"meanSpeed":speedSum/samples}
def motion(trace):
    with trace.open() as f:return motion_frames(json.loads(line) for line in f)
def evaluate(rows):
    if set(rows)!={"reference","smooth"}:raise ValueError("Both modes required")
    a,b=rows["reference"],rows["smooth"]
    for mode,row in rows.items():
        if not all((integrated.mode_ok(row,True),integrated.stats_ok(row),integrated.resource_ok(row))):
            raise ValueError("Invalid evidence")
        if row.get("motionSmooth") is not (mode=="smooth") or any(row.get(k) is not False for k in
          ("determinismProbe","orderedPose","collisionPose","adaptiveContact","surfaceImpact","angularImpact","sweptImpact","splitImpact","chainImpact","limbImpact","lineBreak","runLanes","triangle","creativeCarry","duel","holdUp","finish","keeperAI","defenseShape","transition","roleProfile","closeTouch")):
            raise ValueError("Policy not isolated")
        p=row["motionProbe"]
        if any(type(p.get(k)) is not int or p[k]<0 for k in ("planned","limited")) or p["limited"]>p["planned"]:
            raise ValueError("Invalid planned motion counters")
        if mode=="reference" and any(p.values()):raise ValueError("Reference policy active")
    if a["hardwareThreads"]!=b["hardwareThreads"]:raise ValueError("Host changed")
    def accuracy(m):return sum(m["completed"])/max(1,sum(m["passes"]))
    m,n=a["gameplay"],b["gameplay"]
    return {"delivery":all(integrated.wall_ok(x) for x in rows.values()),
        "limited":b["motionProbe"]["limited"],"planned":b["motionProbe"]["planned"],"reference":a["motion"],"candidate":b["motion"],
        "shotsDelta":sum(n["shots"])-sum(m["shots"]),"onTargetDelta":sum(n["onTarget"])-sum(m["onTarget"]),
        "boxDelta":sum(n["controlledBoxCrossings"])-sum(m["controlledBoxCrossings"]),
        "accuracyDelta":accuracy(n)-accuracy(m)}
def aggregate(rows):
    if set(rows)!=set(SCENARIOS):raise ValueError("Missing scenarios")
    values=list(rows.values())
    def rate(mode,event,denom):return sum(r[mode][event] for r in values)/sum(r[mode][denom] for r in values)
    before=rate("reference","spikes","samples");after=rate("candidate","spikes","samples")
    turnsBefore=rate("reference","turns","turnSamples");turnsAfter=rate("candidate","turns","turnSamples")
    checks={"delivery":all(r["delivery"] for r in values),"motionPlanLimited":all(r["limited"]>0 for r in values),
        "accelerationSpikesReduced":after<before,
        "fastTurnsNotIncreased":turnsAfter<=turnsBefore,
        "meanSpeedProtected":all(r["candidate"]["meanSpeed"]>=r["reference"]["meanSpeed"]*.95 for r in values),
        "attackProtected":all(sum(r[k] for r in values)>=0 for k in ("shotsDelta","onTargetDelta","boxDelta")),
        "passAccuracyProtected":all(r["accuracyDelta"]>=-.08 for r in values)}
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"referenceSpikeShare":before,"candidateSpikeShare":after,
        "referenceFastTurnShare":turnsBefore,"candidateFastTurnShare":turnsAfter}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    frozen=integrated.capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"productionEnabled":False,"authoritative":False,"status":"incomplete","identity":frozen,
      "scenarios":{},"completedRuns":[],"note":"Locomotion root-motion plans only; planned step counters include speculative animation queries, not actual executed steps. Actual velocity discontinuities sampled at approximately 100 ms, not foot-bone motion; set pieces and large position jumps excluded. No new mass, IK, animation clips or production approval."}
    def checkpoint():
        if integrated.capacity.fingerprint(a.runtime,a.fixtures)!=frozen:raise ValueError("Frozen inputs changed")
        integrated.save(a.out/"motion-smoothing.json",stamp(report,a.runtime,"motion-smoothing"))
    checkpoint()
    for idx,scenario in enumerate(SCENARIOS):
        rows={}
        for mode in (("reference","smooth") if idx%2==0 else ("smooth","reference")):
            prefix=a.out/f"{scenario}-{mode}"
            row=integrated.run(a.runtime,a.fixtures/(scenario+".json"),prefix,True,motion_smooth=mode=="smooth")
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
