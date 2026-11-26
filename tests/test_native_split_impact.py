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
b=load("split-impact-benchmark")
class SplitImpactTest(unittest.TestCase):
    def test_cpp_sweep(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"impact.hpp").write_text(i.IMPACT_HEADER)
            (p/"test.cpp").write_text(r'''
#include "impact.hpp"
#include <cassert>
using namespace tribun_impact;
int main(){
  Vec lo{-0.1f,-0.1f,-0.1f},hi{0.1f,0.1f,0.1f};
  auto hit=sweepSphere({-1,0,0},{1,0,0},lo,hi,0.11f);
  assert(hit.hit && std::abs(hit.time-0.395f)<0.00001f);
  auto reverse=sweepSphere({1,0,0},{-1,0,0},lo,hi,0.11f);
  assert(reverse.hit && std::abs(reverse.time-hit.time)<0.00001f);
  assert(!sweepSphere({-1,0.3f,0},{1,0.3f,0},lo,hi,0.11f).hit);
  // Expanded box would accept this corner; true rounded sphere misses.
  assert(!sweepSphere({-1,0.19f,0.19f},{1,0.19f,0.19f},lo,hi,0.11f).hit);
  assert(sweepSphere({-1,0.16f,0.16f},{1,0.16f,0.16f},lo,hi,0.11f).hit);
  assert(sweepSphere({0,0,0},{2,0,0},lo,hi,0.11f).time==0);
  assert(!sweepSphere({2,0,0},{3,0,0},lo,hi,0.11f).hit);
  assert(!sweepSphere({2,0,0},{2,0,0},lo,hi,0.11f).hit);
  auto response=resolveAngular(hit.point,lo,hi,{25,0,0},{0,0,0},Foot,{0,0,0});
  assert(response.valid && response.velocity.x<0);
  for(int j=0;j<=1000;++j){
    auto dt=splitDurations(j/1000.0f);
    assert(dt.before>=0 && dt.after>=0 && std::abs(dt.before+dt.after-0.01f)<1e-8f);
    float x=-1+25*dt.before+response.velocity.x*dt.after;
    assert(std::isfinite(x));
  }
}
''')
            subprocess.run(["c++","-std=c++17",str(p/"test.cpp"),"-o",str(p/"test")],check=True)
            subprocess.run([str(p/"test")],check=True)
    def test_guard(self):
        with self.assertRaises(ValueError):
            b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),split_impact=True)
    def test_gate(self):
        def row(split):
            return dict(nullRenderer=True,noDraw=True,noUpload=True,sharedAssets=False,configuredRenderIntervalMs=100,
                softwareRenderThreads=1,attackProfile="short-match",exactNativeDuration=True,nativeElapsedMs=300000,
                halfMs=150000,scale=1.0,retention=False,boxRuns=False,timedAttack=False,quickRestarts=False,
                leanScene=True,visualRng=True,skipPitchTexture=True,positionSkinning=True,requestedTaskWorkers=3,
                hardwareThreads=8,taskWorkerPool=3,determinismProbe=True,orderedPose=True,collisionPose=True,
                contactIntervalMs=10,adaptiveContact=False,surfaceImpact=True,angularImpact=True,sweptImpact=True,splitImpact=split,
                adaptiveContactProbe=dict(missingQueries=0,staleQueries=0),angularProbe=dict(energyViolations=0),
                sweptProbe=dict(applied=2),splitProbe=dict(queued=3 if split else 0,applied=2 if split else 0,
                    cancelled=1 if split else 0,beforeMs=7 if split else 0,afterMs=13 if split else 0),
                observedWallMs=300100,maxObservedGapMs=200,resources=dict(userSeconds=30,systemSeconds=2,maxRssKiB=500),
                nativeMemory=dict(peakPssKiB=300,peakNativeThreads=10,sampleCount=300),
                gameplay={k:[1,1] for k in b.integrated.METRICS})
        rows={"early":row(False),"split":row(True)}
        self.assertTrue(b.evaluate(rows)["diagnosticPassed"])
        rows["split"]["splitProbe"]["afterMs"]=14
        with self.assertRaises(ValueError):b.evaluate(rows)
