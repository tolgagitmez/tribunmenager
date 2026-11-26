import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location("patch",ROOT/"short_match_patch.py")
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class CloseTouchTest(unittest.TestCase):
    def test_cap(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)
            (f/"rules.hpp").write_text("#include <algorithm>\n#include <cmath>\n"+p.CLOSE_TOUCH_RULES)
            (f/"test.cpp").write_text(r'''
#include "rules.hpp"
#include <cassert>
int main(){
  assert(CloseTouchScale(2,4,.8f,3,1)==1);
  assert(CloseTouchScale(9,3,.6f,1,.2f)<1);
  assert(CloseTouchScale(20,2,.6f,1,0)>=.72f);
  assert(CloseTouchCap(3,.9f,4,1)>CloseTouchCap(3,.5f,1,0));
  CloseTouchProbe p;p.Record(8,7);p.Record(5,5);assert(p.contacts==2&&p.adjusted==1);
}
''')
            subprocess.run(["c++","-std=c++17",str(f/"test.cpp"),"-o",str(f/"test")],check=True)
            subprocess.run([str(f/"test")],check=True)
