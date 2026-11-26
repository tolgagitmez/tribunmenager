"""Stage 49: compare full CPU skinning and position-only skinning in null mode."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("fixed",HERE/"fixed-duration.py")
fixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixed)

def evaluate(rows):
    if set(rows)!={"full","position-only"}: raise ValueError("Require both modes")
    a,b=rows["full"],rows["position-only"]
    for row,mode in ((a,False),(b,True)):
        if (row.get("noDraw") is not True or row.get("noUpload") is not True or row.get("nullRenderer") is not True or row.get("leanScene") is not False or row.get("visualRng") is not False or row.get("skipPitchTexture") is not False or row.get("requestedTaskWorkers")!=0 or row.get("positionSkinning") is not mode or row.get("sharedAssets") is not False or row.get("configuredRenderIntervalMs")!=100
            or row.get("softwareRenderThreads")!=2 or row.get("exactNativeDuration") is not True
            or row.get("nativeElapsedMs")!=300000 or row.get("attackProfile")!="short-match"
            or any(row.get(k) for k in ("retention","boxRuns","timedAttack","quickRestarts"))):
            raise ValueError("Invalid isolated experiment")
    if a["hardwareThreads"]!=b["hardwareThreads"] or a["taskWorkerPool"]!=max(3,a["hardwareThreads"]) or b["taskWorkerPool"]!=a["taskWorkerPool"]:
        raise ValueError("Invalid worker pool evidence")
    def cpu(row):
        return row["resources"]["userSeconds"]+row["resources"]["systemSeconds"]
    fields=("score","shots","onTarget","controlledBoxCrossings")
    return {"schema":1,"authoritative":False,"productionEnabled":False,
            "nullContextObserved":True,"contextFree":False,
            "peakNativeThreadDelta":b["nativeMemory"]["peakNativeThreads"]-a["nativeMemory"]["peakNativeThreads"],"matches":rows,"cpuSecondsDelta":cpu(b)-cpu(a),
            "rssDeltaKiB":b["resources"]["maxRssKiB"]-a["resources"]["maxRssKiB"],
            "peakPssDeltaKiB":b["nativeMemory"]["peakPssKiB"]-a["nativeMemory"]["peakPssKiB"],
            "startupDeltaMs":b["launchToKickoffMs"]-a["launchToKickoffMs"],
            "wallDeltaMs":b["observedWallMs"]-a["observedWallMs"],
            "maxGapDeltaMs":b["maxObservedGapMs"]-a["maxObservedGapMs"],
            "observedGameplayEqual":all(a[k]==b[k] for k in fields),
            "note":"Only runtime normal/tangent/bitangent skinning changes. Bind-pose and vertex positions, skeleton, collision geometry, replay and AI are retained. One pair is not proof of gameplay parity."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime");p.add_argument("fixture");p.add_argument("out")
    a=p.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    paths=[Path(a.runtime)/"gameplayfootball",Path(a.runtime)/"tribun-runtime.json",Path(a.fixture)]
    identity=lambda:[hashlib.sha256(x.read_bytes()).hexdigest() for x in paths]
    pinned=identity()
    rows={}
    for name,mode in (("full",False),("position-only",True)):
        if identity()!=pinned:raise ValueError("Inputs changed")
        prefix=str(out/"stage49")
        row=fixed.timing.run(a.runtime,a.fixture,prefix,(name,"1.0","0"),"short-match",True,
                             render_threads=2,render_interval_ms=100,no_draw=True,no_upload=True,null_renderer=True,sample_pss=True,position_skinning=mode)
        with Path(prefix+"."+name+".ndjson").open() as f:
            row={**row,**fixed.verify(json.loads(line) for line in f)}
        if identity()!=pinned:raise ValueError("Inputs changed during match")
        rows[name]=row
        (out/(name+".json")).write_text(json.dumps(row,indent=2,allow_nan=False)+"\n")
    result={**evaluate(rows),"identity":dict(zip(("binarySha256","manifestSha256","fixtureSha256"),pinned))}
    (out/"position-skinning-comparison.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result),flush=True)
if __name__=="__main__":main()
