import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_box_entry_av import compare
class BoxEntryTest(unittest.TestCase):
    def row(self,fixture,mode,entries):
        return dict(passed=True,profile='short-match',boxLane=mode,boxLaneObserved=mode,fixtureSha256=fixture,quality=dict(football=dict(totalControlledBoxCrossings=entries,totalShots=5,passes=[20,20],completed=[14,14],onTarget=[1,1])))
    def test_review(self):
        a,b=self.row('a',False,2),self.row('a',True,3)
        c,d=self.row('b',False,2),self.row('b',True,3)
        r=compare([(a,b),(c,d)]);self.assertTrue(r['candidateForFurtherReview']);self.assertFalse(r['automaticPromotion'])
        d['boxLaneObserved']=False;self.assertFalse(compare([(a,b),(c,d)])['passed'])
    def test_no_gain_or_duplicate(self):
        a,b=self.row('a',False,2),self.row('a',True,2)
        c,d=self.row('b',False,2),self.row('b',True,2)
        self.assertFalse(compare([(a,b),(c,d)])['candidateForFurtherReview'])
        self.assertFalse(compare([(a,b),(a,b)])['passed'])
