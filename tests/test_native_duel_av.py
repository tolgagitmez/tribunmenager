import sys
import json
import tempfile
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_duel_av import trace_counts,compare,KEYS
class DuelTest(unittest.TestCase):
    def evidence(self,m):
        return dict(zip(KEYS,(12,8,5,3,2,1,0,1) if m else (0,)*8))
    def test_trace(self):
        zero=self.evidence(False);x=self.evidence(True)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'trace'
            p.write_text(json.dumps(dict(done=True,attackingDuels=[x,zero])))
            self.assertEqual(trace_counts(p),[x,zero])
            p.write_text(json.dumps(dict(done=True,attackingDuels=[dict(x,beaten=3),zero])))
            with self.assertRaises(ValueError):trace_counts(p)
    def row(self,f,m,entries):
        return dict(passed=True,profile='short-match',attackingDuel=m,controlledCarry=False,boxLane=False,timedPass=False,fixtureSha256=f,duelEvidence=[self.evidence(m),self.evidence(False)],quality=dict(football=dict(totalControlledBoxCrossings=entries,totalShots=5,passes=[20,20],completed=[14,14])))
    def test_review(self):
        a,b=self.row('a',False,2),self.row('a',True,3)
        c,d=self.row('b',False,2),self.row('b',True,3)
        r=compare([(a,b),(c,d)]);self.assertTrue(r['candidateForFurtherReview']);self.assertFalse(r['automaticPromotion'])
        d['duelEvidence'][0].update(attempts=0,beaten=0,cancelled=0)
        r=compare([(a,b),(c,d)]);self.assertTrue(r['passed']);self.assertFalse(r['candidateForFurtherReview'])
