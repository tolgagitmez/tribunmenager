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
b=load("duel-benchmark")
class DuelTest(unittest.TestCase):
    def test_cpp_policy(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)
            (f/"rules.hpp").write_text("#include <algorithm>\n"+p.DUEL_RULES)
            (f/"test.cpp").write_text(r'''
#include "rules.hpp"
#include <cassert>
int main(){
  assert(DuelEligible(2,3,1,.5f,.8f));
  assert(!DuelEligible(-1,3,1,.5f,.8f));
  assert(!DuelEligible(2,3,-1,.5f,.8f));
  assert(!DuelEligible(2,3,1,.5f,.4f));
  assert(DuelEscapeScore(2,2,1,.6f,.8f,1)>DuelEscapeScore(2,2,1,.6f,.8f,-1));
  DuelTrial s;
  assert(s.Begin(1,2,0,1,100));
  s.Observe(1,false,false,2.1f,2,2,350);assert(s.beaten==0);
  s.Observe(1,false,false,3.2f,2,2,400);assert(s.beaten==1);
  assert(!s.Begin(1,2,0,1,500));
  assert(s.Begin(1,2,0,-1,1100));
  s.Observe(1,true,false,-1,-2,1,1200);assert(s.lost==1);
  assert(s.Begin(1,2,0,-1,1900));
  s.Observe(3,false,false,-3,-1,2,2200);assert(s.cancelled==1);
}
''')
            subprocess.run(["c++","-std=c++17",str(f/"test.cpp"),"-o",str(f/"test")],check=True)
            subprocess.run([str(f/"test")],check=True)
    def test_guard(self):
        with self.assertRaises(ValueError):
            b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),duel=True)
    def test_gate(self):
        rows={key:dict(deliveryPassed=True,policySelected=True,beatenDefenders=1,
            boxCrossingsDelta=1,shotsDelta=0,onTargetDelta=0,passAccuracyDelta=-.01) for key in b.SCENARIOS}
        self.assertTrue(b.aggregate(rows)["diagnosticPassed"])
        for row in rows.values():row["beatenDefenders"]=0
        self.assertFalse(b.aggregate(rows)["diagnosticPassed"])
