"""Exercise the actual HTTP fixture projection without missing catalogue files."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import server

class FixtureRosterAPI(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=server.DATA
        server.DATA=Path(self.temp.name)/'fixture.sqlite3'
        server.init_db()
        self.league=server.new_league('Kendi Menajerim')
        with server.db() as c:
            c.executescript('''CREATE TABLE transfer_profiles(id TEXT PRIMARY KEY,auth TEXT,state TEXT);
                CREATE TABLE transfer_league_links(profile TEXT PRIMARY KEY,league TEXT,slot INT);''')
            self.fixture=dict(c.execute('SELECT * FROM fixtures WHERE league=? AND round=0 AND home=0',(self.league['code'],)).fetchone())
            self.enemy=self.fixture['away']
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join()
        server.DATA=self.old
        self.temp.cleanup()

    def squad(self,slot,starters=None):
        players=[{'id':i,'uid':f'catalog:{slot}-{i}','name':f'Rakip {i}','pos':'GK' if i==10 else 'MID',
            'rating':82,'fitness':90,'form':76,'preferredFoot':'left','weakFoot':71,
            'strength':91,'vision':87,'composure':84,'handling':92,'reactions':88,
            'owned':i!=11,'privateNote':'must not cross boundary'} for i in range(12)]
        state={'profileId':'private-profile','revision':17,'players':players,'starters':starters or list(range(11)),
            'wallet':{'cash':999999},'scout':{'results':['secret']},'offer':{'price':1},'auth':'secret'}
        with server.db() as c:
            c.execute('INSERT INTO transfer_profiles VALUES(?,?,?)',(f'profile-{slot}','secret-auth',json.dumps(state)))
            c.execute('INSERT INTO transfer_league_links VALUES(?,?,?)',(f'profile-{slot}',self.league['code'],slot))
            c.execute('UPDATE teams SET formation=?,tactics=? WHERE league=? AND slot=?',
                ('4-4-2',server.serialize_tactics({'press':81,'passing':'direct'}),self.league['code'],slot))

    def get(self,token=None):
        headers={'Authorization':'Bearer '+token} if token is not None else {}
        request=Request(f'http://127.0.0.1:{self.http.server_port}/api/league/local-match',headers=headers)
        with urlopen(request) as response:
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            return json.load(response)

    def test_actual_endpoint_returns_only_football_snapshot(self):
        self.squad(self.enemy)
        data=self.get(self.league['token'])
        self.assertEqual(data['opponent']['source'],'linked-roster')
        self.assertEqual(data['opponent']['formation'],'4-4-2')
        self.assertEqual(data['opponent']['tactics']['press'],81)
        self.assertEqual(data['opponent']['starters'],list(range(11)))
        self.assertEqual(data['opponent']['revision'],17)
        self.assertEqual(len(data['opponent']['players']),11,'sold records are not an opponent squad')
        player=data['opponent']['players'][0]
        self.assertEqual((player['preferredFoot'],player['strength'],player['vision']),('left',91,87))
        raw=json.dumps(data)
        for private in ('secret','wallet','scout','offer','profileId','privateNote','owned','auth'):
            self.assertNotIn(private,raw)
        self.assertTrue(data['fixture']['isHome'])

    def test_missing_official_squad_is_explicit(self):
        data=self.get(self.league['token'])
        self.assertEqual(data['opponent']['source'],'missing-roster')
        self.assertEqual(data['opponent']['players'],[])
        self.assertEqual(data['opponent']['starters'],[])

    def test_invalid_lineup_is_not_published_as_playable(self):
        self.squad(self.enemy,[0]*11)
        data=self.get(self.league['token'])
        self.assertEqual(data['opponent']['source'],'invalid-roster')
        self.assertEqual(data['opponent']['players'],[])

    def test_away_fixture_keeps_real_venue_and_opponent(self):
        with server.db() as c:
            fixture=dict(c.execute('SELECT * FROM fixtures WHERE league=? AND away=0 ORDER BY round LIMIT 1',(self.league['code'],)).fetchone())
        data=server.local_match(self.league['token'],fixture['kickoff']+1)
        self.assertFalse(data['fixture']['isHome'])
        self.assertEqual(data['fixture']['home'],fixture['home'])
        self.assertEqual(data['opponent']['slot'],fixture['home'])
        self.assertEqual(data['fixture']['state'],'live')

    def test_reading_snapshot_never_settles_official_result(self):
        data=server.local_match(self.league['token'],self.fixture['kickoff']+301)
        with server.db() as c:
            scores=c.execute('SELECT home_score,away_score FROM fixtures WHERE league=?',(self.league['code'],)).fetchall()
        self.assertTrue(all(row['home_score'] is None and row['away_score'] is None for row in scores))

    def test_endpoint_requires_a_valid_league_credential(self):
        for token in (None,'wrong-league-token'):
            with self.assertRaises(HTTPError) as failure:self.get(token)
            self.assertEqual(failure.exception.code,403)

if __name__=='__main__':unittest.main()
