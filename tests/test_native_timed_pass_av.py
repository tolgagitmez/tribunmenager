import sys
import json
import tempfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_timed_pass_av import trace_counts,compare
class TimedPassTest(unittest.TestCase):
    def test_trace(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'trace'
            zero=dict(passes=0,receipts=0,shots=0)
            x=dict(passes=2,receipts=1,shots=1)
            p.write_text(json.dumps(dict(done=False,timedAttacks=[zero,zero]))+'\n'+json.dumps(dict(done=True,timedAttacks=[x,zero]))+'\n')
            self.assertEqual(trace_counts(p),[x,zero])
            p.write_text(json.dumps(dict(done=True,timedAttacks=[dict(passes=0,receipts=1,shots=0),zero])))
            with self.assertRaises(ValueError):trace_counts(p)
    def row(self,f,m,entries):
        return dict(passed=True,profile='short-match',timedPass=m,boxLane=False,fixtureSha256=f,timedEvidence=[dict(passes=int(m),receipts=int(m),shots=0),dict(passes=0,receipts=0,shots=0)],quality=dict(football=dict(totalControlledBoxCrossings=entries,passes=[20,20],completed=[14,14],onTarget=[1,1])))
    def test_compare(self):
        a,b=self.row('a',False,2),self.row('a',True,3)
        c,d=self.row('b',False,2),self.row('b',True,3)
        r=compare([(a,b),(c,d)]);self.assertTrue(r['candidateForFurtherReview']);self.assertFalse(r['automaticPromotion'])
        d['timedEvidence'][0]['receipts']=0
        self.assertFalse(compare([(a,b),(c,d)])['candidateForFurtherReview'])
