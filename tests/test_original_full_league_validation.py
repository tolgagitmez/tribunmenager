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
            from original_match_history import read_recent
            recent=read_recent(history)
            self.assertEqual(len(recent['records']),2)
            self.assertFalse(recent['linkedToLeagueFixtures'])
            with sqlite3.connect(history) as db:
                db.execute('UPDATE match_history SET passes_completed1=1000 WHERE id=2')
            recent=read_recent(history)
            self.assertEqual(recent['skipped'],1)
            self.assertEqual(len(recent['records']),1)


    def test_history_persists_only_after_clean_exit(self):
        from original_match_history import HISTORY_PATH,STORED_NAME,restore_history,commit_history,read_recent
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            root=base/'store'
            first=base/'first'
            second=base/'second'
            root.mkdir()
            dbpath=first/HISTORY_PATH
            dbpath.parent.mkdir(parents=True)
            with sqlite3.connect(dbpath) as db:
                db.executescript("""
                CREATE TABLE match_history(id INTEGER PRIMARY KEY,team1_name TEXT,team2_name TEXT,
                    score1 INTEGER,score2 INTEGER,match_time_ms INTEGER,shots1 INTEGER,shots2 INTEGER,
                    shots_on_target1 INTEGER,shots_on_target2 INTEGER,
                    possession1_pct REAL,possession2_pct REAL,passes1 INTEGER,passes2 INTEGER,
                    passes_completed1 INTEGER,passes_completed2 INTEGER,fouls1 INTEGER,fouls2 INTEGER);
                INSERT INTO match_history VALUES(1,'Home','Away',2,1,5400000,6,4,3,2,54.5,45.5,100,80,84,60,2,3);
                """)
            (dbpath.parent/'unrelated.config').write_text('not persisted')
            before=dbpath.read_bytes()
            self.assertTrue(commit_history(root,first,0))
            self.assertEqual((root/STORED_NAME).read_bytes(),before)
            self.assertTrue(restore_history(root,second))
            restored=second/HISTORY_PATH
            self.assertEqual(restored.read_bytes(),before)
            self.assertFalse((restored.parent/'unrelated.config').exists())
            with sqlite3.connect(restored) as db:
                db.execute('INSERT INTO match_history SELECT 2,team1_name,team2_name,score1,score2,match_time_ms,shots1,shots2,shots_on_target1,shots_on_target2,possession1_pct,possession2_pct,passes1,passes2,passes_completed1,passes_completed2,fouls1,fouls2 FROM match_history WHERE id=1')
            self.assertFalse(commit_history(root,second,1))
            self.assertEqual((root/STORED_NAME).read_bytes(),before)
            self.assertTrue(commit_history(root,second,0))
            self.assertEqual(len(read_recent(root/STORED_NAME)['records']),2)
            retained=(root/STORED_NAME).read_bytes()
            restored.write_bytes(b'not sqlite')
            with self.assertRaises(sqlite3.Error):
                commit_history(root,second,0)
            self.assertEqual((root/STORED_NAME).read_bytes(),retained)


    def test_team_performance_uses_weighted_rates_and_exact_names(self):
        from original_match_history import summarize_teams,validate
        rows=[
            ('Home','Away',2,1,5400000,10,4,5,2,60,40,100,80,90,60,2,3),
            ('Other','Home',0,0,5400000,0,2,0,2,45,55,20,10,10,5,0,1),
            ('Home','Home',1,1,5400000,8,6,3,4,50,50,50,50,40,40,1,1),
        ]
        stats=summarize_teams([validate(row) for row in rows])
        self.assertEqual(stats['sampleMatches'],2)
        self.assertEqual(stats['excludedSameNameMatches'],1)
        teams={row['teamName']:row for row in stats['teams']}
        home=teams['Home']
        self.assertEqual((home['played'],home['won'],home['drawn'],home['lost']),(2,1,1,0))
        self.assertEqual(home['shotsPerMatch'],6)
        self.assertEqual(home['goalsPerMatch'],1)
        self.assertEqual(home['shotAccuracyPct'],58.33)
        self.assertEqual(home['passAccuracyPct'],86.36)
        self.assertEqual(home['meanPossessionPct'],57.5)
        self.assertIsNone(teams['Other']['shotAccuracyPct'])
        self.assertEqual(summarize_teams([])['teams'],[])


    def test_last_five_trends_chronological_and_side_correct(self):
        from original_match_history import recent_team_matches,validate
        records=[]
        for i in range(7,0,-1):
            # Most recent first, alternate home/away. Two oldest are excluded.
            if i%2:
                row=('Club','Opponent '+str(i),i,0,5400000,10,4,5,2,60,40,100,80,90,60,2,3)
            else:
                row=('Opponent '+str(i),'Club',0,i,5400000,4,10,2,5,40,60,80,100,60,90,3,2)
            records.append(validate(row))
        records.insert(0,validate(('Club','Club',9,9,5400000,10,10,5,5,50,50,80,80,60,60,1,1)))
        teams={t['teamName']:t['matches'] for t in recent_team_matches(records)}
        club=teams['Club']
        self.assertEqual([m['goalsFor'] for m in club],[3,4,5,6,7])
        self.assertEqual([m['home'] for m in club],[True,False,True,False,True])
        self.assertTrue(all(m['shots']==10 and m['shotsAgainst']==4 and m['shotsOnTargetAgainst']==2 for m in club))
        self.assertEqual([m['opponent'] for m in club],['Opponent '+str(i) for i in range(3,8)])
        self.assertEqual(len(teams['Opponent 1']),1)
        self.assertEqual(recent_team_matches([]),[])


    def test_restored_fixture_requires_one_new_exact_result_and_fresh_full_history(self):
        from original_full_league_validation import completed_own,verify_restored_fixture
        from original_fixture_gate import next_native_fixture
        with tempfile.TemporaryDirectory() as tmp:
            session=Path(tmp)
            league=session/'saves'/'test'
            league.mkdir(parents=True)
            dbpath=league/'autosave.sqlite'
            fixture(dbpath)
            expected=next_native_fixture(dbpath)
            before=completed_own(dbpath)
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
            with self.assertRaisesRegex(ValueError,'exactly the reserved'):
                verify_restored_fixture(session,expected,before)
            with sqlite3.connect(dbpath) as db:
                db.execute('UPDATE match_results SET played=1,team1_goals=1,team2_goals=3 WHERE calendar_id=12')
            saved_bytes=dbpath.read_bytes(),history.read_bytes()
            report=verify_restored_fixture(session,expected,before)
            self.assertTrue(report['reservedFixtureResultVerified'])
            self.assertEqual(report['previousOwnResultsPreserved'],1)
            self.assertEqual(report['expectedFixture']['nativeFixtureId'],12)
            self.assertFalse(report['automaticLeagueImport'])
            self.assertEqual((dbpath.read_bytes(),history.read_bytes()),saved_bytes)
            with sqlite3.connect(history) as db:
                db.execute('UPDATE match_history SET match_time_ms=10000')
            with self.assertRaisesRegex(ValueError,'full regulation'):
                verify_restored_fixture(session,expected,before)
            with sqlite3.connect(history) as db:
                db.execute('UPDATE match_history SET match_time_ms=5400000,score1=2')
            with self.assertRaisesRegex(ValueError,'does not match reserved'):
                verify_restored_fixture(session,expected,before)
            with sqlite3.connect(history) as db:
                db.execute('UPDATE match_history SET score1=1')
            with sqlite3.connect(dbpath) as db:
                db.execute('UPDATE match_results SET team1_goals=5 WHERE calendar_id=10')
            with self.assertRaisesRegex(ValueError,'Previously completed'):
                verify_restored_fixture(session,expected,before)
