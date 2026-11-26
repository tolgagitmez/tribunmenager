import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
spec=importlib.util.spec_from_file_location("integrated",ROOT/"integrated-profile.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(candidate):
    return dict(ok=True,nullRenderer=True,noDraw=True,noUpload=True,sharedAssets=False,
        configuredRenderIntervalMs=100,softwareRenderThreads=1,attackProfile="short-match",
        exactNativeDuration=True,nativeElapsedMs=300000,halfMs=150000,scale=1.0,
        retention=False,boxRuns=False,timedAttack=False,quickRestarts=False,
        leanScene=candidate,visualRng=candidate,skipPitchTexture=candidate,positionSkinning=candidate,
        requestedTaskWorkers=3 if candidate else 0,hardwareThreads=8,taskWorkerPool=3 if candidate else 8,
        observedWallMs=300100,maxObservedGapMs=200,launchToKickoffMs=8000,
        resources=dict(userSeconds=50 if candidate else 100,systemSeconds=2,maxRssKiB=500),
        nativeMemory=dict(peakPssKiB=300,peakNativeThreads=10,sampleCount=300),
        gameplay={k:[1,1] for k in m.METRICS})
class IntegratedProfileTest(unittest.TestCase):
    def test_paired_metrics(self):
        a,b=row(False),row(True)
        result=m.evaluate_pair(a,b)
        self.assertEqual(result["cpuSecondsDelta"],-50)
        self.assertTrue(result["candidateDeliveryPassed"])
        b["gameplay"]["shots"]=[2,1]
        self.assertFalse(m.evaluate_pair(a,b)["observedGameplayEqual"])
    def test_invalid_mode(self):
        b=row(True);b["positionSkinning"]=False
        with self.assertRaises(ValueError):m.evaluate_pair(row(False),b)
    def test_reject_invalid_stats(self):
        b=row(True);b["gameplay"]["completed"]=[2,1]
        with self.assertRaises(ValueError):m.evaluate_pair(row(False),b)
    def test_delivery_gate(self):
        b=row(True);b["observedWallMs"]=302000
        self.assertFalse(m.evaluate_pair(row(False),b)["candidateDeliveryPassed"])
    def test_concurrency_gate(self):
        self.assertTrue(m.group_gate({"diagnosticPassed":True,"matches":[row(True),row(True)]}))
        self.assertFalse(m.group_gate({"diagnosticPassed":True,"matches":[row(True),row(False)]}))
        self.assertFalse(m.group_gate({"diagnosticPassed":False,"matches":[row(True)]}))
