import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from original_catalog import catalog, tactics, formation


class OriginalCatalogTests(unittest.TestCase):
    def test_native_catalog_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'database.sqlite'
            with sqlite3.connect(path) as db:
                db.executescript("""
                CREATE TABLE teams(id INTEGER PRIMARY KEY,name TEXT,formation_xml TEXT,tactics_xml TEXT);
                CREATE TABLE players(id INTEGER PRIMARY KEY,team_id INTEGER,firstname TEXT,lastname TEXT,role TEXT,formationorder INTEGER);
                INSERT INTO teams VALUES(1,'Club','<p1><position>-1,0</position><role>GK</role></p1>','<dribble_offensiveness>0.7</dribble_offensiveness>');
                INSERT INTO teams VALUES(2,'Other','','');
                INSERT INTO players VALUES(5,1,'A','B','CF',2),(4,1,'C','D','GK',1),(6,2,'E','F','CB',1);
                """)
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(len(catalog(path)['teams']),2)
            result=catalog(path,1)
            self.assertEqual([p['id'] for p in result['players']],[4,5])
            self.assertEqual(result['formation'][0]['rawPosition'],[-1,0])
            self.assertFalse(result['representsLiveLineup'])
            self.assertTrue(result['readOnly'])
            self.assertEqual(result['tactics'][0]['value'],.7)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
            with self.assertRaises(ValueError):
                catalog(path,3)

    def test_only_documented_defaults(self):
        result={x['key']:x for x in tactics('<team_pressure>0.3</team_pressure>')}
        self.assertEqual(set(result),{'team_pressure','support_distance','counter_attack'})
        self.assertEqual(result['team_pressure']['value'],.3)
        self.assertEqual(result['counter_attack']['source'],'upstream-memory-default')

    def test_invalid_tactic_xml(self):
        for raw in ('<team_pressure>nan</team_pressure>',
                    '<team_pressure>0.5</team_pressure><team_pressure>0.7</team_pressure>',
                    '<!DOCTYPE root>'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                tactics(raw)

    def test_formation_invalid_coordinate(self):
        with self.assertRaises(ValueError):
            formation('<p1><position>nan,0</position></p1>')


if __name__=='__main__':
    unittest.main()
