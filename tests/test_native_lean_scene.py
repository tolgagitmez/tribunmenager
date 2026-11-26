import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
instrument=load("instrument")
bench=load("lean-scene-benchmark")
class LeanSceneTest(unittest.TestCase):
    def test_preserves_pitch_animation_and_excitement(self):
        src='''#include "match.hpp"
const float crowdGainUpdateThreshold = 0.001f;
  if (!SuperDebug()) {
    tmpStadiumNode = full;
    RandomizeAdboards(tmpStadiumNode);
  }
  if (SuperDebug())
    tmpStadiumNode = pitch;
  anims->Load("media/animations");
  GeneratePitch(2048, 1024, 1024, 512, 2048, 1024);
  Log(e_Notice, "Match", "Match", "Loading crowd sounds");
  GetScene3D()->AddObject(crowd02);
  scene3D->DeleteObject(crowd01);
  scene3D->DeleteObject(crowd02);
  excitementEventBoost *= excitementEventDecayRate;
  const float effectiveExcitement = clamp(excitement + excitementEventBoost, 0.0f, 1.0f);
'''
        patched=instrument.lightweight_match(src)
        for x in ('anims->Load("media/animations");',"GeneratePitch(2048, 1024, 1024, 512, 2048, 1024);","excitementEventBoost *= excitementEventDecayRate;"):
            self.assertIn(x,patched)
        self.assertIn("if (SuperDebug() || TribunLeanScene())",patched)
        self.assertIn("if (crowd01) scene3D->DeleteObject(crowd01);",patched)
        self.assertLess(patched.index("excitementEventBoost *="),patched.index("if (TribunLeanScene()) return;"))
        self.assertIn("TRIBUN_NATIVE_NO_UPLOAD",patched)
    def test_guard(self):
        with self.assertRaises(ValueError):bench.fixed.timing.run("x","x","x",("test","1.0","0"),lean_scene=True)
    def test_comparison(self):
        def row(mode,cpu,pss):
            return dict(noDraw=True,noUpload=True,nullRenderer=True,leanScene=mode,sharedAssets=False,
                        configuredRenderIntervalMs=100,softwareRenderThreads=2,exactNativeDuration=True,nativeElapsedMs=300000,
                        attackProfile="short-match",resources=dict(userSeconds=cpu,systemSeconds=2,maxRssKiB=1000),
                        observedWallMs=300100,maxObservedGapMs=150,score=[0,0],shots=[1,1],onTarget=[0,0],
                        controlledBoxCrossings=[2,2],nativeMemory=dict(peakPssKiB=pss),launchToKickoffMs=10000)
        a,b=row(False,100,500),row(True,60,400)
        result=bench.evaluate({"full":a,"lean":b})
        self.assertEqual(result["cpuSecondsDelta"],-40)
        self.assertEqual(result["peakPssDeltaKiB"],-100)
        self.assertFalse(result["productionEnabled"])
        b["nullRenderer"]=False
        with self.assertRaises(ValueError):bench.evaluate({"full":a,"lean":b})
