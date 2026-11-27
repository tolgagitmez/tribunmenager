import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from original_results import read_save, collect, store


def fixture(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE settings(id INTEGER PRIMARY KEY, team_id INTEGER);
        CREATE TABLE teams(id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE calendar(id INTEGER PRIMARY KEY, team1_id INTEGER, team2_id INTEGER, timestamp TEXT);
        CREATE TABLE match_results(calendar_id INTEGER, team1_id INTEGER, team2_id INTEGER,
            team1_goals INTEGER, team2_goals INTEGER, played INTEGER);
        INSERT INTO settings VALUES(1,1);
        INSERT INTO teams VALUES(1,'Home'),(2,'Away'),(3,'Other');
        INSERT INTO calendar VALUES(10,1,2,'2026-11-27'),(11,2,3,'2026-11-28'),(12,2,1,'2026-11-29');
        INSERT INTO match_results VALUES(10,1,2,2,1,1),(11,2,3,3,0,1),(12,2,1,0,0,0);
        """)


class OriginalResultsTests(unittest.TestCase):
    def test_only_completed_own_team_and_no_write(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'autosave.sqlite'
            fixture(path)
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            result=read_save(path)
            self.assertEqual(len(result['results']),1)
            self.assertEqual(result['results'][0]['homeGoals'],2)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)


    def test_managed_team_and_pending_fixtures_are_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'autosave.sqlite'
            fixture(path)
            with sqlite3.connect(path) as db:
                db.execute("INSERT INTO calendar VALUES(13,1,3,'2026-11-30')")
            before=path.read_bytes()
            result=read_save(path)
            self.assertEqual(result['managedTeam'],{'id':1,'name':'Home'})
            self.assertEqual([x['nativeFixtureId'] for x in result['pendingFixtures']],[12,13])
            self.assertNotIn('homeGoals',result['pendingFixtures'][0])
            self.assertFalse(result['pendingTruncated'])
            self.assertEqual(path.read_bytes(),before)

    def test_ambiguous_managed_team_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'autosave.sqlite'
            fixture(path)
            with sqlite3.connect(path) as db:
                db.execute('INSERT INTO settings VALUES(2,2)')
            with self.assertRaises(ValueError):
                read_save(path)


    def test_native_standings_points_goal_difference_and_form(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'autosave.sqlite'
            fixture(path)
            with sqlite3.connect(path) as db:
                db.executescript("""
                CREATE TABLE leagues(id INTEGER PRIMARY KEY,name TEXT);
                INSERT INTO leagues VALUES(1,'Test League'),(2,'Other League');
                ALTER TABLE teams ADD COLUMN league_id INTEGER DEFAULT 1;
                INSERT INTO teams VALUES(4,'Idle',1),(5,'External',2);
                ALTER TABLE match_results ADD COLUMN id INTEGER;
                UPDATE match_results SET id=rowid;
                INSERT INTO calendar VALUES(13,1,5,'2026-11-30');
                INSERT INTO match_results VALUES(13,1,5,0,0,1,4);
                """)
            before=path.read_bytes()
            table=read_save(path)['standings']
            self.assertEqual(table['league'],'Test League')
            self.assertEqual([r['name'] for r in table['rows']],['Home','Away','Idle','Other'])
            home,away,idle,other=table['rows']
            self.assertEqual((home['played'],home['won'],home['drawn'],home['points'],home['goalDifference'],home['form']),(2,1,1,4,1,'WD'))
            self.assertEqual((away['points'],away['goalDifference'],away['form']),(3,2,'LW'))
            self.assertEqual((idle['points'],idle['played'],idle['form']),(0,0,''))
            self.assertTrue(home['managed'])
            self.assertTrue(table['includesAllPlayedCompetitions'])
            self.assertEqual(path.read_bytes(),before)

    def test_missing_standings_schema_does_not_hide_valid_results(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'autosave.sqlite'
            fixture(path)
            result=read_save(path)
            self.assertIsNone(result['standings'])
            self.assertEqual(len(result['results']),1)

    def test_unsettled_journal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'autosave.sqlite'
            fixture(path)
            Path(str(path)+'-wal').write_bytes(b'pending')
            with self.assertRaises(ValueError):
                read_save(path)

    def test_ambiguous_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'autosave.sqlite'
            fixture(path)
            with sqlite3.connect(path) as db:
                db.execute('INSERT INTO match_results VALUES(10,1,2,3,0,1)')
            with self.assertRaises(ValueError):
                read_save(path)

    def test_report_only_normal_exit_and_no_league_import(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            save=root/'saves'/'league'
            save.mkdir(parents=True)
            fixture(save/'autosave.sqlite')
            self.assertEqual(collect(root,'rev',1)['saves'],[])
            result=collect(root,'rev',0)
            self.assertFalse(result['automaticLeagueImport'])
            self.assertFalse(result['provesRenderedMatch'])
            self.assertEqual(len(result['saves']),1)
            path=root/'report.json'
            store(result,path)
            self.assertEqual(json.loads(path.read_text()),result)


if __name__=='__main__':
    unittest.main()
