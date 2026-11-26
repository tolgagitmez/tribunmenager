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
bench=load("worker-limit-benchmark")
class WorkerLimitTest(unittest.TestCase):
    def test_actual_cpp_count(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"limit.hpp").write_text(instrument.WORKER_LIMIT_HEADER)
            (p/"test.cpp").write_text(r'''
#include "limit.hpp"
#include <cassert>
int main(){
  using tribun_workers::count;
  assert(count(0,nullptr,false)==3);
  assert(count(64,"0",false)==64);
  assert(count(64,"3",true)==3);
  assert(count(64,"4",true)==4);
  assert(count(2,"4",true)==3);
  for(auto value:{"1","2","5","", "03"}){
    bool rejected=false;
    try{count(64,value,true);}catch(const std::invalid_argument&){rejected=true;}
    assert(rejected);
  }
  bool rejected=false;
  try{count(64,"3",false);}catch(const std::invalid_argument&){rejected=true;}
  assert(rejected);
}
''')
            subprocess.run(["c++","-std=c++17",str(p/"test.cpp"),"-o",str(p/"test")],check=True)
            subprocess.run([str(p/"test")],check=True)
    def test_guard(self):
        for cap in (1,2,3,4,5,True):
            with self.assertRaises(ValueError):
                bench.fixed.timing.run("x","x","x",("test","1.0","0"),task_workers=cap)
    def test_compare(self):
        def row(cap,hardware,pool,cpu):
            return dict(noDraw=True,noUpload=True,nullRenderer=True,leanScene=False,visualRng=False,
                skipPitchTexture=False,requestedTaskWorkers=cap,hardwareThreads=hardware,taskWorkerPool=pool,
                sharedAssets=False,configuredRenderIntervalMs=100,softwareRenderThreads=2,
                exactNativeDuration=True,nativeElapsedMs=300000,attackProfile="short-match",
                resources=dict(userSeconds=cpu,systemSeconds=2,maxRssKiB=1000),
                observedWallMs=300100,maxObservedGapMs=150,score=[0,0],shots=[1,1],onTarget=[0,0],
                controlledBoxCrossings=[2,2],nativeMemory=dict(peakPssKiB=500,peakNativeThreads=pool+4),launchToKickoffMs=10000)
        result=bench.evaluate({"auto":row(0,8,8,100),"cap3":row(3,8,3,60)})
        self.assertTrue(result["actualPoolContrast"])
        self.assertEqual(result["taskWorkerDelta"],-5)
        self.assertFalse(bench.evaluate({"auto":row(0,2,3,100),"cap3":row(3,2,3,100)})["actualPoolContrast"])
        with self.assertRaises(ValueError):bench.evaluate({"auto":row(0,8,8,100),"cap3":row(3,8,4,60)})
