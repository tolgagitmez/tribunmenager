import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_host_budget import summarize
class BudgetTest(unittest.TestCase):
    def test_failure_retains_wall_time(self):
        r=summarize({'dual-baseline':{'passed':False,'requestedMatches':2,'matches':[{'observedWallSeconds':666,'browserExit':1},{'observedWallSeconds':705,'browserExit':1}]}})
        self.assertFalse(r['productionQualified'])
        self.assertFalse(r['trials'][0]['passed'])
        self.assertEqual(r['trials'][0]['realMatchSeconds'],[666,705])
