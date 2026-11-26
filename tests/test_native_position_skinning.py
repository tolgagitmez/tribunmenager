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
bench=load("position-skinning-benchmark")
class PositionSkinningTest(unittest.TestCase):
    def test_cpp_channel_guard(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"skin.hpp").write_text(instrument.SKINNING_CHANNEL_HEADER)
            (p/"test.cpp").write_text(r'''
#include "skin.hpp"
#include <cassert>
int main(){
  for(int isolated=0;isolated<2;++isolated)
    for(int requested=0;requested<2;++requested)
      for(int bind=0;bind<2;++bind){
        auto c=tribun_skinning::channels(isolated,requested,bind);
        assert(c.vertices);
        bool expected=!(isolated&&requested&&!bind);
        assert(c.normals==expected && c.tangents==expected && c.bitangents==expected);
      }
}
''')
            subprocess.run(["c++","-std=c++17",str(p/"test.cpp"),"-o",str(p/"test")],check=True)
            subprocess.run([str(p/"test")],check=True)
    def test_transform_preserves_positions_and_pose(self):
        src='''#include "humanoid.hpp"
void HumanoidBase::UpdateFullbodyModel(bool updateSrc) {
  int uploadVertices = true;
  int uploadNormals = true;
  int uploadTangents = true;
  int uploadBitangents = true;
  if (uploadVertices) resultVertex.Rotate(joint);
}
void HumanoidBase::Put() { UpdateFullbodyNodes(); }
'''
        patched=instrument.optimize_skinning_channels(src)
        self.assertIn("channels(isolated, requested, updateSrc)",patched)
        self.assertIn("if (uploadVertices) resultVertex.Rotate(joint);",patched)
        self.assertIn("void HumanoidBase::Put() { UpdateFullbodyNodes(); }",patched)
    def test_guard(self):
        with self.assertRaises(ValueError):
            bench.fixed.timing.run("x","x","x",("test","1.0","0"),position_skinning=True)
    def test_compare(self):
        def row(mode,cpu):
            return dict(noDraw=True,noUpload=True,nullRenderer=True,leanScene=False,visualRng=False,
                skipPitchTexture=False,requestedTaskWorkers=0,positionSkinning=mode,hardwareThreads=8,taskWorkerPool=8,
                sharedAssets=False,configuredRenderIntervalMs=100,softwareRenderThreads=2,
                exactNativeDuration=True,nativeElapsedMs=300000,attackProfile="short-match",
                resources=dict(userSeconds=cpu,systemSeconds=2,maxRssKiB=1000),
                observedWallMs=300100,maxObservedGapMs=150,score=[0,0],shots=[1,1],onTarget=[0,0],
                controlledBoxCrossings=[2,2],nativeMemory=dict(peakPssKiB=500,peakNativeThreads=12),launchToKickoffMs=10000)
        a,b=row(False,100),row(True,60)
        self.assertEqual(bench.evaluate({"full":a,"position-only":b})["cpuSecondsDelta"],-40)
        b["positionSkinning"]=False
        with self.assertRaises(ValueError):bench.evaluate({"full":a,"position-only":b})
