import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
import native_season
from test_native_season import fixture
from concurrent.futures import ThreadPoolExecutor

spec=importlib.util.spec_from_file_location('avqueue',Path(__file__).resolve().parents[1]/'integrations/league-soccer/native_av_queue.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

class QueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'league.db'
        with sqlite3.connect(self.path) as db:
            db.executescript("""CREATE TABLE live_matches(league,round,home,away,kickoff,config);
            CREATE TABLE fixtures(league,round,home,away,home_score);
            INSERT INTO fixtures VALUES('L',0,0,1,NULL),('L',0,2,3,NULL),('L',1,0,2,NULL);
            INSERT INTO live_matches VALUES('L',0,0,1,100,'{"seed":1}'),('L',0,2,3,100,'{"seed":2}'),('L',1,0,2,86500,'{"seed":3}');"""+q.SCHEMA)
            self.assertEqual(q.sync(db,100),2)
            self.assertEqual(q.sync(db,100),0)

    def tearDown(self):self.tmp.cleanup()

    def test_atomic_claim_and_finish(self):
        with ThreadPoolExecutor(2) as pool:
            jobs=list(pool.map(lambda _:q.claim(self.path,1,100),range(2)))
        self.assertEqual(sum(j is not None for j in jobs),1)
        key,sha,config,attempt=next(j for j in jobs if j)
        f,m=fixture()
        result=dict(authoritative=False,verified=True,configSha256=sha,score=f['score'],season=native_season.candidate(f,m))
        with self.assertRaises(ValueError):q.finish(self.path,key,sha,attempt,report={k:v for k,v in result.items() if k!='season'})
        self.assertFalse(q.finish(self.path,key,sha,'wrong',report=result))
        self.assertTrue(q.finish(self.path,key,sha,attempt,report=result))
        self.assertFalse(q.finish(self.path,key,sha,attempt,report=result))
        self.assertIsNotNone(q.claim(self.path,1,100))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM fixtures WHERE home_score IS NOT NULL').fetchone()[0],0)

    def test_capacity_and_changed_config(self):
        self.assertIsNone(q.claim(self.path,0,100))
        with sqlite3.connect(self.path) as db:db.execute("UPDATE live_matches SET config='{}' WHERE home=0 AND round=0")
        self.assertIsNone(q.claim(self.path,1,100))
        self.assertIsNotNone(q.claim(self.path,1,100))

if __name__=='__main__':unittest.main()
