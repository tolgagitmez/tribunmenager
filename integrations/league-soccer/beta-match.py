"""Generate a private, non-authoritative native beta replay package."""
import argparse, importlib.util, json, subprocess
from pathlib import Path
from release_evidence import stamp, sha
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("combined",HERE/"combined-ai-benchmark.py")
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
I=C.I
def arguments(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("runtime",type=Path);p.add_argument("out",type=Path)
    p.add_argument("--profile",choices=("reference","combined"),default="reference")
    p.add_argument("--seed",type=int,default=2026)
    for side,formation in (("home","4-3-3"),("away","4-2-3-1")):
        p.add_argument("--"+side+"-formation",choices=("4-3-3","4-2-3-1","4-4-2","3-5-2","5-3-2","4-5-1"),default=formation)
        p.add_argument("--"+side+"-style",choices=("balanced","counter","possession"),default="balanced")
        p.add_argument("--"+side+"-press",type=int,choices=range(101),default=55)
        p.add_argument("--"+side+"-passing",choices=("mixed","short","direct"),default="mixed")
    a=p.parse_args(argv)
    if not 0<=a.seed<=0xffffffff:p.error("Seed out of range")
    return a
def options(a):
    return {"seed":a.seed,**{side+suffix.capitalize():getattr(a,side+"_"+suffix) for side in ("home","away") for suffix in ("formation","style","press","passing")}}
def main(argv=None):
    a=arguments(argv)
    runtime=a.runtime.resolve();out=a.out.resolve()
    if not (runtime/"gameplayfootball").is_file() or not (runtime/"tribun-runtime.json").is_file():
        raise ValueError("Prepare a frozen runtime first")
    out.mkdir(parents=True,exist_ok=False)
    fixture=out/"fixture.json"
    subprocess.run(["node",str(HERE/"beta-fixture.cjs"),json.dumps(options(a)),str(fixture)],check=True)
    prefix=out/"match"
    trace=Path(str(prefix)+".candidate.ndjson")
    manifest=Path(str(trace)+".fixture.json")
    report=stamp({"schema":1,"authoritative":False,"productionEnabled":False,
      "profile":a.profile,"status":"incomplete","options":options(a),
      "note":"Precomputed replay, not a live controllable match. Does not qualify or deploy the engine."},runtime,"beta-match")
    I.save(out/"beta-package.json",report)
    row=I.run(runtime,fixture,prefix,True,combined_ai=a.profile=="combined")
    C.validate(row,a.profile=="combined")
    if not I.wall_ok(row):raise ValueError("Five-minute timing gate failed")
    if not manifest.is_file():raise ValueError("Fixture manifest missing")
    report.update(status="replay-ready",files={p.name:sha(p) for p in (fixture,trace,manifest)},match=row)
    I.save(out/"beta-package.json",report)
    print("Private beta replay ready:",trace,flush=True)
if __name__=="__main__":main()
