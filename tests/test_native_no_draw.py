import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
instrument=load("instrument")
bench=load("no-draw-benchmark")
class NoDrawTest(unittest.TestCase):
    def test_preserves_game_put(self):
        source="""  graphicsSequence->AddUserTaskEntry(gameTask, e_TaskPhase_Put);
  graphicsSequence->AddSystemTaskEntry(graphicsSystem, e_TaskPhase_Get);
  graphicsSequence->AddSystemTaskEntry(graphicsSystem, e_TaskPhase_Process);
  graphicsSequence->AddSystemTaskEntry(graphicsSystem, e_TaskPhase_Put);"""
        patched=instrument.suppress_draw_tasks(source)
        self.assertEqual(patched.count("AddUserTaskEntry(gameTask, e_TaskPhase_Put)"),1)
        self.assertIn("if (!tribunNoDraw)",patched)
        self.assertIn("[tribun-render] scheduled-draw=",patched)
        with self.assertRaises(SystemExit):instrument.suppress_draw_tasks("")
    def test_comparison(self):
        def row(mode,cpu):
            return dict(noDraw=mode,configuredRenderIntervalMs=100,softwareRenderThreads=2,
                        exactNativeDuration=True,nativeElapsedMs=300000,attackProfile="short-match",
                        resources=dict(userSeconds=cpu,systemSeconds=2,maxRssKiB=1000),
                        observedWallMs=300100,maxObservedGapMs=150,score=[0,0],shots=[1,1],
                        onTarget=[0,0],controlledBoxCrossings=[2,2])
        a,b=row(False,100),row(True,60)
        report=bench.evaluate({"draw":a,"no-draw":b})
        self.assertEqual(report["cpuSecondsDelta"],-40)
        self.assertTrue(report["observedGameplayEqual"])
        self.assertFalse(report["productionEnabled"])
        b["shots"]=[0,1]
        self.assertFalse(bench.evaluate({"draw":a,"no-draw":b})["observedGameplayEqual"])
        b["noDraw"]=False
        with self.assertRaises(ValueError):bench.evaluate({"draw":a,"no-draw":b})
