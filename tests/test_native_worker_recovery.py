import sys
import sqlite3
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
import native_av_queue as q
import native_worker_lease as lease
from test_native_av_queue import QueueTest

class RecoveryTest(QueueTest):
    def test_expired_attempt_fenced_and_quarantined(self):
        import time
        now=time.time()
        job=q.claim(self.path,1,now,managed=True)
        key,sha,_,attempt=job
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE native_av_leases SET expires=? WHERE attempt=?',(now-1,attempt))
        self.assertIsNone(q.claim(self.path,1,now))
        self.assertFalse(q.heartbeat(self.path,attempt))
        self.assertFalse(q.finish(self.path,key,sha,attempt,error='late'))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT state FROM native_av_jobs WHERE attempt=?',(attempt,)).fetchone()[0],'failed')
            self.assertEqual(lease.held(db),1)
            self.assertFalse(lease.clear_after_reboot(db,attempt))
            self.assertEqual(db.execute('SELECT count(*) FROM native_av_season_results').fetchone()[0],0)
    def test_heartbeat_and_normal_failure(self):
        import time
        job=q.claim(self.path,1,time.time(),managed=True)
        key,sha,_,attempt=job
        self.assertTrue(q.heartbeat(self.path,attempt))
        self.assertTrue(q.finish(self.path,key,sha,attempt,error='controlled failure'))
        self.assertFalse(q.heartbeat(self.path,attempt))
        self.assertIsNotNone(q.claim(self.path,1,time.time(),managed=True))
