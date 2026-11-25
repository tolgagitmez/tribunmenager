import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("gate",Path(__file__).resolve().parents[1]/"integrations/league-soccer/readiness.py")
g=importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

def row(i,ms=300000,shots=7,box=4,combos=1,rebounds=1):
    base=dict(shots=5,onTarget=2,goals=0,controlledBox=2,finalThirdMs=20000,combinations=0,reboundShots=0)
    candidate={**base,"shots":shots,"controlledBox":box,"combinations":combos,"reboundShots":rebounds}
    return dict(scenario=g.SCENARIOS[i],seed=2026+i,fixtureHash=str(i),baseline=base,candidate=candidate,calibrated=candidate,calibratedMs=ms)

class ReadinessTest(unittest.TestCase):
    def test_small_sample_is_blocked(self):
        self.assertFalse(g.evaluate([row(0)])["checks"]["sampleSize"])
    def test_full_report_not_authoritative(self):
        result=g.evaluate([row(i) for i in range(3)])
        self.assertEqual(result["status"],"expanded-validation-eligible")
        self.assertFalse(result["authoritative"])
    def test_slow_and_low_attack_block(self):
        r=g.evaluate([row(i,338000,2,1,0,0) for i in range(3)])
        self.assertEqual(r["status"],"blocked")
        self.assertFalse(r["checks"]["calibratedDuration"])
        self.assertFalse(r["checks"]["candidateShotVolume"])
        self.assertFalse(r["checks"]["observedCombination"])
        self.assertFalse(r["checks"]["observedReboundShot"])
    def test_duplicate_seed(self):
        with self.assertRaises(ValueError):g.evaluate([row(0),row(0)])
    def test_missing_metrics(self):
        with self.assertRaises(ValueError):g.pair_sum(None)
        with self.assertRaises(ValueError):g.pair_sum([1,float("nan")])
