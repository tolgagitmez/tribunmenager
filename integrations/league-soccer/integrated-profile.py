"""Stage 50: staged integrated native profile evidence; never enables production."""
import argparse
import json
import math
import os
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
capacity=load("null-capacity")
fixed=capacity.fixed
SCENARIOS=("balanced","counter-possession")
METRICS=("score","shots","onTarget","passes","completed","fouls","cards","reds","controlledBoxCrossings")
COMMON=dict(render_threads=1,render_interval_ms=100,no_draw=True,no_upload=True,
            null_renderer=True,sample_pss=True)
CANDIDATE=dict(lean_scene=True,visual_rng=True,skip_pitch=True,task_workers=3,position_skinning=True)
def mode_ok(row,candidate):
    return (row.get("nullRenderer") is True and row.get("noDraw") is True and row.get("noUpload") is True
            and row.get("sharedAssets") is False and row.get("configuredRenderIntervalMs")==100
            and row.get("softwareRenderThreads")==1 and row.get("attackProfile")=="short-match"
            and row.get("exactNativeDuration") is True and row.get("nativeElapsedMs")==300000
            and row.get("halfMs")==150000 and row.get("scale")==1.0
            and all(row.get(k) is False for k in ("retention","boxRuns","timedAttack","quickRestarts"))
            and all(row.get(k) is candidate for k in ("leanScene","visualRng","skipPitchTexture","positionSkinning"))
            and row.get("requestedTaskWorkers")== (3 if candidate else 0)
            and type(row.get("hardwareThreads")) is int
            and row.get("taskWorkerPool")== (3 if candidate else max(3,row["hardwareThreads"])))
def metric_pair(v):
    return isinstance(v,list) and len(v)==2 and all(type(x) is int and x>=0 for x in v)
def stats_ok(row):
    m=row.get("gameplay",{})
    return (all(metric_pair(m.get(k)) for k in METRICS)
            and all(a<=b for a,b in zip(m["completed"],m["passes"]))
            and all(a<=b for a,b in zip(m["onTarget"],m["shots"])))
def resource_ok(row):
    resources=row.get("resources") or {};memory=row.get("nativeMemory") or {}
    return (all(type(resources.get(k)) in (int,float) and math.isfinite(resources[k]) and resources[k]>=0
            for k in ("userSeconds","systemSeconds","maxRssKiB"))
            and all(type(memory.get(k)) is int and memory[k]>0 for k in ("peakPssKiB","peakNativeThreads","sampleCount")))
def wall_ok(row):
    return abs(row["observedWallMs"]-300000)<=1000 and row["maxObservedGapMs"]<=1000
def cpu(row):
    return row["resources"]["userSeconds"]+row["resources"]["systemSeconds"]
def evaluate_pair(reference,candidate):
    if not mode_ok(reference,False) or not mode_ok(candidate,True):
        raise ValueError("Integrated profile evidence mismatch")
    if reference["hardwareThreads"]!=candidate["hardwareThreads"]:
        raise ValueError("Host changed within comparison")
    if not all(stats_ok(r) and resource_ok(r) for r in (reference,candidate)):
        raise ValueError("Invalid gameplay or resource evidence")
    return {"candidateDeliveryPassed":wall_ok(candidate),"referenceDeliveryPassed":wall_ok(reference),
            "cpuSecondsDelta":cpu(candidate)-cpu(reference),
            "peakPssDeltaKiB":candidate["nativeMemory"]["peakPssKiB"]-reference["nativeMemory"]["peakPssKiB"],
            "startupDeltaMs":candidate["launchToKickoffMs"]-reference["launchToKickoffMs"],
            "peakNativeThreadDelta":candidate["nativeMemory"]["peakNativeThreads"]-reference["nativeMemory"]["peakNativeThreads"],
            "gameplayDelta":{k:[b-a for a,b in zip(reference["gameplay"][k],candidate["gameplay"][k])] for k in METRICS},
            "observedGameplayEqual":reference["gameplay"]==candidate["gameplay"]}
def read_gameplay(trace):
    attack=json.loads(Path(str(trace)+".attack.json").read_text())
    season=json.loads(Path(str(trace)+".season.json").read_text())
    if attack["score"]!=season["score"] or season.get("authoritative") is not False:
        raise ValueError("Mismatched season evidence")
    return {**{k:attack[k] for k in ("score","shots","onTarget","passes","completed","fouls")},
            "cards":season["cards"],"reds":season["reds"],"controlledBoxCrossings":attack["sampled"]["controlledBoxCrossings"]}
def run(runtime,fixture,prefix,candidate,determinism_probe=False,ordered_pose=False,collision_pose=False,contact_interval_ms=100,adaptive_contact=False,surface_impact=False,angular_impact=False,swept_impact=False,split_impact=False,chain_impact=False,limb_impact=False,line_break=False,run_lanes=False,triangle=False,creative_carry=False,duel=False,hold_up=False,finish=False,keeper_ai=False,defense_shape=False,transition=False,role_profile=False,close_touch=False,motion_smooth=False,collective_ai=False):
    name="candidate" if candidate else "reference"
    row=fixed.timing.run(str(runtime),str(fixture),str(prefix),(name,"1.0","0"),"short-match",True,
                         determinism_probe=determinism_probe,ordered_pose=ordered_pose,collision_pose=collision_pose,contact_interval_ms=contact_interval_ms,adaptive_contact=adaptive_contact,surface_impact=surface_impact,angular_impact=angular_impact,swept_impact=swept_impact,split_impact=split_impact,chain_impact=chain_impact,limb_impact=limb_impact,line_break=line_break,run_lanes=run_lanes,triangle=triangle,creative_carry=creative_carry,duel=duel,hold_up=hold_up,finish=finish,keeper_ai=keeper_ai,defense_shape=defense_shape,transition=transition,role_profile=role_profile,close_touch=close_touch,motion_smooth=motion_smooth,collective_ai=collective_ai,**COMMON,**(CANDIDATE if candidate else {}))
    trace=Path(str(prefix)+"."+name+".ndjson")
    with trace.open() as f:row.update(fixed.verify(json.loads(line) for line in f))
    row["gameplay"]=read_gameplay(trace)
    if not mode_ok(row,candidate) or not resource_ok(row) or not stats_ok(row):
        raise ValueError("Invalid integrated match")
    return row
def save(path,data):
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(data,indent=2,allow_nan=False)+"\n")
    os.replace(temp,path)
def group_gate(group):
    rows=group["matches"]
    return (group["diagnosticPassed"] is True and all(mode_ok(r,True) and resource_ok(r) and stats_ok(r) for r in rows))
def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    identity=capacity.fingerprint(a.runtime,a.fixtures)
    report={"schema":1,"authoritative":False,"productionEnabled":False,
            "profile":"integrated-experimental-null","identity":identity,
            "reference":"full scene null renderer; no drawing/uploads, no other optimizations",
            "sharedAssetsIncluded":False,"pairs":{},"groups":[],"largestPassingGroup":0,
            "note":"Two fixture comparisons are descriptive; no deterministic parity or production approval. Shared-assets mode remains separate. Individual PSS peaks are not aggregate host RAM."}
    target=a.out/"integrated-profile.json"
    def checkpoint():
        if capacity.fingerprint(a.runtime,a.fixtures)!=identity:raise ValueError("Frozen inputs changed")
        save(target,report)
    checkpoint()
    for scenario in SCENARIOS:
        item=report["pairs"][scenario]={}
        for mode in (False,True):
            name="candidate" if mode else "reference"
            item[name]=run(a.runtime,a.fixtures/(scenario+".json"),a.out/(scenario+"-"+name),mode)
            checkpoint()
        item["comparison"]=evaluate_pair(item["reference"],item["candidate"])
        checkpoint()
        if not item["comparison"]["candidateDeliveryPassed"]:
            raise SystemExit("Integrated candidate missed delivery gate; capacity test blocked")
    report["largestPassingGroup"]=1
    checkpoint()
    for n in (2,4):
        def worker(index,scenario):
            return run(a.runtime,a.fixtures/(scenario+".json"),a.out/f"n{n}-{index:02d}-{scenario}",True)
        group=capacity.run_group(a.runtime,a.fixtures,a.out,n,runner=worker)
        group["integratedProfilePassed"]=group_gate(group)
        report["groups"].append(group)
        if group["integratedProfilePassed"]:report["largestPassingGroup"]=n
        checkpoint()
        if not group["integratedProfilePassed"]:raise SystemExit("Integrated capacity gate failed")
    print(json.dumps({"largestPassingGroup":report["largestPassingGroup"],"productionEnabled":False}),flush=True)
if __name__=="__main__":main()
