"""Native trial reservations must never start the old authoritative worker."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import live_match
import server

class NativeOwnershipTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.registry=live_match.Registry()
        self.addCleanup(self.registry.close)
        self.path=Path(tmp.name)/'league.sqlite3'
        p=patch.multiple(server,DATA=self.path,LIVE_MATCHES=self.registry,TRANSFERS_ENABLED=False)
        p.start()
        self.addCleanup(p.stop)
        server.init_db()
        self.league=server.new_league('Native test')
        with server.db() as db:
            row=db.execute('SELECT * FROM fixtures WHERE round=0 AND (home=0 OR away=0)').fetchone()
            self.key=tuple(row[k] for k in ('league','round','home','away'))
            self.kickoff=row['kickoff']
        self.now=self.kickoff-1

    def reserve(self,review='a'*64,**kw):
        return server.reserve_native_trial(self.key,self.kickoff,review,now=self.now,**kw)

    def test_hold_is_opt_in_and_excludes_legacy(self):
        with self.assertRaises(ValueError):
            self.reserve()
        self.assertTrue(self.reserve(experimental=True))
        self.assertFalse(self.reserve(experimental=True))
        with self.assertRaises(ValueError):
            self.reserve('b'*64,experimental=True)
        # Scheduler still provisions other matches, without starting workers
        # in this test; a viewer cannot force the reserved match into JS.
        with patch.object(server.shutil,'which',return_value='/usr/bin/node'):
            server.settle_due(self.kickoff)
            with self.assertRaises(live_match.LiveMatchError) as exc:
                server.live_session(self.league['token'],0,watch=True,now=self.kickoff)
            self.assertEqual(exc.exception.status,409)
            local=server.local_match(self.league['token'],now=self.kickoff)
            self.assertEqual(local['fixture']['state'],'native-reserved')
        with server.db() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM live_matches WHERE '+live_match.FIXTURE_KEY,self.key).fetchone())
            self.assertIsNone(db.execute('SELECT home_score FROM fixtures WHERE '+live_match.FIXTURE_KEY,self.key).fetchone()[0])
            with self.assertRaisesRegex(sqlite3.IntegrityError,'native fixture is reserved'):
                db.execute('INSERT INTO live_matches (league,round,home,away,kickoff,config) VALUES(?,?,?,?,?,?)',(*self.key,self.kickoff,'{}'))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM native_fixture_holds')
        self.assertNotIn((self.path.resolve(),self.key),self.registry.matches)

    def test_existing_legacy_worker_cannot_be_taken_over(self):
        with server.db() as db:
            db.execute('INSERT INTO live_matches (league,round,home,away,kickoff,config) VALUES(?,?,?,?,?,?)',(*self.key,self.kickoff,'{}'))
        with self.assertRaisesRegex(sqlite3.IntegrityError,'unavailable'):
            self.reserve(experimental=True)
        with server.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM native_fixture_holds').fetchone()[0],0)
