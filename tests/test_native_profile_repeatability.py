import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location("repeat",ROOT/"profile-repeatability.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(candidate):
    return dict(nullRenderer=True,noDraw=True,noUpload=True,sharedAssets=False,configuredRenderIntervalMs=100,
        softwareRenderThreads=1,attackProfile="short-match",exactNativeDuration=True,nativeElapsedMs=300000,
        halfMs=150000,scale=1.0,retention=False,boxRuns=False,timedAttack=False,quickRestarts=False,
        leanScene=candidate,visualRng=candidate,skipPitchTexture=candidate,positionSkinning=candidate,
        requestedTaskWorkers=3 if candidate else 0,hardwareThreads=8,taskWorkerPool=3 if candidate else 8,
        observedWallMs=300100,maxObservedGapMs=200,resources=dict(userSeconds=30,systemSeconds=2,maxRssKiB=500),
        nativeMemory=dict(peakPssKiB=300,peakNativeThreads=10,sampleCount=300),
        gameplay={k:[1,1] for k in m.integrated.METRICS})
def runs():
    return {mode:[dict(runId=mode+str(i),match=row(mode=="candidate"),digests={0:"a",100:"b",300000:"c"}) for i in range(2)] for mode in ("reference","candidate")}
class RepeatabilityTest(unittest.TestCase):
    def test_first_divergence(self):
        result=m.compare({0:"a",100:"b",200:"c"},{0:"a",100:"x",300:"c"})
        self.assertEqual(result["firstDifferentCommonMs"],100)
        self.assertEqual(result["firstUnmatchedSampleMs"],200)
        self.assertFalse(result["observedTraceEqual"])
    def test_grid_mismatch_not_physical_difference(self):
        r=m.compare({0:"a",100:"b"},{0:"a",200:"b"})
        self.assertIsNone(r["firstDifferentCommonMs"])
        self.assertFalse(r["observedTraceEqual"])
    def test_identical_observed_runs(self):
        self.assertTrue(m.evaluate_scenario(runs())["observedParityGatePassed"])
    def test_reference_instability_blocks(self):
        r=runs();r["reference"][1]["digests"][100]="x"
        result=m.evaluate_scenario(r)
        self.assertFalse(result["checks"]["referenceRepeatable"])
        self.assertFalse(result["observedParityGatePassed"])
    def test_candidate_regression_blocks(self):
        r=runs();r["candidate"][0]["match"]["gameplay"]["passes"]=[2,1]
        self.assertFalse(m.evaluate_scenario(r)["observedParityGatePassed"])
    def test_duplicate_run(self):
        r=runs();r["reference"][1]["runId"]=r["reference"][0]["runId"]
        with self.assertRaises(ValueError):m.evaluate_scenario(r)
    def test_frame_digest_ignores_host_clock(self):
        def frame(t):
            return {**{k:0 for k in m.FRAME_FIELDS},"fixedClock":{"started":True,"elapsedMs":t},
                    "players":[],"elapsedMs":t+500}
        a=[frame(t) for t in list(range(0,150000,1000))+[150000,300000]]
        b=[{**x,"elapsedMs":x["elapsedMs"]+20} for x in a]
        self.assertEqual(m.digest_frames(a),m.digest_frames(b))
        b[1]["ball"]=[1,2,3]
        self.assertNotEqual(m.digest_frames(a),m.digest_frames(b))
