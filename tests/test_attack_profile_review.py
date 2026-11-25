import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("review",Path(__file__).resolve().parents[1]/"tools/native-attack-review.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def report(profile,count=3,**changes):
    rows=[]
    for name,seed in list(m.SCENARIOS.items())[:count]:
        a=dict(shots=3,onTarget=1,goals=0,controlledBox=2,finalThirdMs=5000,
               sameTeamRecovery=4,opponentRecovery=4,unresolved=1,twoBoxAttackersMs=2000)
        b={**a,"shots":4,"controlledBox":3,"sameTeamRecovery":6,"opponentRecovery":2,
           "twoBoxAttackersMs":3000,**changes}
        row={"scenario":name,"seed":seed,"control":a,profile:b,"controlWallMs":300300,profile+"WallMs":300400}
        if profile=="timedAttack":
            row["controlContacts"]=dict(passes=0,receipts=0,shots=0)
            row[profile+"Contacts"]=dict(passes=2,receipts=1,shots=1)
        rows.append(row)
    return dict(authoritative=False,pairCount=count,rows=rows,meanDelta={"shots":999})
class ReviewTest(unittest.TestCase):
    def test_missing_reports_block(self):
        self.assertEqual(m.review({})["status"],"blocked")
    def test_only_retest_not_promotion(self):
        r=m.review({p:report(p) for p in m.PROFILES})
        self.assertEqual(r["retestCandidates"],list(m.PROFILES))
        self.assertFalse(r["combinedEnabled"])
        self.assertFalse(r["productionEnabled"])
        self.assertEqual(r["profiles"]["retention"]["meanDelta"]["shots"],1)
    def test_incomplete_timed_and_recovery_regression(self):
        r=m.review({"timedAttack":report("timedAttack",1),"retention":report("retention",sameTeamRecovery=1,opponentRecovery=7)})
        self.assertEqual(r["profiles"]["timedAttack"]["status"],"needs-more-pairs")
        self.assertEqual(r["profiles"]["retention"]["status"],"not-selected")
    def test_unresolved_not_improvement(self):
        r=m.assess(report("retention",sameTeamRecovery=1,opponentRecovery=0,unresolved=30),"retention")
        self.assertFalse(r["checks"]["resolvedCoverageNotMateriallyLower"])
    def test_invalid_or_duplicate(self):
        r=report("boxRuns")
        r["rows"][1]=r["rows"][0]
        self.assertEqual(m.review({"boxRuns":r})["profiles"]["boxRuns"]["status"],"invalid")
        r=report("timedAttack")
        r["rows"][0]["controlContacts"]["passes"]=1
        self.assertEqual(m.review({"timedAttack":r})["profiles"]["timedAttack"]["status"],"invalid")
    def test_average_cannot_hide_zero_output(self):
        r=report("boxRuns")
        r["rows"][0]["boxRuns"]["shots"]=0
        r["rows"][0]["boxRuns"]["onTarget"]=0
        r["rows"][1]["boxRuns"]["shots"]=10
        self.assertFalse(m.assess(r,"boxRuns")["checks"]["noScenarioLosesAllObservedShots"])
