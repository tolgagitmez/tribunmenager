"""Stage 99: single-runtime release-quality matrix. No production activation."""
import argparse
import importlib.util
import json
import subprocess
from pathlib import Path
from release_evidence import stamp, fingerprint, sha
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
I=load("integrated-profile")
POLICIES={"keeper":("keeper_ai",load("keeper-ai-benchmark")),
          "collective":("collective_ai",load("collective-ai-benchmark")),
          "pace":("match_pace",load("match-pace-benchmark"))}
SCENARIOS=("balanced","counter-possession","possession-counter")
MODES=("reference",*POLICIES)
AUDITS=("animation-blend","motion-matching","motion-identity","anatomy","contact-precision","ground-recovery","keeper-completion")
def evaluate(report,runtime,fixtures):
    expected=stamp({},runtime,"release-quality")["evidence"]
    checks={"versionBound":report.get("evidence")==expected,
            "sameFrozenInputs":report.get("identity")==I.capacity.fingerprint(runtime,fixtures),
            "diagnosticOnly":report.get("authoritative") is False and report.get("productionEnabled") is False}
    runs=report.get("completedRuns",[])
    pairs={(s,m) for s in SCENARIOS for m in MODES}
    seen={(r.get("scenario"),r.get("mode")) for r in runs}
    checks["fullMatrix"]=len(runs)==len(pairs) and seen==pairs
    checks["traceHashes"]=checks["fullMatrix"] and all(
        isinstance(r.get("traceSha256"),str) and len(r["traceSha256"])==64 and
        all(c in "0123456789abcdef" for c in r["traceSha256"]) for r in runs)
    checks["fixedDuration"]=checks["fullMatrix"] and all(
        I.mode_ok(r.get("match",{}),True) and I.stats_ok(r["match"]) and I.resource_ok(r["match"]) and I.wall_ok(r["match"]) for r in runs)
    for name,(_,m) in POLICIES.items():
        try:
            rows={}
            for s in SCENARIOS:
                pair={r["mode"]:r["match"] for r in runs if r.get("scenario")==s and r.get("mode") in ("reference",name)}
                rows[s]=m.evaluate(pair)
            result=m.aggregate(rows)
            checks[name+"Qualified"]=result["diagnosticPassed"] is True
            checks[name+"Consistent"]=report.get("policies",{}).get(name)=={"scenarios":rows,"aggregate":result}
        except (KeyError,ValueError,TypeError,ZeroDivisionError):
            checks[name+"Qualified"]=False;checks[name+"Consistent"]=False
    visual=report.get("visual",{})
    checks["visualAuditsExecuted"]=set(visual)==set(AUDITS) and all(
        isinstance(v,dict) and v.get("authoritative") is False for v in visual.values())
    contact=visual.get("contact-precision",{}).get("metrics",{})
    def coverage(kind):
        v=contact.get(kind,{})
        return type(v.get("samples")) is int and v["samples"]>0 and isinstance(v.get("baselineMeanCm"),(float,int)) and isinstance(v.get("candidateMeanCm"),(float,int)) and 0<=v["candidateMeanCm"]<=v["baselineMeanCm"]+1e-7
    # A missing event is inconclusive, never a passing quality result.
    checks["footContactCoverage"]=coverage("foot")
    checks["palmContactCoverage"]=coverage("palm")
    checks["headContactCoverage"]=coverage("head")
    ground=visual.get("ground-recovery",{})
    checks["groundRecoveryCoverage"]=type(ground.get("groundSamples")) is int and ground["groundSamples"]>0
    keep=visual.get("keeper-completion",{})
    checks["keeperDiveCoverage"]=type(keep.get("eligible")) is int and keep["eligible"]>0 and type(keep.get("palms")) is int and keep["palms"]>0
    checks["webglActualTrace"]=report.get("webgl",{}).get("passed") is True and report.get("webgl",{}).get("traceSha256")==report.get("visualTraceSha256") and isinstance(report.get("visualTraceSha256"),str)
    return {"checks":checks,"diagnosticPassed":all(checks.values()),"status":"manual-review-required" if all(checks.values()) else "blocked",
        "productionEnabled":False,"combinedQualified":False,
        "remaining":["Combined-policy qualification","Full live controls, season transaction and restart recovery","Concurrent host capacity","Real-device FPS and visual inspection","Asset provenance review"]}
def main():
    p=argparse.ArgumentParser();p.add_argument("runtime",type=Path);p.add_argument("fixtures",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    identity=I.capacity.fingerprint(a.runtime,a.fixtures)
    report=stamp({"schema":1,"authoritative":False,"productionEnabled":False,"combinedQualified":False,
        "identity":identity,"status":"incomplete","completedRuns":[],"policies":{},"visual":{},
        "note":"Twelve matches: one reference and three separately activated policies per fixture. A shared reference reduces cost but does not replace repeated or combined-policy experiments."},a.runtime,"release-quality")
    def checkpoint():
        if I.capacity.fingerprint(a.runtime,a.fixtures)!=identity or fingerprint()!=report["evidence"]["candidateSha256"]:raise ValueError("Frozen inputs changed")
        I.save(a.out/"release-quality.json",report)
    checkpoint()
    allrows={}
    for i,s in enumerate(SCENARIOS):
        rows={}
        # Rotate order to avoid always running the reference first.
        modes=MODES[i:]+MODES[:i]
        for mode in modes:
            prefix=a.out/f"{s}-{mode}"
            flags={} if mode=="reference" else {POLICIES[mode][0]:True}
            row=I.run(a.runtime,a.fixtures/(s+".json"),prefix,True,**flags)
            trace=Path(str(prefix)+".candidate.ndjson")
            rows[mode]=row
            report["completedRuns"].append({"scenario":s,"mode":mode,"match":row,"traceSha256":sha(trace)})
            checkpoint()
        allrows[s]=rows
    for name,(_,m) in POLICIES.items():
        try:
            rows={s:m.evaluate({"reference":allrows[s]["reference"],name:allrows[s][name]}) for s in SCENARIOS}
            report["policies"][name]={"scenarios":rows,"aggregate":m.aggregate(rows)}
        except (KeyError,ValueError,TypeError,ZeroDivisionError) as e:
            report["policies"][name]={"error":str(e)}
        checkpoint()
    trace=a.out/"balanced-reference.candidate.ndjson"
    report["visualTraceSha256"]=sha(trace)
    for audit in AUDITS:
        try:
            result=subprocess.run(["node",str(HERE/(audit+"-audit.cjs")),str(trace)],cwd=ROOT,capture_output=True,text=True,check=True,timeout=180)
            report["visual"][audit]=json.loads(result.stdout)
        except (subprocess.SubprocessError,ValueError) as e:
            report["visual"][audit]={"error":str(e)}
        checkpoint()
    # The browser smoke exercises a real recording and actual GLB, not only synthetic frames.
    try:
        subprocess.run(["node",str(HERE/"replay-browser.cjs"),str(trace)],cwd=ROOT,check=True,timeout=240)
        report["webgl"]={"passed":True,"traceSha256":sha(trace)}
    except subprocess.SubprocessError as e:
        report["webgl"]={"passed":False,"error":str(e)}
    report["gate"]=evaluate(report,a.runtime,a.fixtures);report["status"]=report["gate"]["status"];checkpoint()
    print(json.dumps(report["gate"],indent=2),flush=True)
    if report["status"]=="blocked":raise SystemExit(2)
if __name__=="__main__":main()
