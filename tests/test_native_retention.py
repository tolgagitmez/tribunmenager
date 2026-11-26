import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("retention",Path(__file__).resolve().parents[1]/"integrations/league-soccer/retention-benchmark.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RetentionBenchmarkTest(unittest.TestCase):
    def test_pairs_and_recovery(self):
        a=dict(shots=2,onTarget=0,goals=0,controlledBox=1,finalThirdMs=2000,sameTeamRecovery=4,opponentRecovery=4,unresolved=2)
        b={**a,"shots":3,"sameTeamRecovery":6,"opponentRecovery":2}
        r=m.evaluate([dict(scenario=m.SCENARIOS[0],control=a,retention=b)])
        self.assertEqual(r["status"],"incomplete")
        self.assertEqual(r["meanDelta"]["shots"],1)
        self.assertEqual(r["resolvedRecoveryRate"],{"control":.5,"retention":.75})
        self.assertFalse(r["authoritative"])
        row=dict(scenario=m.SCENARIOS[0],control=a,retention=b)
        with self.assertRaises(ValueError):m.evaluate([row,row])
    def test_missing_transitions(self):
        with self.assertRaises(ValueError):m.metric({},{"controlTransitions":None})
