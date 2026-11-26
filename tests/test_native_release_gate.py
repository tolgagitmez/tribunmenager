import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_release_gate import evaluate
from unittest.mock import patch
class GateTest(unittest.TestCase):
    def setUp(self):
        self.host={'host':{},'affinity':[0,1],'limitsSha256':'x','cgroup':'x'}
        self.runtime={'manifestSha256':'a'*64,'binarySha256':'b'*64}
        self.commit='c'*40
    def wrap(self,kind,row):
        return {**row,'releaseBinding':dict(schema=1,kind=kind,candidateCommit=self.commit,runtime=self.runtime,bootHost=self.host,observedAt=1000)}
    def e2e(self):
        return self.wrap('league-e2e',dict(passed=True,nativeOnly=True,authoritative=False,leagueScreenVerified=True,officialTablesUnchanged=True,
            duplicateRejected=True,fixtureCount=1,coverage=.99,appearanceCount=22,commandHistory=dict(verified=True,submitted=[1,1],applied=[1,1])))
    def test_missing_blocks(self):
        r=evaluate({},self.commit,self.runtime,self.host,1001)
        self.assertFalse(r['privateRoundReviewEligible']);self.assertFalse(r['productionEnabled'])
    def test_private_round_not_production_even_with_evidence(self):
        reports={'league-e2e':self.e2e(),'capacity':self.wrap('capacity',{})}
        with patch('native_release_gate.admitted_slots',return_value=4):
            r=evaluate(reports,self.commit,self.runtime,self.host,1001)
            self.assertTrue(r['privateRoundReviewEligible']);self.assertFalse(r['productionEnabled'])
            reports['league-e2e']['releaseBinding']['candidateCommit']='d'*40
            self.assertFalse(evaluate(reports,self.commit,self.runtime,self.host,1001)['privateRoundReviewEligible'])
    def test_two_slots_insufficient_and_stale(self):
        reports={'league-e2e':self.e2e(),'capacity':self.wrap('capacity',{})}
        with patch('native_release_gate.admitted_slots',return_value=2):
            self.assertFalse(evaluate(reports,self.commit,self.runtime,self.host,1001)['privateRoundReviewEligible'])
        self.assertFalse(evaluate(reports,self.commit,self.runtime,self.host,5001)['checks']['league-e2eBound'])
