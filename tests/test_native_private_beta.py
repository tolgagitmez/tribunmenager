import sqlite3
import sys
from pathlib import Path
import tempfile
import unittest
HERE=Path(__file__).resolve().parents[1]/'integrations/league-soccer'
sys.path.insert(0,str(HERE))
import native_private_beta as beta
import native_private_media as media
from native_av_gateway import GatewayError

class BetaTest(unittest.TestCase):
    def test_private_directory(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'new'
            self.assertEqual(beta.private_new(p),p.resolve())
            self.assertEqual(p.stat().st_mode&0o777,0o700)
            with self.assertRaises(FileExistsError):beta.private_new(p)
        with self.assertRaises(ValueError):beta.private_new(beta.server.ROOT/'not-created')
    def test_foreign_native_account_resolves_only_own_fixture(self):
        with sqlite3.connect(':memory:') as db:
            db.executescript("""
            CREATE TABLE teams(league,slot,token);
            CREATE TABLE native_only_leagues(league);
            CREATE TABLE fixtures(league,round,home,away,kickoff);
            CREATE TABLE native_av_jobs(league,round,home,away,attempt,state);
            INSERT INTO native_only_leagues VALUES('L'),('X');
            INSERT INTO teams VALUES('L',0,'home'),('X',0,'foreign');
            INSERT INTO fixtures VALUES('L',0,0,1,100),('X',0,0,1,200);
            INSERT INTO native_av_jobs VALUES('L',0,0,1,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','running');
            """)
            self.assertEqual(media.authorize(db,'home',0,150),('a'*32,0))
            with self.assertRaises(GatewayError) as exc:media.authorize(db,'foreign',0,150)
            self.assertEqual(exc.exception.status,409)
            with self.assertRaises(GatewayError) as exc:media.authorize(db,'',0,150)
            self.assertEqual(exc.exception.status,403)
            db.execute("INSERT INTO native_av_jobs VALUES('X',0,0,1,'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','running')")
            self.assertEqual(media.authorize(db,'foreign',0,250),('b'*32,0))
