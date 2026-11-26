import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(ROOT))
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
i=load("instrument")
b=load("adaptive-contact-benchmark")
class AdaptiveContactTest(unittest.TestCase):
    def test_cpp_intervals(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"rng.hpp").write_text(i.VISUAL_RNG_HEADER)
            (p/"test.cpp").write_text(r'''
#include "rng.hpp"
#include <cassert>
int main(){
  using tribun_visual::collisionTicks;
  assert(collisionTicks(nullptr)==10 && collisionTicks("100")==10);
  assert(collisionTicks("50")==5 && collisionTicks("20")==2 && collisionTicks("10")==1);
  assert(collisionTicks("0")==0 && collisionTicks("30")==0);
  using tribun_visual::adaptiveTicks;
  using tribun_visual::adaptiveDue;
  assert(adaptiveTicks(5,false,false)==1);
  assert(adaptiveTicks(6,false,false)==2);
  assert(adaptiveTicks(13,false,false)==10);
  assert(adaptiveTicks(50,true,false)==1 && adaptiveTicks(50,false,true)==1);
  assert(adaptiveDue(20,0,10) && adaptiveDue(20,19,1) && !adaptiveDue(20,19,10));
}
''')
            subprocess.run(["c++","-std=c++17",str(p/"test.cpp"),"-o",str(p/"test")],check=True)
            subprocess.run([str(p/"test")],check=True)
    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),adaptive_contact=True)
    def test_gate(self):
        def row(adaptive):
            return dict(nullRenderer=True,noDraw=True,noUpload=True,sharedAssets=False,configuredRenderIntervalMs=100,
                softwareRenderThreads=1,attackProfile="short-match",exactNativeDuration=True,nativeElapsedMs=300000,
                halfMs=150000,scale=1.0,retention=False,boxRuns=False,timedAttack=False,quickRestarts=False,
                leanScene=True,visualRng=True,skipPitchTexture=True,positionSkinning=True,requestedTaskWorkers=3,
                hardwareThreads=8,taskWorkerPool=3,determinismProbe=True,orderedPose=True,collisionPose=True,
                contactIntervalMs=10,adaptiveContact=adaptive,
                adaptiveContactProbe=dict(playerUpdates=30 if adaptive else 60,highUpdates=10 if adaptive else 0,
                  mediumUpdates=10 if adaptive else 0,lowUpdates=10 if adaptive else 0,queries=10,missingQueries=0,
                  staleQueries=0,maxQueryAgeTicks=1),observedWallMs=300100,maxObservedGapMs=200,
                resources=dict(userSeconds=30,systemSeconds=2,maxRssKiB=500),
                nativeMemory=dict(peakPssKiB=300,peakNativeThreads=10,sampleCount=300),
                gameplay={k:[1,1] for k in b.integrated.METRICS})
        rows={"uniform":row(False),"adaptive":row(True)}
        self.assertTrue(b.evaluate(rows)["diagnosticPassed"])
        self.assertEqual(b.evaluate(rows)["playerUpdateReduction"],0.5)
        rows["adaptive"]["adaptiveContactProbe"]["staleQueries"]=1
        self.assertFalse(b.evaluate(rows)["diagnosticPassed"])
