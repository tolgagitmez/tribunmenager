import copy
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location("quality",ROOT/"quality-qualification.py")
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
def row():
    return dict(deliveryPassed=True,policySelected=True,controlledCarries=4,
        decisionProbe={"attempts":[3,3],"technical":[0,0],"lost":[0,1]},
        boxCrossingsDelta=1,shotsDelta=1,onTargetDelta=1,passAccuracyDelta=.01,
        referenceCpu=30,candidateCpu=31,referencePss=100,candidatePss=105,
        referenceShots=5,candidateShots=6,referenceOnTarget=2,candidateOnTarget=3)
class QualityTest(unittest.TestCase):
    def setUp(self):self.rows={s:[row(),row()] for s in q.SCENARIOS}
    def test_gate(self):
        result=q.aggregate(self.rows)
        self.assertTrue(result["diagnosticPassed"])
        self.assertFalse(result["technicalCoverageObserved"])
        self.assertEqual(result["pairs"],6)
    def test_single_outlier_cannot_pass(self):
        for pair in self.rows.values():
            for r in pair:r["boxCrossingsDelta"]=-1
        self.rows["balanced"][0]["boxCrossingsDelta"]=20
        self.assertFalse(q.aggregate(self.rows)["diagnosticPassed"])
    def test_resource_or_missing_evidence_blocks(self):
        self.rows["balanced"][0]["candidatePss"]=120
        self.assertFalse(q.aggregate(self.rows)["diagnosticPassed"])
        self.rows["balanced"].pop()
        with self.assertRaises(ValueError):q.aggregate(self.rows)
    def test_combined_flags_rejected(self):
        with self.assertRaisesRegex(ValueError,"cannot be combined"):
            q.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),creative_carry=True,finish=True)
