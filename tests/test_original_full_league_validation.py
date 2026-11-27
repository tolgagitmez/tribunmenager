import sqlite3
import tempfile
import unittest
from pathlib import Path
from original_full_league_validation import verify
from test_original_results import fixture


class FullLeagueValidationTests(unittest.TestCase):
    def test_history_matches_only_completed_own_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=Path(tmp)
            league=session/'saves'/'test'
            league.mkdir(parents=True)
            dbpath=league/'autosave.sqlite'
            fixture(dbpath)
            with sqlite3.connect(dbpath) as db:
                db.executescript("""
                CREATE TABLE leagues(id INTEGER PRIMARY KEY,name TEXT);
                INSERT INTO leagues VALUES(1,'Test League');
                ALTER TABLE teams ADD COLUMN league_id INTEGER DEFAULT 1;
                ALTER TABLE match_results ADD COLUMN id INTEGER;
                UPDATE match_results SET id=rowid;
                """)
            history=session/'data/saves/match_history.sqlite'
            history.parent.mkdir(parents=True)
            with sqlite3.connect(history) as db:
                db.executescript("""
                CREATE TABLE match_history(id INTEGER PRIMARY KEY,team1_name TEXT,team2_name TEXT,
                    score1 INTEGER,score2 INTEGER,match_time_ms INTEGER,shots1 INTEGER,shots2 INTEGER,
                    shots_on_target1 INTEGER,shots_on_target2 INTEGER,
                    possession1_pct REAL,possession2_pct REAL,passes1 INTEGER,passes2 INTEGER,
                    passes_completed1 INTEGER,passes_completed2 INTEGER,fouls1 INTEGER,fouls2 INTEGER);
                INSERT INTO match_history VALUES(1,'Home','Away',2,1,5400000,6,4,3,2,54.5,45.5,100,80,84,60,2,3);
                """)
            before=dbpath.read_bytes(),history.read_bytes()
            report=verify(session)
            self.assertTrue(report['native3DHistoryMatchesLeagueResult'])
            self.assertEqual(report['history']['passAccuracyPct'],[84.0,75.0])
            self.assertEqual(report['history']['possessionPct'],[54.5,45.5])
            self.assertEqual(report['history']['fouls'],[2,3])
            self.assertEqual((dbpath.read_bytes(),history.read_bytes()),before)
            for column,bad,good in [('possession1_pct',70,54.5),('passes_completed1',101,84),('shots_on_target2',5,2),('fouls1',-1,2)]:
                with sqlite3.connect(history) as db:
                    db.execute(f'UPDATE match_history SET {column}=?',(bad,))
                with self.assertRaisesRegex(ValueError,'Invalid 3D match history'):
                    verify(session)
                with sqlite3.connect(history) as db:
                    db.execute(f'UPDATE match_history SET {column}=?',(good,))
            with sqlite3.connect(history) as db:
                db.execute('UPDATE match_history SET score1=3')
            with self.assertRaisesRegex(ValueError,'score does not match'):
                verify(session)
            with sqlite3.connect(history) as db:
                db.execute('INSERT INTO match_history SELECT 2,team1_name,team2_name,score1,score2,match_time_ms,shots1,shots2,shots_on_target1,shots_on_target2,possession1_pct,possession2_pct,passes1,passes2,passes_completed1,passes_completed2,fouls1,fouls2 FROM match_history WHERE id=1')
            with self.assertRaisesRegex(ValueError,'exactly one finished'):
                verify(session)
