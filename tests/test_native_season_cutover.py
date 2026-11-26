import json
import sqlite3
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
import native_av_queue as q
import native_av_season as ledger
import native_season
import native_season_cutover as cut
import season_state
from live_match import SCHEMA
from test_native_season import fixture

class CutoverTest(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript(SCHEMA+season_state.SCHEMA+q.SCHEMA+"""
            CREATE TABLE teams(league,slot,name,manager);
            CREATE TABLE fixtures(league,round,home,away,kickoff,home_score,away_score,home_yellows,away_yellows,home_reds,away_reds);
            INSERT INTO teams VALUES('L',0,'A','M'),('L',1,'B','N');
            INSERT INTO fixtures VALUES('L',0,0,1,100,NULL,NULL,NULL,NULL,NULL,NULL);
            INSERT INTO live_matches(league,round,home,away,kickoff,config) VALUES('L',0,0,1,100,'{"seed":1}');
        """)
        f,m=fixture();state=native_season.candidate(f,m)
        self.report=dict(authoritative=False,verified=True,configSha256=q.digest({'seed':1}),engine='league-soccer',audioOwnershipVerified=True,controlSource='league-gateway',score=state['score'],season=state)
        with self.db:
            q.sync(self.db,100)
            self.db.execute("UPDATE native_av_jobs SET state='ready',report=?",(q.canonical(self.report),))
            ledger.apply(self.db,('L',0,0,1),self.report)
    def test_projection_leaves_source_unchanged(self):
        r=cut.rehearse(self.db,'L')
        self.assertTrue(r['passed']);self.assertEqual(r['playerAppearances'],22)
        self.assertEqual([s['points'] for s in r['standings']],[3,0])
        self.assertEqual(self.db.execute('SELECT count(*) FROM season_player_state').fetchone()[0],0)
        self.assertIsNone(self.db.execute('SELECT home_score FROM fixtures').fetchone()[0])
    def test_reject_tampering_and_legacy(self):
        with self.db:self.db.execute("UPDATE native_av_jobs SET report='{}'")
        with self.assertRaises(ValueError):cut.rehearse(self.db,'L')
        with self.db:
            self.db.execute("UPDATE native_av_jobs SET report=?",(q.canonical(self.report),))
            self.db.execute('UPDATE fixtures SET home_score=0')
        with self.assertRaises(ValueError):cut.rehearse(self.db,'L')
    def test_reject_partial_round(self):
        with self.db:self.db.execute("INSERT INTO fixtures VALUES('L',0,2,3,100,NULL,NULL,NULL,NULL,NULL,NULL)")
        with self.assertRaises(ValueError):cut.rehearse(self.db,'L')
