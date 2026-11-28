import sqlite3
import tempfile
import unittest
from pathlib import Path
import shutil

from original_custom_database_probe import prepare_pack,verify,PACK,MARKER


class CustomDatabaseProbeTests(unittest.TestCase):
    def test_separate_pack_and_native_save_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Path(tmp)
            original=runtime/'databases/default/database.sqlite'
            original.parent.mkdir(parents=True)
            with sqlite3.connect(original) as db:
                db.executescript("""
                CREATE TABLE teams(id INTEGER PRIMARY KEY,name TEXT);
                INSERT INTO teams VALUES(1,'Club');
                CREATE TABLE players(id INTEGER PRIMARY KEY,team_id INTEGER,firstname TEXT,lastname TEXT,base_stat REAL);
                INSERT INTO players VALUES(11,1,'First','Last',0.75);
                """)
            before=original.read_bytes()
            expected=prepare_pack(runtime)
            self.assertEqual(original.read_bytes(),before)
            alternate=runtime/'databases'/PACK/'database.sqlite'
            with sqlite3.connect(alternate) as db:
                self.assertEqual(db.execute('SELECT lastname,base_stat FROM players').fetchone(),(MARKER,0.75))
            save=runtime/'saves'/'test'/'autosave.sqlite'
            save.parent.mkdir(parents=True)
            shutil.copyfile(alternate,save)
            with sqlite3.connect(save) as db:
                db.executescript('CREATE TABLE settings(id INTEGER); INSERT INTO settings VALUES(1); CREATE TABLE calendar(id INTEGER); INSERT INTO calendar VALUES(1);')
            snapshot=save.read_bytes()
            self.assertTrue(verify(runtime,expected)['customDatabasePlayerRoundtripVerified'])
            self.assertEqual(save.read_bytes(),snapshot)
            with sqlite3.connect(save) as db:
                db.execute("UPDATE players SET lastname='Last'")
            with self.assertRaisesRegex(ValueError,'did not retain'):
                verify(runtime,expected)
