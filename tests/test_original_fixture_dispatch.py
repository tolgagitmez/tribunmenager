import sqlite3
import tempfile
import unittest
from pathlib import Path
from original_engine import digest
from original_fixture_dispatch import claim_fixture
from original_fixture_gate import next_native_fixture
from original_saves import locked_store

class DispatchTests(unittest.TestCase):
    def test_durable_single_claim_and_stale_save_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            snap='snapshot-'+'a'*32
            (root/'current').write_text(snap+'\n')
            folder=root/snap/'League'
            folder.mkdir(parents=True)
            path=folder/'autosave.sqlite'
            with sqlite3.connect(path) as db:
                db.executescript("""
                CREATE TABLE settings(team_id INT);
                INSERT INTO settings VALUES(1);
                CREATE TABLE teams(id INT);
                INSERT INTO teams VALUES(1),(2);
                CREATE TABLE calendar(id INT,team1_id INT,team2_id INT,timestamp TEXT);
                INSERT INTO calendar VALUES(1,1,2,'2026-06-01');
                CREATE TABLE match_results(calendar_id INT,played INT);
                """)
            before=path.read_bytes()
            fixture=dict(league='TEST',round=0,home=0,away=1,kickoff=100)
            reviewed={**fixture,**next_native_fixture(path),'snapshotId':snap,'saveName':'League','saveSha256':digest(path)}
            self.assertEqual(claim_fixture(root,'League',fixture,reviewed,99)['reason'],'not-due')
            self.assertFalse((root/'fixture-dispatch.sqlite3').exists())
            self.assertEqual(claim_fixture(root,'League',fixture,{**reviewed,'saveSha256':'stale'},100)['reason'],'stale-reviewed-save')
            with locked_store(root):
                with self.assertRaises(RuntimeError):
                    claim_fixture(root,'League',fixture,reviewed,100)
            result=claim_fixture(root,'League',fixture,reviewed,100)
            self.assertTrue(result['claimed'])
            self.assertFalse(result['automaticLaunch'])
            self.assertEqual(claim_fixture(root,'League',fixture,reviewed,101)['reason'],'already-reserved')
            self.assertEqual(claim_fixture(root,'League',{**fixture,'kickoff':200},{**reviewed,'kickoff':200},200)['reason'],'already-reserved')
            alternate={**fixture,'round':1}
            self.assertEqual(claim_fixture(root,'League',alternate,{**reviewed,'round':1},100)['reason'],'native-fixture-already-reserved')
            self.assertEqual(path.read_bytes(),before)
            with sqlite3.connect(root/'fixture-dispatch.sqlite3') as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM claims').fetchone(),(1,))


    def test_closed_result_candidate_after_explicit_launch(self):
        from unittest.mock import patch
        from original_fixture_dispatch import launch_reviewed
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old='snapshot-'+'a'*32
            new='snapshot-'+'b'*32
            (root/'current').write_text(old+'\n')
            folder=root/old/'League'
            folder.mkdir(parents=True)
            path=folder/'autosave.sqlite'
            with sqlite3.connect(path) as db:
                db.executescript("""
                CREATE TABLE settings(team_id INT);
                INSERT INTO settings VALUES(1);
                CREATE TABLE teams(id INT);
                INSERT INTO teams VALUES(1),(2);
                CREATE TABLE calendar(id INT,team1_id INT,team2_id INT,timestamp TEXT);
                INSERT INTO calendar VALUES(1,1,2,'2026-06-01');
                CREATE TABLE match_results(calendar_id INT,played INT,team1_id INT,team2_id INT,team1_goals INT,team2_goals INT);
                """)
            before=path.read_bytes()
            fixture=dict(league='TEST',round=0,home=0,away=1,kickoff=100)
            reviewed={**fixture,**next_native_fixture(path),'snapshotId':old,'saveName':'League','saveSha256':digest(path)}
            def fake_session(build,env,report,store):
                self.assertEqual(store,root)
                with self.assertRaises(RuntimeError):
                    claim_fixture(root,'League',fixture,reviewed,100)
                shutil.copytree(root/old,root/new)
                with sqlite3.connect(root/new/'League/autosave.sqlite') as db:
                    db.execute('INSERT INTO match_results VALUES(1,1,1,2,3,1)')
                (root/'current').write_text(new+'\n')
                return 0
            with patch('original_engine.launch_session',side_effect=fake_session) as launch:
                outcome=launch_reviewed(root,None,{},'League',fixture,reviewed,100)
                self.assertEqual(launch.call_count,1)
                self.assertTrue(outcome['desktopSessionLaunched'])
                self.assertFalse(outcome['automaticKickoff'])
                self.assertEqual(outcome['reconciliation']['reason'],'native-result-candidate')
                self.assertEqual(outcome['reconciliation']['homeGoals'],3)
                self.assertFalse(outcome['reconciliation']['renderedMatchVerified'])
                self.assertFalse(outcome['reconciliation']['scoreWritten'])
                self.assertFalse(launch_reviewed(root,None,{},'League',fixture,reviewed,100)['claimed'])
                self.assertEqual(launch.call_count,1)
            self.assertEqual(path.read_bytes(),before)
