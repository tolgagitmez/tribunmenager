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
b=load("surface-impact-benchmark")
class SurfaceImpactTest(unittest.TestCase):
    def test_cpp_physics(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"impact.hpp").write_text(i.IMPACT_HEADER)
            (p/"test.cpp").write_text(r'''
#include "impact.hpp"
#include <cassert>
using namespace tribun_impact;
int main(){
  Vec p{1.1f,0,0},lo{-1,-1,-1},hi{1,1,1},still{0,0,0};
  auto a=resolve(p,lo,hi,{-10,0,0},still,Foot);
  assert(a.valid && std::abs(a.velocity.x-4.8f)<0.001f);
  auto torso=resolve(p,lo,hi,{-10,0,0},still,Torso);
  assert(torso.valid && torso.velocity.x<a.velocity.x);
  auto oblique=resolve(p,lo,hi,{-10,5,0},still,Foot);
  assert(oblique.valid && std::abs(oblique.velocity.y-3.9f)<0.001f);
  assert(!resolve(p,lo,hi,{10,0,0},still,Foot).valid);
  auto moving=resolve(p,lo,hi,{-10,0,0},{2,0,0},Foot);
  assert(moving.valid && moving.velocity.x>a.velocity.x);
  auto inside=normal({0.9f,0,0},lo,hi);
  assert(inside.x==1 && inside.y==0 && inside.z==0);
  for(int r=0;r<RegionCount;++r)for(int x=-30;x<0;++x)for(int y=-30;y<=30;++y){
    auto q=resolve(p,lo,hi,{float(x),float(y),3},still,static_cast<Region>(r));
    assert(q.valid && q.relativeAfter<=q.relativeBefore+0.0001f && q.velocity.x>0);
  }
  assert(region("left_foot")==Foot && region("right_lowerleg")==Leg);
}
''')
            subprocess.run(["c++","-std=c++17",str(p/"test.cpp"),"-o",str(p/"test")],check=True)
            subprocess.run([str(p/"test")],check=True)
    def test_guard(self):
        with self.assertRaises(ValueError):
            b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),surface_impact=True)
    def test_gate(self):
        def row(surface):
            return dict(nullRenderer=True,noDraw=True,noUpload=True,sharedAssets=False,configuredRenderIntervalMs=100,
                softwareRenderThreads=1,attackProfile="short-match",exactNativeDuration=True,nativeElapsedMs=300000,
                halfMs=150000,scale=1.0,retention=False,boxRuns=False,timedAttack=False,quickRestarts=False,
                leanScene=True,visualRng=True,skipPitchTexture=True,positionSkinning=True,requestedTaskWorkers=3,
                hardwareThreads=8,taskWorkerPool=3,determinismProbe=True,orderedPose=True,collisionPose=True,
                contactIntervalMs=10,adaptiveContact=False,surfaceImpact=surface,
                adaptiveContactProbe=dict(missingQueries=0,staleQueries=0),
                impactProbe=dict(legacy=0 if surface else 2,surface=2 if surface else 0,rejected=1 if surface else 0,
                  regions=[2,0,0,0,0,0] if surface else [0]*6,relativeSpeedBeforeSum=20 if surface else 0,
                  relativeSpeedAfterSum=10 if surface else 0,energyViolations=0),
                observedWallMs=300100,maxObservedGapMs=200,resources=dict(userSeconds=30,systemSeconds=2,maxRssKiB=500),
                nativeMemory=dict(peakPssKiB=300,peakNativeThreads=10,sampleCount=300),
                gameplay={k:[1,1] for k in b.integrated.METRICS})
        rows={"legacy":row(False),"surface":row(True)}
        self.assertTrue(b.evaluate(rows)["diagnosticPassed"])
        rows["surface"]["impactProbe"]["energyViolations"]=1
        self.assertFalse(b.evaluate(rows)["diagnosticPassed"])
