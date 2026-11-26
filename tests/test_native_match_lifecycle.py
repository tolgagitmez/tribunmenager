import os
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import unittest
import server
from live_match import Registry

class LifecycleTest(unittest.TestCase):
    def test_queue_running_expired_and_failure(self):
        with tempfile.TemporaryDirectory() as t,patch.multiple(server,DATA=Path(t)/'db.sqlite',LIVE_MATCHES=Registry()),patch.dict(os.environ,{'TRIBUN_NATIVE_ONLY_LEAGUE':'1','TRIBUN_NATIVE_AV_QUEUE':'0','TRIBUN_NATIVE_SHADOW':'0'}):
            server.init_db()
            a=server.new_league('Home',native=True)
            now=time.time()
            with server.db() as db:db.execute('UPDATE fixtures SET kickoff=? WHERE league=? AND round=0',(now-1,a['code']))
            server.settle_due(now)
            state=server.status(a['token'],now)
            self.assertEqual(state['my_match']['nativeState'],'queued')
            self.assertEqual(state['nativeRoundStates']['queued'],3)
            self.assertEqual(state['active'],[])
            job=server.native_av_queue.claim(server.DATA,1,now,managed=True)
            key,sha,_,attempt=job
            state=server.status(a['token'],now+1)
            self.assertEqual(state['my_match']['nativeState'],'running')
            self.assertEqual(state['nativeRoundStates']['running'],1)
            self.assertNotIn(attempt,str(state))
            state=server.status(a['token'],now+31)
            self.assertEqual(state['my_match']['nativeState'],'interrupted')
            self.assertFalse(state['active'])
            with server.db() as db:
                db.execute("UPDATE native_av_jobs SET state='failed',error='private detail' WHERE attempt=?",(attempt,))
            state=server.status(a['token'],now+86401)
            self.assertEqual(state['my_match']['nativeState'],'failed')
            self.assertEqual(state['day'],1)
            self.assertNotIn('private detail',str(state))
            self.assertIsNone(state['my_match']['home_score'])
