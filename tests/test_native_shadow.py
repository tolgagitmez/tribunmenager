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
        frames = [{"engine":"league-soccer","done":False,"elapsedMs":100,"matchMs":0,"score":[0,0]},
                  {"engine":"league-soccer","done":True,"elapsedMs":200,"matchMs":5400000,"score":[3,1]}]
        return ("\n".join(map(json.dumps,frames))+"\n").encode(), {"engine":"league-soccer","score":[3,1]}

    def test_stage100_diagnostic_flags_never_leak_to_league_child(self):
        source={"PATH":"/bin","TRIBUN_NATIVE_RUNTIME":"/tmp/runtime","TRIBUN_NATIVE_MATCH_PACE":"1",
                "TRIBUN_NATIVE_COLLECTIVE_AI":"1","TRIBUN_NATIVE_KEEPER_AI":"1",
                "TRIBUN_NATIVE_FUTURE_EXPERIMENT":"1","TRIBUN_NATIVE_FIXED_DURATION":"1",
                "TRIBUN_LEAGUE_SOCCER_COMMAND_DIR":"/tmp/untrusted","TRIBUN_LEAGUE_SOCCER_FIXTURE":"/tmp/other"}
        env=n.isolated_native_environment(source,"baseline")
        self.assertEqual(env,{"PATH":"/bin","TRIBUN_LEAGUE_SOCCER_ATTACK":"baseline"})
        self.assertEqual(source["TRIBUN_NATIVE_MATCH_PACE"],"1")

    def test_exactly_one_job_and_no_authoritative_change(self):
        with patch.object(n.time,'time',return_value=1000):
            self.assertTrue(n.process_one(self.path, self.runner))
        self.assertFalse(n.process_one(self.path, self.runner))
        with closing(n.connect(self.path)) as db:
            self.assertIsNone(n.status(db,self.key,1299)["report"])
            self.assertEqual(n.status(db,self.key,1300)["report"]["score"],[3,1])
            self.assertFalse(n.status(db,self.key,1300)["authoritative"])
            self.assertIsNone(db.execute("SELECT final_state FROM live_matches").fetchone()[0])
            self.assertTrue(gzip.decompress(db.execute("SELECT trace FROM native_shadow_matches").fetchone()[0]))
            self.assertEqual(db.execute("SELECT count(*) FROM native_shadow_matches").fetchone()[0],1)

    def test_shared_broadcast_starts_when_ready_and_hides_final(self):
        with patch.object(n.time,'time',return_value=1200):
            self.assertTrue(n.process_one(self.path,self.runner))
        with closing(n.connect(self.path)) as db:
            self.assertIsNone(n.broadcast(db,self.key,1199)["frame"])
            a=n.broadcast(db,self.key,1300)
            self.assertEqual(a,n.broadcast(db,self.key,1300))
            self.assertEqual(a["frame"]["score"],[0,0])
            self.assertEqual(a["elapsedMs"],100000)
            self.assertIsNone(n.status(db,self.key,1499)["report"])
            self.assertFalse(n.broadcast(db,self.key,1499.999)["frame"]["done"])
            end=n.broadcast(db,self.key,1500)
            self.assertEqual(end["phase"],"finished")
            self.assertEqual(end["frame"]["score"],[3,1])
            self.assertEqual(n.status(db,self.key,1500)["report"]["score"],[3,1])
            self.assertEqual(db.execute("SELECT count(*) FROM native_shadow_frames").fetchone()[0],2)

    def test_failure_does_not_fake_result(self):
        self.assertTrue(n.process_one(self.path,lambda *_:(b"bad",{})))
        with closing(n.connect(self.path)) as db:
            s=n.status(db,self.key,2000)
            self.assertEqual(s["state"],"failed")
            self.assertIsNone(s["report"])
            self.assertIsNone(db.execute("SELECT final_state FROM live_matches").fetchone()[0])

    def test_stale_completion_and_failure_cannot_touch_new_attempt(self):
        old=n.claim(self.path)
        n.recover(self.path)
        new=n.claim(self.path)
        self.assertEqual(old[4],1)
        self.assertEqual(new[4],2)
        raw,report=self.runner(self.config,"baseline",None)
        self.assertFalse(n.commit_shadow_result(self.path,*old[:3],old[4],raw,report))
        self.assertFalse(n.fail_shadow_attempt(self.path,*old[:3],old[4],"late error"))
        with closing(n.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT state,attempts FROM native_shadow_matches").fetchone(),("running",2))
            self.assertEqual(db.execute("SELECT count(*) FROM native_shadow_frames").fetchone()[0],0)
        self.assertTrue(n.commit_shadow_result(self.path,*new[:3],new[4],raw,report))
        self.assertFalse(n.commit_shadow_result(self.path,*old[:3],old[4],raw,report))
        self.assertFalse(n.fail_shadow_attempt(self.path,*old[:3],old[4],"late error"))
        with closing(n.connect(self.path)) as db:
            row=db.execute("SELECT state,report,trace_sha FROM native_shadow_matches").fetchone()
            self.assertEqual(row[0],"ready")
            bound=json.loads(row[1])
            self.assertEqual(bound["provenance"],{"attempt":2,"configSha256":new[1],"profile":"baseline","traceSha256":row[2]})
            self.assertFalse(bound["authoritative"])
            self.assertEqual(db.execute("SELECT count(*) FROM native_shadow_frames").fetchone()[0],2)
            self.assertIsNone(db.execute("SELECT final_state FROM live_matches").fetchone()[0])

    def test_config_mutation_during_run_rejected(self):
        def runner(config,profile,stop):
            with closing(n.connect(self.path)) as db, db:
                db.execute("UPDATE live_matches SET config=?", (json.dumps({"seed":99}),))
            return self.runner(config,profile,stop)
        self.assertTrue(n.process_one(self.path,runner))
        with closing(n.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT state FROM native_shadow_matches").fetchone()[0],"failed")
            self.assertEqual(db.execute("SELECT count(*) FROM native_shadow_frames").fetchone()[0],0)

    def test_frame_index_rollback(self):
        job=n.claim(self.path)
        raw,report=self.runner(self.config,"baseline",None)
        with patch.object(n,"index_frames",side_effect=RuntimeError("simulated write failure")):
            with self.assertRaises(RuntimeError):
                n.commit_shadow_result(self.path,*job[:3],job[4],raw,report)
        with closing(n.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT state,trace,report FROM native_shadow_matches").fetchone(),("running",None,None))
            self.assertEqual(db.execute("SELECT count(*) FROM native_shadow_frames").fetchone()[0],0)

    def test_shadow_report_cannot_be_authoritative(self):
        def runner(*args):
            raw,report=self.runner(*args)
            return raw,{**report,"authoritative":True}
        self.assertTrue(n.process_one(self.path,runner))
        with closing(n.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT state FROM native_shadow_matches").fetchone()[0],"failed")
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
