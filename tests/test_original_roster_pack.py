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


    def test_explicit_lineup_and_profile_in_alternate_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Path(tmp)
            original=runtime/'databases/default/database.sqlite'
            original.parent.mkdir(parents=True)
            roles=['GK','LB','CB','CB','RB','DM','CM','AM','LM','RM','CF']
            formation=''.join(f'<p{i+1}><position>0,0</position><role>{role}</role></p{i+1}>' for i,role in enumerate(roles))
            with sqlite3.connect(original) as db:
                db.execute('CREATE TABLE teams(id INTEGER PRIMARY KEY,formation_xml TEXT,tactics_xml TEXT)')
                db.execute('INSERT INTO teams VALUES(1,?,?)',(formation,'unchanged tactics'))
                db.execute('CREATE TABLE players(id INTEGER PRIMARY KEY,team_id INTEGER,nationalteam_id INTEGER,firstname TEXT,lastname TEXT,role TEXT,base_stat REAL,age INTEGER,profile_xml TEXT,formationorder INTEGER UNIQUE)')
                db.executemany('INSERT INTO players VALUES(?,?,?,?,?,?,?,?,?,?)',[(i,1,0,'Old',str(i),'CM',.5,27,'<technical_shot>0.4</technical_shot>',i) for i in range(1,13)])
            before=original.read_bytes()
            rows=[dict(nativePlayerId=i,localIndex=i-1,firstName='New',lastName=str(i),webRole=role,nativeRole=role,webValues={'shooting':90}) for i,role in enumerate(roles+['GK'],1)]
            order=[11,*range(1,11)]
            for bad in ([0]*11,list(range(1,12))):
                with self.assertRaises(ValueError):
                    build_pack(runtime,1,rows,skill_pilot=True,slot_order=bad)
            report=build_pack(runtime,1,rows,skill_pilot=True,slot_order=order)
            self.assertTrue(report['experimentalLineupWritten'])
            self.assertEqual(report['experimentalSkillProfilesWritten'],12)
            self.assertFalse(report['skillEquivalenceVerified'])
            self.assertEqual(original.read_bytes(),before)
            with sqlite3.connect(runtime/'databases/tribun-roster-pilot/database.sqlite') as db:
                self.assertEqual([r[0] for r in db.execute('SELECT id FROM players ORDER BY formationorder')],[12,*range(2,12),1])
                self.assertEqual(db.execute('SELECT formation_xml,tactics_xml FROM teams').fetchone(),(formation,'unchanged tactics'))
                self.assertEqual(db.execute('SELECT base_stat,age,profile_xml FROM players WHERE id=12').fetchone(),(.5,27,'<technical_shot>0.75</technical_shot>'))
