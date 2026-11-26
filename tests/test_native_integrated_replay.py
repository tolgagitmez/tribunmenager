import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
import native_integrated_replay as m
import native_av_queue as q
import native_season
from test_native_season import fixture

class IntegratedReplayTest(unittest.TestCase):
    def reports(self):
        configs=[{'seed':1},{'seed':2}]
        reports=[]
        for config in configs:
            f,manifest=fixture()
            reports.append(dict(authoritative=False,verified=True,configSha256=q.digest(config),
                                score=f['score'],season=native_season.candidate(f,manifest)))
        return configs,reports
    def test_two_fixtures_and_isolation(self):
        c,r=self.reports();result=m.replay(c,r)
        self.assertTrue(result['passed']);self.assertEqual(result['appearanceCount'],44)
        self.assertEqual(result['scores'],[[2,1],[2,1]])
        self.assertEqual([x['points'] for x in result['standings']],[3,3,0,0])
        self.assertTrue(result['officialTablesUnchanged'])
    def test_wrong_config_rejected(self):
        c,r=self.reports();r[1]['configSha256']=r[0]['configSha256']
        with self.assertRaises(ValueError):m.replay(c,r)
