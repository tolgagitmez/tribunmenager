import importlib.util
from pathlib import Path
import subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(ROOT))
def load(n):
    s=importlib.util.spec_from_file_location(n,ROOT/(n+".py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=load("match-pace-benchmark")
p=load("short_match_patch")
class PaceTest(unittest.TestCase):
    def test_cpp_rules(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"test.cpp"
            f.write_text("#include <algorithm>\n#include <cmath>\n#include <cassert>\n"+p.PACE_RULES+r'''
int main(){
 assert(PaceOutlet(20,8,12,2,.7,.8));
 assert(!PaceOutlet(20,-8,12,2,.7,.8));
 assert(!PaceOutlet(20,8,12,.5,.7,.8));
 assert(!PaceOutlet(20,8,12,2,.7,.5));
 assert(PacePassBonus(9,15,1)>PacePassBonus(9,30,0));
 assert(PaceShot(10,.8,.8,.7,true));
 assert(!PaceShot(30,.8,.8,.7,true));
 assert(!PaceShot(10,.2,.8,.7,true));
 assert(!PaceShot(10,.8,.8,.7,false));
}''')
            subprocess.run(["c++","-std=c++17",str(f),"-o",str(f.with_suffix(""))],check=True)
            subprocess.run([str(f.with_suffix(""))],check=True)
    def test_isolation(self):
        run=b.I.fixed.timing.run
        with self.assertRaises(ValueError):run("x","x","x",("test","1.0","0"),match_pace=True)
        with self.assertRaises(ValueError):run("x","x","x",("test","1.0","0"),match_pace=True,collective_ai=True)
    def test_gate(self):
        rows={s:dict(deliveryPassed=True,outletEvaluations=5,boxEntriesDelta=1,shotsDelta=1,onTargetDelta=0,accuracyDelta=0,openPlayMsDelta=0) for s in b.SCENARIOS}
        self.assertTrue(b.aggregate(rows)["diagnosticPassed"])
        for row in rows.values():row["shotsDelta"]=0
        self.assertFalse(b.aggregate(rows)["diagnosticPassed"])
