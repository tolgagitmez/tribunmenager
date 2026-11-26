import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_av_attack_comparison import compare
class ComparisonTest(unittest.TestCase):
    def row(self,profile,shots,entries):
        return dict(profile=profile,fixtureSha256='a'*64,passed=True,quality=dict(football=dict(totalShots=shots,totalControlledBoxCrossings=entries,onTarget=[1,0])))
    def test_pair(self):
        a=self.row('baseline',2,3);b=self.row('short-match',5,7)
        r=compare([a,b]);self.assertTrue(r['passed']);self.assertEqual(r['delta'],dict(totalShots=3,totalControlledBoxCrossings=4,onTarget=0))
        self.assertFalse(r['automaticPromotion'])
        b['fixtureSha256']='b'*64;self.assertFalse(compare([a,b])['passed'])
    def test_incomplete(self):
        a=self.row('baseline',2,3);b=self.row('short-match',5,None)
        self.assertFalse(compare([a,b])['passed'])
        b['passed']=False;self.assertIsNone(compare([a,b])['delta'])
        with self.assertRaises(ValueError):compare([b,a])
