import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_alpha import match_env
class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.source = {'PATH':'/bin','HOME':'/tmp','TRIBUN_AV_OFFBALL_LANES':'1','TRIBUN_AV_COORDINATED_RUNS':'1','TRIBUN_AV_DUEL_ESCAPE':'1','TRIBUN_NATIVE_NO_DRAW':'1','GF_CAPTURE_PATH':'bad'}
    def test_default(self):
        self.assertEqual(match_env(self.source,'default'),{'PATH':'/bin','HOME':'/tmp'})
    def test_lanes(self):
        self.assertEqual(match_env(self.source,'lanes'),{'PATH':'/bin','HOME':'/tmp','TRIBUN_AV_OFFBALL_LANES':'1','TRIBUN_AV_COORDINATED_RUNS':'0'})
    def test_coordinated(self):
        self.assertEqual(match_env(self.source,'coordinated'),{'PATH':'/bin','HOME':'/tmp','TRIBUN_AV_OFFBALL_LANES':'1','TRIBUN_AV_COORDINATED_RUNS':'1'})
    def test_invalid(self):
        with self.assertRaises(ValueError):match_env(self.source,'unknown')
    def test_no_mutation(self):
        saved=self.source.copy()
        match_env(self.source,'lanes')
        self.assertEqual(self.source,saved)
