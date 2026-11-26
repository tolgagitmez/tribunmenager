import sys
import json
import tempfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_controlled_carry_av import trace_counts,compare
class CarryTest(unittest.TestCase):
    def test_trace(self):
        zero=dict(attempts=0,progressed=0,lost=0,cancelled=0)
        x=dict(attempts=2,progressed=1,lost=0,cancelled=1)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'trace'
            p.write_text(json.dumps(dict(done=True,controlledCarries=[x,zero])))
            self.assertEqual(trace_counts(p),[x,zero])
            p.write_text(json.dumps(dict(done=True,controlledCarries=[dict(x,progressed=3),zero])))
            with self.assertRaises(ValueError):trace_counts(p)
    def row(self,f,m,entries):
        return dict(passed=True,profile='short-match',controlledCarry=m,boxLane=False,timedPass=False,fixtureSha256=f,carryEvidence=[dict(attempts=int(m),progressed=int(m),lost=0,cancelled=0),dict(attempts=0,progressed=0,lost=0,cancelled=0)],quality=dict(football=dict(totalControlledBoxCrossings=entries,totalShots=5,passes=[20,20],completed=[14,14])))
    def test_review(self):
        a,b=self.row('a',False,2),self.row('a',True,3)
        c,d=self.row('b',False,2),self.row('b',True,3)
        r=compare([(a,b),(c,d)]);self.assertTrue(r['candidateForFurtherReview']);self.assertFalse(r['automaticPromotion'])
        d['carryEvidence'][0].update(progressed=0,lost=1)
        self.assertFalse(compare([(a,b),(c,d)])['candidateForFurtherReview'])
