import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
instrument=load("instrument")
bench=load("no-upload-benchmark")
class NoUploadTest(unittest.TestCase):
    def test_preserve_cpu(self):
        source = """#include "gametask.hpp"
void GameTask::PutPhase() {
    match->Put();
    TaskManager::GetInstance().EnqueueWork(updateFullbodyModel, true);
    match->UploadGoalNetting();
  if (match) {
    unsigned int playersPerThread = 7;
    TaskManager::GetInstance().EnqueueWork(uploadFullbodyModel, true);
  }
}"""
        patched=instrument.suppress_geometry_uploads(source)
        self.assertIn("match->Put();",patched)
        self.assertIn("EnqueueWork(updateFullbodyModel, true)",patched)
        self.assertIn("if (match && !tribunNoUpload)",patched)
        self.assertIn("if (!tribunNoUpload) match->UploadGoalNetting();",patched)
        with self.assertRaises(SystemExit):instrument.suppress_geometry_uploads("")
    def test_requires_no_draw(self):
        with self.assertRaises(ValueError):
            bench.fixed.timing.run("unused","unused","unused",("test","1.0","0"),no_upload=True)
    def test_comparison(self):
        def row(mode,cpu):
            return dict(noDraw=True,noUpload=mode,configuredRenderIntervalMs=100,softwareRenderThreads=2,
                        exactNativeDuration=True,nativeElapsedMs=300000,attackProfile="short-match",
                        resources=dict(userSeconds=cpu,systemSeconds=2,maxRssKiB=1000),
                        observedWallMs=300100,maxObservedGapMs=150,score=[0,0],shots=[1,1],
                        onTarget=[0,0],controlledBoxCrossings=[2,2])
        a,b=row(False,100),row(True,60)
        report=bench.evaluate({"upload":a,"no-upload":b})
        self.assertEqual(report["cpuSecondsDelta"],-40)
        self.assertFalse(report["productionEnabled"])
        self.assertTrue(report["observedGameplayEqual"])
        b["noDraw"]=False
        with self.assertRaises(ValueError):bench.evaluate({"upload":a,"no-upload":b})
