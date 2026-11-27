import sqlite3
import tempfile
import unittest
from pathlib import Path

from original_roster_pack import build_pack


class RosterPackTests(unittest.TestCase):
    def test_explicit_complete_mapping_preserves_native_skill_and_other_teams(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Path(tmp)
            original=runtime/'databases/default/database.sqlite'
            original.parent.mkdir(parents=True)
            with sqlite3.connect(original) as db:
                db.execute('CREATE TABLE players(id INTEGER PRIMARY KEY,team_id INTEGER,firstname TEXT,lastname TEXT,role TEXT,base_stat REAL,profile_xml TEXT,formationorder INTEGER)')
                db.executemany('INSERT INTO players VALUES(?,?,?,?,?,?,?,?)',[(i,1 if i<=11 else 2,'Old',str(i),'CM',0.75,'profile',i) for i in range(1,13)])
            before=original.read_bytes()
            rows=[dict(nativePlayerId=i,localIndex=i-1,firstName='New',lastName=str(i),webRole='LW' if i==1 else 'CM',nativeRole='LM' if i==1 else 'CM') for i in range(1,12)]
            for bad in (rows[:-1],[{**rows[0],'nativePlayerId':12}]+rows[1:],[{**rows[0],'nativeRole':'CF'}]+rows[1:]):
                with self.assertRaises(ValueError):
                    build_pack(runtime,1,bad)
                self.assertFalse((runtime/'databases/tribun-roster-pilot').exists())
            report=build_pack(runtime,1,rows)
            self.assertEqual(report['mappedPlayers'],11)
            self.assertFalse(report['nativeSkillsImported'])
            self.assertEqual(original.read_bytes(),before)
            with sqlite3.connect(runtime/'databases/tribun-roster-pilot/database.sqlite') as db:
                self.assertEqual(db.execute('SELECT firstname,lastname,role,base_stat,profile_xml,formationorder FROM players WHERE id=1').fetchone(),('New','1','LM',0.75,'profile',1))
                self.assertEqual(db.execute('SELECT firstname FROM players WHERE id=12').fetchone(),('Old',))
            with self.assertRaises(ValueError):
                build_pack(runtime,1,rows)
