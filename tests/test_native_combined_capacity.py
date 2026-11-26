import importlib.util
from pathlib import Path
from unittest.mock import patch
import sys,threading,unittest
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location("combined_capacity",HERE/"combined-capacity.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(start=0,pss=100):
    return dict(ok=True,hardwareThreads=4,firstObservedMonotonic=start,finalObservedMonotonic=start+300,
       observedWallMs=300000,maxObservedGapMs=200,
       resources=dict(userSeconds=10,systemSeconds=2),
       nativeMemory=dict(peakPssKiB=pss,samples=[dict(monotonic=start+i,Pss=pss) for i in range(301)]))
class CombinedCapacityTest(unittest.TestCase):
    def test_alignment(self):
        r=m.aligned_pss([row(0,100),row(.4,200)])
        self.assertEqual(r["peakAlignedPssKiB"],300);self.assertEqual(r["coverage"],1)
        x=row();x["nativeMemory"]["samples"]=x["nativeMemory"]["samples"][::5]
        self.assertLess(m.aligned_pss([x])["coverage"],.9)
    def test_nonoverlap_and_budget(self):
        with patch.object(m.C,"validate"):
            a={**row(),"job":"a"};b={**row(400),"job":"b"}
            self.assertFalse(m.evaluate([a,b],2)["diagnosticPassed"])
            b={**row(),"job":"b"}
            self.assertTrue(m.evaluate([a,b],2,200)["diagnosticPassed"])
            self.assertFalse(m.evaluate([a,b],2,199)["diagnosticPassed"])
    def test_parallel_and_failed_worker(self):
        barrier=threading.Barrier(3)
        def run(i,s):
            barrier.wait(timeout=5)
            if i==1:raise RuntimeError("crash")
            return row()
        with patch.object(m.C,"validate"):
            g=m.run_group(Path("."),Path("."),Path("."),3,runner=run,check_disk=False)
        self.assertFalse(g["diagnosticPassed"])
        self.assertEqual(sum(x["ok"] for x in g["matches"]),2)
        self.assertEqual(len({x["job"] for x in g["matches"]}),3)
    def test_invalid_rows(self):
        with self.assertRaises(ValueError):m.evaluate([{"job":"x"},{"job":"x"}],2)
        with self.assertRaises(ValueError):m.run_group(Path("."),Path("."),Path("."),4,check_disk=False)
        with patch.object(m.C,"validate",side_effect=ValueError("wrong policy")):
            self.assertFalse(m.evaluate([{**row(),"job":"x"}],1)["diagnosticPassed"])
