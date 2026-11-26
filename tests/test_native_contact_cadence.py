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
b=load("contact-cadence-benchmark")
class ContactCadenceTest(unittest.TestCase):
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
}
''')
            subprocess.run(["c++","-std=c++17",str(p/"test.cpp"),"-o",str(p/"test")],check=True)
            subprocess.run([str(p/"test")],check=True)
    def test_invalid_mode(self):
        for value in (0,30,10,20,50,True):
            with self.assertRaises(ValueError):
                b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),contact_interval_ms=value)
    def test_gate(self):
        def row(ms):
            return dict(nullRenderer=True,noDraw=True,noUpload=True,sharedAssets=False,configuredRenderIntervalMs=100,
                softwareRenderThreads=1,attackProfile="short-match",exactNativeDuration=True,nativeElapsedMs=300000,
                halfMs=150000,scale=1.0,retention=False,boxRuns=False,timedAttack=False,quickRestarts=False,
                leanScene=True,visualRng=True,skipPitchTexture=True,positionSkinning=True,requestedTaskWorkers=3,
                hardwareThreads=8,taskWorkerPool=3,determinismProbe=True,orderedPose=True,collisionPose=True,
                contactIntervalMs=ms,contactProbe=dict(intervalMs=ms,poseUpdates=300000//ms,maxAgeTicks=ms//10,
                  missingPoseChecks=0,ballOverlaps=3,keeperOverlaps=1,tackleOverlaps=2,controlledRequests=1),
                observedWallMs=300100,maxObservedGapMs=200,resources=dict(userSeconds=30,systemSeconds=2,maxRssKiB=500),
                nativeMemory=dict(peakPssKiB=300,peakNativeThreads=10,sampleCount=300),
                gameplay={k:[1,1] for k in b.integrated.METRICS})
        rows={ms:row(ms) for ms in b.INTERVALS}
        self.assertTrue(b.evaluate(rows)["10"]["cadenceGatePassed"])
        rows[10]["contactProbe"]["maxAgeTicks"]=2
        self.assertFalse(b.evaluate(rows)["10"]["cadenceGatePassed"])
        rows[10]["contactProbe"]["keeperOverlaps"]=4
        with self.assertRaises(ValueError):b.evaluate(rows)
