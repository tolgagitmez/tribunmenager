import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("capacity",Path(__file__).resolve().parents[1]/"integrations/league-soccer/capacity-benchmark.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(start=10,duration=300000):
    return dict(ok=True,firstObservedMonotonic=start,finalObservedMonotonic=start+duration/1000,
                observedWallMs=duration,exactNativeDuration=True,maxObservedGapMs=300,
                resources=dict(userSeconds=10,systemSeconds=2,maxRssKiB=1000))
class CapacityBenchmarkTest(unittest.TestCase):
    def test_actual_overlap(self):
        r=m.evaluate([row(),row(12)],2)
        self.assertTrue(r["diagnosticPassed"])
        self.assertEqual(r["totalCpuSeconds"],24)
    def test_sequential_not_concurrent(self):
        self.assertFalse(m.evaluate([row(),row(400)],2)["checks"]["actualOverlap"])
    def test_slow_and_failed(self):
        self.assertFalse(m.evaluate([row(duration=320000)],1)["diagnosticPassed"])
        self.assertFalse(m.evaluate([{"ok":False}],1)["diagnosticPassed"])
    def test_missing_resources(self):
        r=row();r["resources"]=None
        self.assertFalse(m.evaluate([r],1)["checks"]["resourceMeasurements"])
