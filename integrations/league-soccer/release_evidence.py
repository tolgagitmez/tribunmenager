"""Version-bound diagnostic evidence, never permission to activate the engine."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
# Include native build inputs, runner, match reports and the live publication/season path.
FILES=(
 "integrations/league-soccer/upstream.json",
 "integrations/league-soccer/instrument.py",
 "integrations/league-soccer/fixture_patch.py",
 "integrations/league-soccer/short_match_patch.py",
 "integrations/league-soccer/run-pilot.sh",
 "integrations/league-soccer/run-frozen.sh",
 "integrations/league-soccer/fixture-adapter.cjs",
 "integrations/league-soccer/attack-report.cjs",
 "integrations/league-soccer/timing-benchmark.py",
 "integrations/league-soccer/fixed-duration.py",
 "integrations/league-soccer/manager-control-smoke.py",
 "integrations/league-soccer/readiness.py",
 "integrations/league-soccer/readiness-fixtures.cjs",
 "integrations/league-soccer/capacity-benchmark.py",
 "integrations/league-soccer/null-capacity.py",
 "integrations/league-soccer/integrated-profile.py",
 "integrations/league-soccer/profile-repeatability.py",
 "integrations/league-soccer/ordered-pose-benchmark.py",
 "integrations/league-soccer/collision-pose-benchmark.py",
 "integrations/league-soccer/contact-cadence-benchmark.py",
 "integrations/league-soccer/adaptive-contact-benchmark.py",
 "integrations/league-soccer/surface-impact-benchmark.py",
 "integrations/league-soccer/angular-impact-benchmark.py",
 "integrations/league-soccer/swept-impact-benchmark.py",
 "integrations/league-soccer/split-impact-benchmark.py",
 "integrations/league-soccer/chain-impact-benchmark.py",
 "integrations/league-soccer/limb-impact-benchmark.py",
 "integrations/league-soccer/line-break-benchmark.py",
 "integrations/league-soccer/run-lanes-benchmark.py",
 "integrations/league-soccer/triangle-benchmark.py",
 "integrations/league-soccer/creative-carry-benchmark.py",
 "integrations/league-soccer/duel-benchmark.py",
 "integrations/league-soccer/hold-up-benchmark.py",
 "integrations/league-soccer/finish-benchmark.py",
 "integrations/league-soccer/keeper-ai-benchmark.py",
 "integrations/league-soccer/position-skinning-benchmark.py",
 "integrations/league-soccer/runtime-layout.py",
 "integrations/league-soccer/verify-substitutions.py",
 "integrations/league-soccer/validate_trace.py",
 "integrations/league-soccer/validate_fixture_trace.py",
 "integrations/league-soccer/release_evidence.py",
 "native_shadow.py","native_live.py","native_season.py","live_match.py",
 "season_state.py","server.py","football-sim.js","player-model.js","tactics.js",
 "integrations/league-soccer/native-stream-ui.js","integrations/league-soccer/native-stream-view.js",
 "integrations/league-soccer/native-replay.js","scene3d.js",
)
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def fingerprint(root=ROOT):
    root=Path(root)
    files={name:sha(root/name) for name in FILES}
    return hashlib.sha256(json.dumps(files,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def stamp(report,runtime,kind):
    manifest=Path(runtime)/"tribun-runtime.json"
    executable=Path(runtime)/"gameplayfootball"
    return {**report,"evidence":{"schema":1,"kind":kind,"candidateSha256":fingerprint(),
            "runtimeManifestSha256":sha(manifest),"runtimeBinarySha256":sha(executable)}}

def evaluate(reports,expected=None,required_capacity=3):
    """Report missing/failed evidence. Deliberately no production-ready result."""
    if required_capacity not in (1,2,3):raise ValueError("Invalid required capacity")
    expected=expected or fingerprint()
    checks={}
    manifests=set()
    accepted={}
    for kind in ("readiness","fixed-duration","combined-controls","capacity"):
        r=reports.get(kind)
        e=r.get("evidence",{}) if isinstance(r,dict) else {}
        valid=isinstance(r,dict) and r.get("authoritative") is False and e.get("schema")==1 and e.get("kind")==kind and e.get("candidateSha256")==expected
        valid=valid and all(isinstance(e.get(k),str) and len(e[k])==64 and all(ch in "0123456789abcdef" for ch in e[k]) for k in ("runtimeManifestSha256","runtimeBinarySha256"))
        checks[kind+"VersionBound"]=bool(valid)
        if valid:
            manifests.add(e["runtimeManifestSha256"])
            accepted[kind]=r
    checks["sameRuntimeManifest"]=len(accepted)==4 and len(manifests)==1
    r=accepted.get("readiness",{})
    expected_checks=("sampleSize","candidateShotVolume","candidateBoxEntries","calibratedShotVolume","calibratedBoxEntries","calibratedDuration","observedCombination","observedReboundShot")
    checks["attackReadiness"]=r.get("status")=="expanded-validation-eligible" and all(r.get("checks",{}).get(k) is True for k in expected_checks)
    # The old 1.10 clock profile cannot count as fixed-clock attack evidence.
    checks["fixedClockAttackProfile"]=r.get("calibrationMode")=="fixed-duration"
    def duration_ok(x):
        return x.get("exactNativeDuration") is True and x.get("nativeElapsedMs")==300000 and x.get("halfMs")==150000 and x.get("observedWallMs")==300000
    checks["fixedDurationExact"]=duration_ok(accepted.get("fixed-duration",{}))
    r=accepted.get("combined-controls",{})
    changes=r.get("substitutions",[])
    acks=r.get("acknowledgements",[])
    checks["combinedControls"]=duration_ok(r) and len(changes)==2 and {c.get("team") for c in changes}=={0,1} and all(c.get("performed") is True for c in changes) and len(acks)==3 and {(a.get("team"),a.get("revision")) for a in acks}=={(0,1),(1,1),(0,2)}
    groups=accepted.get("capacity",{}).get("groups",[])
    group_checks=("allMatchesValidated","actualOverlap","exactNativeTicks","wallWithinOneSecond","observedTraceGapBelowOneSecond","resourceMeasurements")
    checks["capacity"]=all(any(g.get("concurrency")==n and g.get("diagnosticPassed") is True and all(g.get("checks",{}).get(k) is True for k in group_checks) and len(g.get("matches",[]))==n and all(x.get("ok") is True and duration_ok(x) for x in g["matches"]) for g in groups) for n in range(1,required_capacity+1))
    return {"schema":1,"authoritative":False,"candidateSha256":expected,"checks":checks,
            "status":"manual-review-required" if all(checks.values()) else "blocked",
            "productionEnabled":False,
            "remainingManualChecks":["deadline foul/penalty policy","HTTP permissions and live commands","crash recovery and authoritative season transaction","asset license audit","target-host/device performance"],
            "note":"Local diagnostic files are not signed CI attestations. Binary hashes are recorded, not required to match across separate builds. No engine switch or database write."}

def main():
    import argparse
    p=argparse.ArgumentParser()
    for kind in ("readiness","fixed-duration","combined-controls","capacity"):
        p.add_argument("--"+kind,type=Path)
    p.add_argument("--required-capacity",type=int,default=3)
    a=p.parse_args()
    reports={k:json.loads(v.read_text()) for k in ("readiness","fixed-duration","combined-controls","capacity") if (v:=getattr(a,k.replace("-","_"))) is not None}
    report=evaluate(reports,required_capacity=a.required_capacity)
    print(json.dumps(report,indent=2))
    if report["status"]=="blocked":raise SystemExit(2)

if __name__=="__main__":main()
