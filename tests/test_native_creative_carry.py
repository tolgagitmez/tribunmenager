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
p=load("short_match_patch")
b=load("creative-carry-benchmark")
class CreativeCarryTest(unittest.TestCase):
    def test_cpp_policy(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)
            (f/"rules.hpp").write_text("#include <algorithm>\n"+p.CREATIVE_CARRY_RULES)
            (f/"test.cpp").write_text(r'''
#include "rules.hpp"
#include <cassert>
int main(){
  assert(CarrySpeedLimit(.9f,5,.5f,1)>CarrySpeedLimit(.4f,5,.5f,1));
  assert(CarrySpeedLimit(.9f,1,.5f,1)<=.62f);
  assert(CarrySpeedLimit(.9f,5,2,1)==.48f);
  assert(CarryOption(2,1,1,.7f,.8f,.5f)==-1000);
  assert(CarryOption(2,3,1,.7f,.8f,.5f)>CarryOption(1,2,1,.7f,.8f,.5f));
  CarryTrial s;
  assert(s.Begin(2,0,1,.8f,100));
  s.Observe(2,false,false,2.1f,200);assert(s.progressed==0);
  s.Observe(2,false,false,2.2f,350);assert(s.progressed==1);
  assert(!s.Begin(2,0,1,.5f,400));
  assert(s.Begin(2,0,-1,.5f,900));s.Observe(2,true,false,-1,1000);assert(s.lost==1);
  assert(s.Begin(2,0,-1,.8f,1600));s.Observe(3,false,false,-1,1700);assert(s.cancelled==1);
  assert(s.attempts==3&&s.technical==2&&s.conservative==1);
}
''')
            subprocess.run(["c++","-std=c++17",str(f/"test.cpp"),"-o",str(f/"test")],check=True)
            subprocess.run([str(f/"test")],check=True)
    def test_guard(self):
        with self.assertRaises(ValueError):
            b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),creative_carry=True)
    def test_gate(self):
        rows={key:dict(deliveryPassed=True,policySelected=True,controlledCarries=1,
            boxCrossingsDelta=1,shotsDelta=0,onTargetDelta=0,passAccuracyDelta=-.01) for key in b.SCENARIOS}
        self.assertTrue(b.aggregate(rows)["diagnosticPassed"])
        for row in rows.values():row["controlledCarries"]=0
        self.assertFalse(b.aggregate(rows)["diagnosticPassed"])
