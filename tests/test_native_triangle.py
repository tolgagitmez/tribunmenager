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
b=load("triangle-benchmark")
class TriangleTest(unittest.TestCase):
    def test_cpp_state(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)
            (f/"rules.hpp").write_text(p.TRIANGLE_RULES)
            (f/"test.cpp").write_text(r'''
#include "rules.hpp"
#include <cassert>
int main(){
  TriangleState s;
  assert(!s.Begin(1,2,1,100));
  assert(s.Begin(1,2,3,100));
  assert(!s.Pass(2,3,120));
  s.Observe(2,100,false,130);assert(s.stage==1);
  s.Observe(2,140,false,150);assert(s.stage==2);
  assert(!s.Pass(2,1,160));assert(s.Pass(2,3,170));
  s.Observe(3,180,false,190);assert(s.completed==1&&s.stage==0);
  assert(!s.Begin(1,2,3,200));assert(s.Begin(1,2,3,1500));
  s.Observe(2,1510,true,1520);assert(s.stage==0&&s.completed==1);
  assert(s.Begin(1,2,3,3000));s.Observe(-1,0,false,5500);assert(s.stage==0);
  assert(TriangleGeometry(7,12,5,2,15));
  assert(!TriangleGeometry(7,12,5,1,15));
  assert(TrianglePassSafe(.8,.83)&&!TrianglePassSafe(.7,.8));
}
''')
            subprocess.run(["c++","-std=c++17",str(f/"test.cpp"),"-o",str(f/"test")],check=True)
            subprocess.run([str(f/"test")],check=True)
    def test_guard(self):
        with self.assertRaises(ValueError):
            b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),triangle=True)
    def test_gate(self):
        rows={key:dict(deliveryPassed=True,policySelected=True,completedTriangles=1,
            boxCrossingsDelta=1,shotsDelta=0,onTargetDelta=0,passAccuracyDelta=-.01) for key in b.SCENARIOS}
        self.assertTrue(b.aggregate(rows)["diagnosticPassed"])
        for row in rows.values():row["completedTriangles"]=0
        self.assertFalse(b.aggregate(rows)["diagnosticPassed"])
