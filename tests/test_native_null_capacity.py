import importlib.util
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location("pool",Path(__file__).resolve().parents[1]/"integrations/league-soccer/null-capacity.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(start=1):
    return dict(ok=True,nullRenderer=True,noDraw=True,noUpload=True,exactNativeDuration=True,
                nativeElapsedMs=300000,configuredRenderIntervalMs=100,
                firstObservedMonotonic=start,finalObservedMonotonic=start+300,observedWallMs=300000,
                maxObservedGapMs=300,resources=dict(userSeconds=10,systemSeconds=2,maxRssKiB=100))
class NullCapacityTest(unittest.TestCase):
    def test_distinct_concurrent_jobs(self):
        barrier=threading.Barrier(4)
        def run(index,scenario):
            barrier.wait(timeout=5)
            return row()
        result=m.run_group(Path("."),Path("."),Path("."),4,runner=run,check_disk=False)
        self.assertTrue(result["diagnosticPassed"])
        self.assertEqual(result["totalCpuSeconds"],48)
        self.assertEqual(len({r["job"] for r in result["matches"]}),4)
    def test_failure_isolated(self):
        def run(index,scenario):
            if index==1:raise RuntimeError("crash")
            return row()
        result=m.run_group(Path("."),Path("."),Path("."),2,runner=run,check_disk=False)
        self.assertFalse(result["diagnosticPassed"])
        self.assertTrue(result["matches"][0]["ok"])
        self.assertFalse(result["matches"][1]["ok"])
    def test_not_real_overlap(self):
        self.assertFalse(m.evaluate([{**row(0),"job":"a"},{**row(400),"job":"b"}],2)["diagnosticPassed"])
    def test_mode_and_bounds(self):
        self.assertFalse(m.evaluate([{**row(),"job":"a","nullRenderer":False}],1)["diagnosticPassed"])
        with self.assertRaises(ValueError):m.run_group(Path("."),Path("."),Path("."),11,check_disk=False)
        with self.assertRaises(ValueError):m.evaluate([{**row(),"job":"a"},{**row(),"job":"a"}],2)
