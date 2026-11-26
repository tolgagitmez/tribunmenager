import sqlite3
import sys
import threading
from pathlib import Path
from unittest.mock import patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
import native_av_queue as q

class VerificationLeaseTest(unittest.TestCase):
    def test_renews_while_verification_is_running(self):
        renewed=threading.Event()
        calls=[]
        def heartbeat(db,attempt):
            calls.append((db,attempt))
            if len(calls)>=2:renewed.set()
            return True
        with patch.object(q,'heartbeat',side_effect=heartbeat):
            with q.worker_lease_guard('db','attempt',interval=.01) as check:
                self.assertTrue(renewed.wait(2))
                check()
        self.assertGreaterEqual(len(calls),3)
        self.assertTrue(all(c==('db','attempt') for c in calls))
    def test_expired_reservation_cannot_publish(self):
        failed=threading.Event()
        calls=[]
        def heartbeat(db,attempt):
            calls.append(attempt)
            if len(calls)==1:return True
            failed.set()
            return False
        with patch.object(q,'heartbeat',side_effect=heartbeat):
            with self.assertRaisesRegex(RuntimeError,'Worker lease lost'):
                with q.worker_lease_guard('db','attempt',interval=.01):
                    self.assertTrue(failed.wait(2))
        self.assertEqual(len(calls),2)
    def test_database_failure_is_not_success(self):
        failed=threading.Event()
        def heartbeat(db,attempt):
            if failed.is_set():raise sqlite3.OperationalError('unavailable')
            failed.set()
            return True
        with patch.object(q,'heartbeat',side_effect=heartbeat):
            with self.assertRaises(sqlite3.OperationalError):
                with q.worker_lease_guard('db','attempt',interval=5):pass
    def test_initial_rejection_and_unmanaged_diagnostic(self):
        with patch.object(q,'heartbeat',return_value=False) as renew:
            with self.assertRaisesRegex(RuntimeError,'before launch'):
                with q.worker_lease_guard('db','attempt'):self.fail('launched')
            with q.worker_lease_guard(None,'attempt') as check:check()
            renew.assert_called_once_with('db','attempt')
    def test_run_match_guard_covers_verification(self):
        renewed=threading.Event()
        calls=[]
        def heartbeat(db,attempt):
            calls.append(attempt)
            if len(calls)>1:renewed.set()
            return True
        def match(runtime,root,job,*,check,league_browser_descriptor):
            self.assertTrue(renewed.wait(2))
            check()
            return {'verified':True}
        original=q.worker_lease_guard
        with patch.object(q,'heartbeat',side_effect=heartbeat),patch.object(q,'_run_match',side_effect=match),patch.object(q,'worker_lease_guard',side_effect=lambda db,attempt:original(db,attempt,interval=.01)):
            self.assertEqual(q.run_match(None,None,('key','sha',{},'attempt'),database='db'),{'verified':True})
        self.assertGreaterEqual(len(calls),3)
