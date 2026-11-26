import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
spec=importlib.util.spec_from_file_location("patch",ROOT/"short_match_patch.py")
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class ActivationRedesignTest(unittest.TestCase):
    def test_revised_gates_and_unchanged_success(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)
            (f/"rules.hpp").write_text("#include <algorithm>\n"+p.TRIANGLE_RULES+p.DUEL_RULES+p.HOLD_UP_RULES)
            (f/"test.cpp").write_text(r'''
#include "rules.hpp"
#include <cassert>
int main(){
  assert(DuelEligible(.4f,5,.3f,1.2f,.5f));
  assert(!DuelEligible(.4f,5,-.3f,1.2f,.5f));
  assert(!DuelEligible(.4f,5,.3f,1.2f,.4f));
  assert(HoldEligible(45,.4f,3.8f,1.2f,.5f));
  assert(!HoldEligible(45,.8f,3.8f,1.2f,.5f));
  assert(!HoldEligible(45,.4f,3.8f,1.2f,.4f));
  assert(!TrianglePassSafe(.7f,.8f));
  DuelTrial duel;duel.Begin(1,2,0,1,100);
  duel.Observe(1,false,false,2.2f,2,2,400);assert(duel.beaten==0);
  HoldTrial hold;hold.Begin(1,100);
  assert(!hold.Pass(1,2,true,300));
  TriangleState tri;tri.Begin(1,2,3,100);
  assert(!tri.Pass(2,3,110));
}
''')
            subprocess.run(["c++","-std=c++17",str(f/"test.cpp"),"-o",str(f/"test")],check=True)
            subprocess.run([str(f/"test")],check=True)
