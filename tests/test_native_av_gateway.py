import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import native_av_gateway as g

class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript("""CREATE TABLE teams(league,slot,token);
        CREATE TABLE fixtures(league,round,home,away,kickoff);
        CREATE TABLE native_av_jobs(league,round,home,away,attempt,state);
        INSERT INTO teams VALUES('L',0,'home'),('L',1,'away'),('L',2,'other'),('X',0,'foreign');
        INSERT INTO fixtures VALUES('L',0,0,1,100),('L',0,2,3,100),('X',0,0,1,100);
        INSERT INTO native_av_jobs VALUES('L',0,0,1,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','running'),
        ('L',0,2,3,'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','running');""")
    def test_team_and_league_scope(self):
        self.assertEqual(g.resolve(self.db,'home',0,100),('a'*32,0))
        self.assertEqual(g.resolve(self.db,'away',0,100),('a'*32,1))
        self.assertEqual(g.resolve(self.db,'other',0,100),('b'*32,0))
        for tok,r,now in [('foreign',0,100),('bad',0,100),('home',1,100),('home',0,99)]:
            with self.assertRaises(g.GatewayError):g.resolve(self.db,tok,r,now)
        self.db.execute("UPDATE native_av_jobs SET state='ready'")
        with self.assertRaises(g.GatewayError):g.resolve(self.db,'home',0,100)
    def test_only_private_loopback_capability(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/('a'*32)/'run';p.mkdir(parents=True)
            f=p/'local-manager-0.txt';f.write_text('http://127.0.0.1:8001/'+'a'*32+'/');f.chmod(0o600)
            self.assertEqual(g.private_url(d,'a'*32,0),f.read_text())
            f.write_text('http://example.com:8001/'+'a'*32+'/')
            with self.assertRaises(g.GatewayError):g.private_url(d,'a'*32,0)
            f.write_text('http://127.0.0.1:8001/'+'a'*32+'/');f.chmod(0o644)
            with self.assertRaises(g.GatewayError):g.private_url(d,'a'*32,0)
