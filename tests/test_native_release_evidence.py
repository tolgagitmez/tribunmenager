import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("release",Path(__file__).resolve().parents[1]/"integrations/league-soccer/release_evidence.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReleaseEvidenceTest(unittest.TestCase):
    def test_missing_and_old_evidence_blocked(self):
        r=m.evaluate({},expected="a"*64)
        self.assertEqual(r["status"],"blocked")
        self.assertFalse(r["productionEnabled"])
        old={"authoritative":False,"evidence":{"schema":1,"kind":"fixed-duration","candidateSha256":"b"*64,"runtimeManifestSha256":"c"*64,"runtimeBinarySha256":"d"*64}}
        self.assertFalse(m.evaluate({"fixed-duration":old},expected="a"*64)["checks"]["fixed-durationVersionBound"])
    def test_all_evidence_still_only_manual_review(self):
        duration=dict(exactNativeDuration=True,nativeElapsedMs=300000,halfMs=150000,observedWallMs=300000)
        def wrap(kind,r):
            return {**r,"authoritative":False,"evidence":dict(schema=1,kind=kind,candidateSha256="a"*64,runtimeManifestSha256="c"*64,runtimeBinarySha256="d"*64)}
        readiness=dict(status="expanded-validation-eligible",calibrationMode="fixed-duration",checks={k:True for k in ("sampleSize","candidateShotVolume","candidateBoxEntries","calibratedShotVolume","calibratedBoxEntries","calibratedDuration","observedCombination","observedReboundShot")})
        combined={**duration,"substitutions":[dict(team=t,performed=True) for t in (0,1)],"acknowledgements":[dict(team=t,revision=r) for t,r in ((0,1),(1,1),(0,2))]}
        group=dict(concurrency=1,diagnosticPassed=True,checks={k:True for k in ("allMatchesValidated","actualOverlap","exactNativeTicks","wallWithinOneSecond","observedTraceGapBelowOneSecond","resourceMeasurements")},matches=[{**duration,"ok":True}])
        reports={k:wrap(k,r) for k,r in (("readiness",readiness),("fixed-duration",duration),("combined-controls",combined),("capacity",dict(groups=[group])))}
        result=m.evaluate(reports,expected="a"*64,required_capacity=1)
        self.assertEqual(result["status"],"manual-review-required")
        self.assertFalse(result["productionEnabled"])
        self.assertEqual(m.evaluate(reports,expected="a"*64)["status"],"blocked")
        reports["fixed-duration"]["observedWallMs"]=300001
        self.assertFalse(m.evaluate(reports,expected="a"*64,required_capacity=1)["checks"]["fixedDurationExact"])
        reports["readiness"]["calibrationMode"]="scale-1.10"
        self.assertFalse(m.evaluate(reports,expected="a"*64,required_capacity=1)["checks"]["fixedClockAttackProfile"])
