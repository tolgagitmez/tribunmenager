import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from shutil import copy2
from original_engine import digest
from original_fixture_gate import next_native_fixture
from original_fixture_dispatch import claim_fixture
from original_verified_result_ledger import stage_result,provisional_table
from test_original_results import fixture

class VerifiedResultLedgerTests(unittest.TestCase):
    def test_exactly_once_and_provisional_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); root=base/'store'; root.mkdir()
            snap='snapshot-'+'a'*32
            source=root/snap/'test'/'autosave.sqlite'
            source.parent.mkdir(parents=True)
            fixture(source)
            (root/'current').write_text(snap+'\n')
            native=next_native_fixture(source)
            web=dict(league='TEST-2026',round=1,home=20,away=10,kickoff=100)
            reviewed=dict(web,**native,snapshotId=snap,saveName='test',saveSha256=digest(source))
            claim=claim_fixture(root,'test',web,reviewed,100)
            self.assertTrue(claim['claimed'])
            key=claim['fixtureKey']
            session=base/'session'
            saved=session/'saves/test/autosave.sqlite'
            saved.parent.mkdir(parents=True)
            copy2(source,saved)
            history=session/'data/saves/match_history.sqlite'
            history.parent.mkdir(parents=True)
            with sqlite3.connect(history) as db:
                db.executescript("""
                CREATE TABLE match_history(id INTEGER PRIMARY KEY,team1_name TEXT,team2_name TEXT,
                    score1 INTEGER,score2 INTEGER,match_time_ms INTEGER,shots1 INTEGER,shots2 INTEGER,
                    shots_on_target1 INTEGER,shots_on_target2 INTEGER,
                    possession1_pct REAL,possession2_pct REAL,passes1 INTEGER,passes2 INTEGER,
                    passes_completed1 INTEGER,passes_completed2 INTEGER,fouls1 INTEGER,fouls2 INTEGER);
                INSERT INTO match_history VALUES(1,'Away','Home',1,3,5400000,6,4,3,2,54.5,45.5,100,80,84,60,2,3);
                """)
            with self.assertRaises(ValueError):
                stage_result(root,key,session)
            with self.assertRaises(ValueError):
                stage_result(root,key,session,operator_reviewed=True)
            with sqlite3.connect(saved) as db:
                db.execute('UPDATE match_results SET played=1,team1_goals=1,team2_goals=3 WHERE calendar_id=12')
            hashes=(digest(source),digest(saved),digest(history))
            self.assertTrue(stage_result(root,key,session,operator_reviewed=True)['created'])
            self.assertFalse(stage_result(root,key,session,operator_reviewed=True)['created'])
            table=provisional_table(root,'TEST-2026')
            self.assertEqual(table['fixtures'],1)
            self.assertEqual([(r['teamId'],r['played'],r['points'],r['goalDifference']) for r in table['rows']],
                             [(10,1,3,2),(20,1,0,-2)])
            self.assertEqual(provisional_table(root,'TEST-2027')['fixtures'],0)
            self.assertEqual(hashes,(digest(source),digest(saved),digest(history)))
            with sqlite3.connect(saved) as db:
                db.execute('UPDATE match_results SET team2_goals=4 WHERE calendar_id=12')
            with sqlite3.connect(history) as db:
                db.execute('UPDATE match_history SET score2=4')
            with self.assertRaisesRegex(ValueError,'Conflicting'):
                stage_result(root,key,session,operator_reviewed=True)
            self.assertEqual(provisional_table(root,'TEST-2026'),table)

if __name__=='__main__':
    unittest.main()
