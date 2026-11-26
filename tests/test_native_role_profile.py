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
b=load("role-profile-benchmark")
class RoleProfileTest(unittest.TestCase):
    def test_cpp_policy(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)
            (f/"rules.hpp").write_text("#include <algorithm>\n"+p.ROLE_PROFILE_RULES)
            (f/"test.cpp").write_text(r'''
#include "rules.hpp"
#include <cassert>
int main(){
  assert(Profile(CF,.9f,.4f,.9f,.5f,.5f,.4f)==Poacher);
  assert(Profile(CF,.4f,.9f,.4f,.5f,.5f,.9f)==FalseNine);
  assert(Profile(CF,.6f,.6f,.6f,.6f,.6f,.6f)==Neutral);
  assert(Profile(FB,.9f,.5f,.5f,.4f,.9f,.5f)==Overlap);
  assert(Profile(FB,.4f,.5f,.5f,.9f,.4f,.5f)==StayBack);
  assert(ProfileOffset(Poacher,4,0,3).advance>ProfileOffset(FalseNine,4,0,3).advance);
  assert(ProfileOffset(Inside,10,0,3).lateral<0);
  assert(ProfileOffset(Inside,-10,0,3).lateral>0);
  assert(ProfileOffset(Overlap,15,0,2).advance==0);
  RoleProbe p;p.Sample(Poacher,1.25f,-.5f);
  assert(p.samples[Poacher]==1&&p.forwardMm[Poacher]==1250&&p.wideMm[Poacher]==-500);
}
''')
            subprocess.run(["c++","-std=c++17",str(f/"test.cpp"),"-o",str(f/"test")],check=True)
            subprocess.run([str(f/"test")],check=True)
    def test_guard(self):
        with self.assertRaises(ValueError):
            b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),role_profile=True)
    def test_gate(self):
        def profile(k,f):return dict(team=0,profile=k,targets=2,samples=30,forwardMm=f,wideMm=0)
        rows={key:dict(deliveryPassed=True,policySelected=True,profilesUsed=[1,2],
            referenceProfiles=[profile(1,0),profile(2,0)],candidateProfiles=[profile(1,30000),profile(2,-30000)],
            shotsDelta=0,passAccuracyDelta=0) for key in b.SCENARIOS}
        self.assertTrue(b.aggregate(rows)["diagnosticPassed"])
        for row in rows.values():row["candidateProfiles"]=row["referenceProfiles"]
        self.assertFalse(b.aggregate(rows)["diagnosticPassed"])
