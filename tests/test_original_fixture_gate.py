import sqlite3
import tempfile
import unittest
from pathlib import Path
from original_fixture_gate import next_native_fixture,eligibility

class FixtureGateTests(unittest.TestCase):
    def test_upstream_next_fixture_and_read_only_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'autosave.sqlite'
            with sqlite3.connect(path) as db:
                db.executescript("""
                    CREATE TABLE settings(team_id INT);
                    INSERT INTO settings VALUES(1);
                    CREATE TABLE teams(id INT);
                    INSERT INTO teams VALUES(1),(2),(3);
                    CREATE TABLE calendar(id INT,team1_id INT,team2_id INT,timestamp TEXT);
                    INSERT INTO calendar VALUES(1,1,2,'2026-06-01'),(2,2,1,'2026-06-02'),(3,1,3,'2026-06-03');
                    CREATE TABLE match_results(calendar_id INT,played INT);
                    INSERT INTO match_results VALUES(1,1);
                """)
            before=path.read_bytes()
            native=next_native_fixture(path)
            self.assertEqual(native['nativeFixtureId'],2)
            self.assertEqual(native['homeTeamId'],2)
            self.assertEqual(path.read_bytes(),before)
            fixture=dict(league='TEST',round=1,home=2,away=1,kickoff=100)
            expected={**fixture,**native}
            self.assertEqual(eligibility(fixture,expected,native,99)['reason'],'not-due')
            result=eligibility(fixture,expected,native,100)
            self.assertTrue(result['eligible'])
            self.assertFalse(result['automaticLaunch'])
            self.assertFalse(result['scoreWritten'])
            self.assertEqual(eligibility(fixture,expected,{**native,'homeTeamId':3},100)['reason'],'native-fixture-mismatch')
            self.assertEqual(eligibility({**fixture,'home_score':0},expected,native,100)['reason'],'already-scored')
            self.assertEqual(eligibility({**fixture,'round':2},expected,native,100)['reason'],'web-fixture-mismatch')
            with sqlite3.connect(path) as db:
                db.execute("UPDATE calendar SET timestamp='2026-06-02' WHERE id=3")
            with self.assertRaises(ValueError):
                next_native_fixture(path)
