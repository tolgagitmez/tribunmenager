import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location("collective",ROOT/"collective-ai-benchmark.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
class CollectiveAITest(unittest.TestCase):
    def test_isolation(self):
        run=b.I.fixed.timing.run
        with self.assertRaises(ValueError):run("x","x","x",("test","1.0","0"),collective_ai=True)
        with self.assertRaises(ValueError):run("x","x","x",("test","1.0","0"),collective_ai=True,transition=True)
    def test_aggregate_requires_actual_coverage(self):
        p={group:{k:[1,1] for k in keys} for group,keys in b.KEYS.items()}
        rows={s:dict(deliveryPassed=True,candidateProbes=p,shotsDelta=0,onTargetDelta=0,boxEntriesDelta=0,passAccuracyDelta=0) for s in b.SCENARIOS}
        self.assertTrue(b.aggregate(rows)["diagnosticPassed"])
        p["triangleProbe"]["completed"]=[0,0]
        self.assertFalse(b.aggregate(rows)["diagnosticPassed"])
    def test_aggregate_protects_accuracy(self):
        p={group:{k:[1,1] for k in keys} for group,keys in b.KEYS.items()}
        rows={s:dict(deliveryPassed=True,candidateProbes=p,shotsDelta=0,onTargetDelta=0,boxEntriesDelta=0,passAccuracyDelta=0) for s in b.SCENARIOS}
        rows[b.SCENARIOS[0]]["passAccuracyDelta"]=-.09
        self.assertFalse(b.aggregate(rows)["diagnosticPassed"])
