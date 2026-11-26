import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("retest",Path(__file__).resolve().parents[1]/"integrations/league-soccer/attack-holdout.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BUILD={"binarySha256":"a"*64,"manifestSha256":"b"*64}
def rows():
    result=[]
    for name,seed in m.SCENARIOS.items():
        a=dict(shots=3,onTarget=1,goals=0,controlledBox=2,finalThirdMs=5000,
               sameTeamRecovery=4,opponentRecovery=4,unresolved=1,twoBoxAttackersMs=2000)
        b={**a,"shots":4,"controlledBox":3,"sameTeamRecovery":6,"opponentRecovery":2,
           "twoBoxAttackersMs":3000}
        row={"scenario":name,"seed":seed,"fixtureSha256":"c"*64}
        for p in ("control","retention","boxRuns"):
            row.update({p:a if p=="control" else b,p+"WallMs":300400,
                        p+"Runtime":BUILD,p+"FixtureSha256":"c"*64,p+"Fixed":True})
        result.append(row)
    return result
class HoldoutTest(unittest.TestCase):
    def test_two_candidates_not_automatically_combined(self):
        r=m.assess(rows(),["retention","boxRuns"],BUILD)
        self.assertEqual(r["status"],"interaction-test-required")
        self.assertFalse(r["combinedEnabled"])
        self.assertFalse(r["productionEnabled"])
    def test_partial_results_incomplete(self):
        self.assertEqual(m.assess(rows()[:1],["retention"],BUILD)["status"],"incomplete")
    def test_mixed_inputs_rejected(self):
        for key,value in (("retentionRuntime",{}),("retentionFixtureSha256","wrong"),("retentionFixed",False),("seed",2026)):
            r=rows();r[0][key]=value
            with self.assertRaises(ValueError):m.assess(r,["retention"],BUILD)
    def test_actual_contacts(self):
        a={"timedAttacks":[dict(passes=1,receipts=1,shots=1),dict(passes=0,receipts=0,shots=0)]}
        self.assertEqual(m.contacts([a])["shots"],1)
        with self.assertRaises(ValueError):m.contacts([a,{"timedAttacks":[dict(passes=0,receipts=0,shots=0)]*2}])
