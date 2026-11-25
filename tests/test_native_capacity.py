import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import native_live
import native_shadow
from live_match import SCHEMA

class NativeCapacityTest(unittest.TestCase):
    def test_worker_bound(self):
        for value in ("1","2","3"):
            self.assertEqual(native_shadow.worker_count(value),int(value))
        for value in ("0","4","invalid",""):
            with self.assertRaises(ValueError):native_shadow.worker_count(value)
    def test_three_independent_claims(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"league.sqlite"
            config={"seed":2}
            keys=[("L",0,i,i+3) for i in range(3)]
            with sqlite3.connect(path) as db:
                db.executescript(SCHEMA+native_shadow.SCHEMA)
                for key in keys:
                    db.execute("INSERT INTO live_matches(league,round,home,away,kickoff,config) VALUES(?,?,?,?,?,?)",(*key,1000,json.dumps(config)))
                    with patch.dict("os.environ",{"TRIBUN_NATIVE_SHADOW":"1","TRIBUN_NATIVE_INTERACTIVE":"0","TRIBUN_NATIVE_SHADOW_PROFILE":"baseline"}):
                        native_shadow.enqueue(db,key,config)
            barrier=threading.Barrier(3)
            def claim():
                barrier.wait(timeout=10)
                return native_shadow.claim(path)
            with ThreadPoolExecutor(max_workers=3) as pool:
                jobs=list(pool.map(lambda _:claim(),range(3)))
            self.assertEqual({job[0] for job in jobs},set(keys))
            self.assertIsNone(native_shadow.claim(path))
    def test_wall_clock_is_measured_not_invented(self):
        with tempfile.TemporaryDirectory() as d:
            now=[10.]
            s=native_live.Session({},Path(d),clock=lambda:now[0])
            f=dict(schema=1,engine="league-soccer",done=False,elapsedMs=100,matchMs=100,score=[0,0],inPlay=True)
            s.ingest(f)
            self.assertIsNone(s.timing()["observedWallMs"])
            now[0]=330.
            s.ingest({**f,"done":True,"elapsedMs":320100,"matchMs":5400000})
            self.assertEqual(s.timing()["observedWallMs"],320000)
            self.assertEqual(s.timing()["deviationMs"],20000)
            self.assertFalse(s.timing()["withinFiveSeconds"])
            self.assertFalse(s.read(0)["canControl"])
if __name__=="__main__":unittest.main()
