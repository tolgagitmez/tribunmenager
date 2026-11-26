import os
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import unittest
import server
import native_league_mode as mode
import native_season
from test_native_season import fixture
from live_match import Registry,LiveMatchError,LiveMatch

class NativeLeagueTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'db.sqlite'
        self.patch=patch.multiple(server,DATA=self.db,LIVE_MATCHES=Registry())
        self.patch.start();self.addCleanup(self.patch.stop)
        self.env=patch.dict(os.environ,{'TRIBUN_NATIVE_ONLY_LEAGUE':'1','TRIBUN_NATIVE_AV_QUEUE':'0','TRIBUN_NATIVE_SHADOW':'0'})
        self.env.start();self.addCleanup(self.env.stop)
        server.init_db()
        self.native=server.new_league('Native',native=True)
        self.legacy=server.new_league('Legacy')
        self.now=time.time()
        with server.db() as db:
            db.execute('UPDATE fixtures SET kickoff=? WHERE round=0',(self.now-1,))
    def test_routing_and_database_fence(self):
        self.assertEqual(server.settle_due(self.now),6)
        with server.db() as db:
            self.assertTrue(mode.is_native(db,self.native['code']))
            self.assertFalse(mode.is_native(db,self.legacy['code']))
            self.assertEqual(db.execute('SELECT count(*) FROM native_av_jobs').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT count(*) FROM live_matches').fetchone()[0],6)
            key=tuple(db.execute('SELECT league,round,home,away FROM live_matches WHERE league=? LIMIT 1',(self.native['code'],)).fetchone())
            config=db.execute('SELECT config FROM live_matches WHERE league=? LIMIT 1',(key[0],)).fetchone()[0]
            self.assertIn('native-only',config)
            for statement,args in [
                ('UPDATE fixtures SET home_score=0 WHERE league=?',(key[0],)),
                ('DELETE FROM native_only_leagues WHERE league=?',(key[0],)),
                ('INSERT INTO native_only_leagues VALUES(?,0)',(self.legacy['code'],)),
                ('INSERT INTO live_match_operations(league,round,home,away,operation) VALUES(?,?,?,?,?)',(*key,'{}'))]:
                with self.assertRaises(sqlite3.IntegrityError):db.execute(statement,args)
        self.assertEqual(len(server.LIVE_MATCHES.matches),3)
        restored=Registry();restored.restore(self.db)
        self.assertEqual(len(restored.matches),3)
        with self.assertRaises(LiveMatchError):LiveMatch(self.db,key,self.now,{}).initialize(time.monotonic())
        with self.assertRaises(LiveMatchError):server.live_session(self.native['token'],0,watch=True,now=self.now)
        with self.assertRaises(LiveMatchError):server.local_match(self.native['token'],now=self.now)
    def test_private_results_and_round_progression(self):
        server.settle_due(self.now)
        q=server.native_av_queue
        with server.db() as db:db.execute('UPDATE fixtures SET kickoff=? WHERE league=? AND round=1',(self.now-1,self.native['code']))
        f,m=fixture();state=native_season.candidate(f,m)
        for i in range(3):
            job=q.claim(self.db,3,self.now)
            key,sha,_,attempt=job
            report=dict(verified=True,authoritative=False,configSha256=sha,score=state['score'],season=state,controlSource='league-gateway',engine='league-soccer',audioOwnershipVerified=True)
            self.assertTrue(q.finish(self.db,key,sha,attempt,report=report))
        self.assertEqual(server.settle_due(self.now),3)
        with server.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM fixtures WHERE home_score IS NOT NULL').fetchone()[0],0)
            projected=mode.fixtures(db,self.native['code'])
            self.assertEqual(sum(f['home_score'] is not None for f in projected),3)
            self.assertEqual(db.execute('SELECT count(*) FROM native_av_jobs WHERE round=1').fetchone()[0],3)
        self.assertEqual(server.status(self.native['token'],self.now)['matchBackend'],'native-only')
