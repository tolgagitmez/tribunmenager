import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
instrument=load("instrument")
bench=load("visual-rng-benchmark")
class VisualRngTest(unittest.TestCase):
    def test_cpp_stream_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"rng.hpp").write_text(instrument.VISUAL_RNG_HEADER)
            (p/"test.cpp").write_text(r'''
#include "rng.hpp"
#include <cassert>
#include <thread>
int main(){
  using namespace tribun_visual;
  Stream physics(123), reference(123), visual(456);
  assert(physics.next()==reference.next());
  for(int i=0;i<10000;i++) visual.next();
  assert(physics.next()==reference.next());
  std::uint32_t a=0,b=0;
  std::thread x([&]{Stream r(seed(1));a=r.next();});
  std::thread y([&]{Stream r(seed(2));b=r.next();});
  x.join();y.join();
  Stream r(seed(1)),s(seed(2));
  assert(a==r.next() && b==s.next() && a!=b);
  for(int i=0;i<1000;i++){float v=visual.range(-1,1);assert(v>=-1 && v<=1);}
}
''')
            subprocess.run(["c++","-std=c++17","-pthread",str(p/"test.cpp"),"-o",str(p/"test")],check=True)
            subprocess.run([str(p/"test")],check=True)
    def test_perlin_legacy_fallback(self):
        src="    srand(mSeed);\n"*3+"rand() % B\n"*4
        patched=instrument.visual_perlin_source(src)
        self.assertEqual(patched.count("visualRng.reset"),3)
        self.assertEqual(patched.count("else srand(mSeed)"),3)
        self.assertEqual(patched.count("visualRng.next()"),4)
    def test_guard(self):
        with self.assertRaises(ValueError):
            bench.fixed.timing.run("x","x","x",("test","1.0","0"),skip_pitch=True)
    def test_compare(self):
        def row(mode,cpu,pss):
            return dict(noDraw=True,noUpload=True,nullRenderer=True,leanScene=True,visualRng=True,skipPitchTexture=mode,
                        sharedAssets=False,configuredRenderIntervalMs=100,softwareRenderThreads=2,
                        exactNativeDuration=True,nativeElapsedMs=300000,attackProfile="short-match",
                        resources=dict(userSeconds=cpu,systemSeconds=2,maxRssKiB=1000),
                        observedWallMs=300100,maxObservedGapMs=150,score=[0,0],shots=[1,1],onTarget=[0,0],
                        controlledBoxCrossings=[2,2],nativeMemory=dict(peakPssKiB=pss),launchToKickoffMs=10000)
        a,b=row(False,100,500),row(True,60,400)
        result=bench.evaluate({"texture":a,"no-texture":b})
        self.assertEqual(result["cpuSecondsDelta"],-40)
        self.assertFalse(result["productionEnabled"])
        b["visualRng"]=False
        with self.assertRaises(ValueError):bench.evaluate({"texture":a,"no-texture":b})
