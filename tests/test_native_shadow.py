import gzip
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

import native_shadow as n
from live_match import SCHEMA

class ShadowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "test.sqlite3"
        self.key = ("TEST", 0, 0, 1)
        self.config = {"seed": 23, "matchMinutes": 5, "players": [{"id": 1}]}
        with closing(n.connect(self.path)) as db, db:
            db.executescript(SCHEMA + n.SCHEMA)
            db.execute("INSERT INTO live_matches VALUES(?,?,?,?,?,?,NULL)", (*self.key, 1000, json.dumps(self.config)))
            with patch.dict(os.environ, {"TRIBUN_NATIVE_SHADOW":"1", "TRIBUN_NATIVE_SHADOW_PROFILE":"baseline"}):
                n.enqueue(db, self.key, self.config)
                n.enqueue(db, self.key, self.config)

    def runner(self, config, profile, stop):
        self.assertEqual(config, self.config)
        self.assertEqual(profile, "baseline")
        frames = [{"engine":"league-soccer","done":False,"matchMs":0,"score":[0,0]},
                  {"engine":"league-soccer","done":True,"matchMs":5400000,"score":[3,1]}]
        return ("\n".join(map(json.dumps,frames))+"\n").encode(), {"engine":"league-soccer","score":[3,1]}

    def test_exactly_one_job_and_no_authoritative_change(self):
        self.assertTrue(n.process_one(self.path, self.runner))
        self.assertFalse(n.process_one(self.path, self.runner))
        with closing(n.connect(self.path)) as db:
            self.assertIsNone(n.status(db,self.key,1299)["report"])
            self.assertEqual(n.status(db,self.key,1300)["report"]["score"],[3,1])
            self.assertFalse(n.status(db,self.key,1300)["authoritative"])
            self.assertIsNone(db.execute("SELECT final_state FROM live_matches").fetchone()[0])
            self.assertTrue(gzip.decompress(db.execute("SELECT trace FROM native_shadow_matches").fetchone()[0]))
            self.assertEqual(db.execute("SELECT count(*) FROM native_shadow_matches").fetchone()[0],1)

    def test_failure_does_not_fake_result(self):
        self.assertTrue(n.process_one(self.path,lambda *_:(b"bad",{})))
        with closing(n.connect(self.path)) as db:
            s=n.status(db,self.key,2000)
            self.assertEqual(s["state"],"failed")
            self.assertIsNone(s["report"])
            self.assertIsNone(db.execute("SELECT final_state FROM live_matches").fetchone()[0])

    def test_restart_and_config_mismatch(self):
        self.assertIsNotNone(n.claim(self.path))
        self.assertIsNone(n.claim(self.path))
        n.recover(self.path)
        self.assertIsNotNone(n.claim(self.path))
        n.recover(self.path)
        with closing(n.connect(self.path)) as db, db:
            self.assertEqual(n.status(db,self.key,2000)["state"],"failed")
            db.execute("UPDATE native_shadow_matches SET state='queued'")
            db.execute("UPDATE live_matches SET config=?", (json.dumps({"seed":99}),))
        self.assertIsNone(n.claim(self.path))
        with closing(n.connect(self.path)) as db:
            self.assertEqual(n.status(db,self.key,2000)["state"],"failed")

if __name__=="__main__":
    unittest.main()
