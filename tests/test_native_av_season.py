import sqlite3
import unittest
import native_av_season as s
import native_season
from test_native_season import fixture
import season_state

class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.row_factory=sqlite3.Row
        self.db.executescript(season_state.SCHEMA+s.SCHEMA+"""
          CREATE TABLE fixtures(league,round,home,away,home_score);
          INSERT INTO fixtures VALUES('L',0,0,1,NULL),('L',1,0,1,NULL);
        """)
        self.addCleanup(self.db.close)
        f,m=fixture();side=native_season.candidate(f,m);side['seasonPreview']=native_season.preview(side)
        self.report=dict(authoritative=False,verified=True,score=[2,1],season=s.verify_candidate(f,m,side))
    def test_points_and_player_isolation(self):
        with self.db:
            self.assertTrue(s.apply(self.db,('L',0,0,1),self.report))
            self.assertFalse(s.apply(self.db,('L',0,0,1),self.report))
        self.assertEqual(s.standings(self.db,'L')[0]['points'],3)
        row=self.db.execute("SELECT * FROM native_av_season_player_state WHERE slot=0 AND player_key='uid:club-0-0'").fetchone()
        self.assertEqual(row['appearances'],1);self.assertEqual(row['suspension_until_round'],2)
        self.assertEqual(self.db.execute('SELECT count(*) FROM season_player_state').fetchone()[0],0)
        self.assertIsNone(self.db.execute('SELECT home_score FROM fixtures').fetchone()[0])
    def test_rollback_and_order(self):
        with self.assertRaises(ValueError):
            with self.db:s.apply(self.db,('L',1,0,1),self.report)
        with self.assertRaises(RuntimeError):
            with self.db:
                s.apply(self.db,('L',0,0,1),self.report)
                raise RuntimeError('rollback')
        self.assertEqual(s.standings(self.db,'L'),[])
        self.assertEqual(self.db.execute('SELECT count(*) FROM native_av_season_player_state').fetchone()[0],0)
    def test_tampered_sidecar(self):
        f,m=fixture();side=native_season.candidate(f,m);side['seasonPreview']=native_season.preview(side)
        side['appearances'][0]['minutes']=89
        with self.assertRaises(ValueError):s.verify_candidate(f,m,side)
