import sqlite3
import tempfile
import unittest
from pathlib import Path
from original_scheduled_kickoff_probe import inspect_lineups

class ScheduledKickoffTests(unittest.TestCase):
    def test_saved_lineups_require_both_complete_squads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'save.sqlite'
            xml=''.join(f'<p{i}><role>GK</role><position>0,0</position></p{i}>' for i in range(1,12))
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE teams(id INT,formation_xml TEXT,tactics_xml TEXT)')
                db.executemany('INSERT INTO teams VALUES(?,?,?)',[(1,xml,''),(2,xml,'')])
                db.execute('CREATE TABLE players(id INT,team_id INT,formationorder INT)')
                db.executemany('INSERT INTO players VALUES(?,?,?)',
                    [(team*100+i,team,i) for team in (1,2) for i in range(1,13)])
            fixture=dict(homeTeamId=1,awayTeamId=2)
            before=path.read_bytes()
            rows=inspect_lineups(path,fixture)
            self.assertEqual([r['savedStarterIds'] for r in rows],
                             [list(range(101,112)),list(range(201,212))])
            self.assertEqual(path.read_bytes(),before)
            with sqlite3.connect(path) as db:
                db.execute('DELETE FROM players WHERE team_id=2 AND formationorder>10')
            with self.assertRaisesRegex(ValueError,'Incomplete'):
                inspect_lineups(path,fixture)
            with sqlite3.connect(path) as db:
                db.execute('UPDATE teams SET formation_xml=? WHERE id=1',('<p1/>',))
            with self.assertRaisesRegex(ValueError,'eleven'):
                inspect_lineups(path,fixture)

if __name__=='__main__':
    unittest.main()
