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
b=load("angular-impact-benchmark")
class AngularImpactTest(unittest.TestCase):
    def test_cpp_coupled_impulse(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"impact.hpp").write_text(i.IMPACT_HEADER)
            (p/"test.cpp").write_text(r'''
#include "impact.hpp"
#include <cassert>
using namespace tribun_impact;
int main(){
  Vec p{1.1f,0,0},lo{-1,-1,-1},hi{1,1,1},still{0,0,0};
  auto headon=resolveAngular(p,lo,hi,{-10,0,0},still,Foot,still);
  assert(headon.valid && headon.spinDelta==0 && headon.velocity.x>0);
  auto oblique=resolveAngular(p,lo,hi,{-10,5,0},still,Foot,still);
  assert(oblique.valid && oblique.spin.z>0 && oblique.velocity.y<5);
  auto reverse=resolveAngular(p,lo,hi,{-10,-5,0},still,Foot,still);
  assert(reverse.valid && reverse.spin.z<0);
  auto rolling=resolveAngular(p,lo,hi,{-10,5,0},still,Foot,{0,0,5/0.11f});
  assert(rolling.valid && rolling.spinDelta<0.001f);
  assert(!resolveAngular(p,lo,hi,{10,0,0},still,Foot,still).valid);
  for(int r=0;r<RegionCount;++r)for(int y=-20;y<=20;++y)for(int w=-100;w<=100;w+=10){
    auto q=resolveAngular(p,lo,hi,{-15,float(y),2},{1,2,0},static_cast<Region>(r),{5,10,float(w)});
    assert(q.valid && q.energyAfter<=q.energyBefore+0.001f);
  }
}
''')
            subprocess.run(["c++","-std=c++17",str(p/"test.cpp"),"-o",str(p/"test")],check=True)
            subprocess.run([str(p/"test")],check=True)
    def test_guard(self):
        with self.assertRaises(ValueError):
            b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),angular_impact=True)
    def test_gate(self):
        def row(angular):
            return dict(nullRenderer=True,noDraw=True,noUpload=True,sharedAssets=False,configuredRenderIntervalMs=100,
                softwareRenderThreads=1,attackProfile="short-match",exactNativeDuration=True,nativeElapsedMs=300000,
                halfMs=150000,scale=1.0,retention=False,boxRuns=False,timedAttack=False,quickRestarts=False,
                leanScene=True,visualRng=True,skipPitchTexture=True,positionSkinning=True,requestedTaskWorkers=3,
                hardwareThreads=8,taskWorkerPool=3,determinismProbe=True,orderedPose=True,collisionPose=True,
                contactIntervalMs=10,adaptiveContact=False,surfaceImpact=True,angularImpact=angular,
                impactProbe=dict(surface=2),adaptiveContactProbe=dict(missingQueries=0,staleQueries=0),
                angularProbe=dict(impacts=2 if angular else 0,spinChanges=1 if angular else 0,
                  energyBeforePerMassSum=30 if angular else 0,energyAfterPerMassSum=10 if angular else 0,
                  maxSpinDeltaRadPerSec=8 if angular else 0,energyViolations=0),
                observedWallMs=300100,maxObservedGapMs=200,resources=dict(userSeconds=30,systemSeconds=2,maxRssKiB=500),
                nativeMemory=dict(peakPssKiB=300,peakNativeThreads=10,sampleCount=300),
                gameplay={k:[1,1] for k in b.integrated.METRICS})
        rows={"retained":row(False),"angular":row(True)}
        self.assertTrue(b.evaluate(rows)["diagnosticPassed"])
        rows["angular"]["angularProbe"]["energyViolations"]=1
        self.assertFalse(b.evaluate(rows)["diagnosticPassed"])
