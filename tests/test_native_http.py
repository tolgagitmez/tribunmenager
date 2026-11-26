"""Real local HTTP authorization and mailbox tests with synthetic native frames.

No C++ match is fabricated as proof: the native engine runs in separate diagnostics.
"""
from contextlib import closing
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import live_match
import native_live
import native_shadow
import server


class NativeHttpTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.path=self.root/"league.sqlite3"
        self.registry=live_match.Registry()
        self.addCleanup(self.registry.close)
        override=patch.multiple(server,DATA=self.path,LIVE_MATCHES=self.registry,TRANSFERS_ENABLED=False)
        override.start()
        self.addCleanup(override.stop)
        server.init_db()
        self.key=("L",0,0,1)
        self.config={"seed":2026,"homeName":"Home","awayName":"Away"}
        self.sha=native_shadow.digest(self.config)
        now=time.time()-5
        with closing(server.db()) as db,db:
            for league in ("L","OTHER"):
                db.execute("INSERT INTO leagues VALUES(?,?,?)",(league,now,now))
            for league,slot,token in (("L",0,"home-token"),("L",1,"away-token"),("L",2,"other-team"),("OTHER",0,"other-league")):
                db.execute("INSERT INTO teams VALUES(?,?,?,?,?,?,?,?)",
                           (league,slot,token,token,token,"4-3-3","{}",70))
            db.execute("INSERT INTO fixtures(league,round,home,away,kickoff) VALUES(?,?,?,?,?)",(*self.key,now))
            db.execute("INSERT INTO live_matches(league,round,home,away,kickoff,config) VALUES(?,?,?,?,?,?)",
                       (*self.key,now,json.dumps(self.config)))
            db.execute("INSERT INTO native_shadow_matches(league,round,home,away,config_sha,profile,state,attempts) VALUES(?,?,?,?,?,?,'running',1)",(*self.key,self.sha,"short-match"))
            db.execute("INSERT INTO native_interactive_matches VALUES(?,?,?,?)",self.key)
        self.mailbox=self.root/"commands"
        self.mailbox.mkdir()
        self.clock=10.0
        self.session=native_live.Session(self.config,self.mailbox,clock=lambda:self.clock)
        native_live.register(self.key,self.session)
        self.addCleanup(native_live.remove,self.key)
        self.session.ingest(self.frame(1))
        self.http=server.ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.close_http)
        self.base=f"http://127.0.0.1:{self.http.server_port}/api/league/native-pilot"
    def close_http(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)
    def frame(self,seq,done=False,revisions=(0,0),score=(0,0)):
        return dict(schema=1,engine="league-soccer",done=done,elapsedMs=seq*100,
                    matchMs=5400000 if done else seq*1800,score=list(score),inPlay=not done,
                    players=[{"team":t} for t in (0,1) for _ in range(11)],
                    managerTactics=[{"team":t,"revision":revisions[t],**({"press":75,"counter":65,"support":50,"width":70,"tempo":80,"formation":442,"appliedMatchMs":seq*1800,"appliedElapsedMs":seq*100} if revisions[t] else {})} for t in (0,1)])
    def call(self,token,path,body=None):
        headers={"Authorization":"Bearer "+token}
        data=None
        if body is not None:
            data=json.dumps(body).encode()
            headers["Content-Type"]="application/json"
        req=Request(self.base+path,data=data,headers=headers)
        try:
            response=urlopen(req,timeout=10)
        except HTTPError as err:
            response=err
        with response:
            return response.code,json.load(response)
    def command(self,token,ident="request-123",**extra):
        body=dict(round=0,requestId=ident,tactics=dict(press=75,counter=65,support=50,width=70,tempo=80,formation=442))
        body.update(extra)
        return self.call(token,"/tactics",body)
    def test_team_authorization_and_idempotency(self):
        for token in ("","bad-token","other-team","other-league"):
            self.assertEqual(self.command(token)[0],403)
            self.assertEqual(self.call(token,"/broadcast?round=0")[0],403)
        self.assertEqual(self.command("home-token",team=1)[0],400)
        self.assertEqual(self.command("home-token",round=9)[0],403)
        self.assertEqual(list(self.mailbox.iterdir()),[])
        code,home=self.command("home-token")
        self.assertEqual(code,202)
        self.assertEqual(home["team"],0)
        self.assertEqual(home["state"],"submitted-not-applied")
        self.assertEqual(self.command("home-token"),(202,home))
        self.assertFalse((self.mailbox/"team-1.txt").exists())
        code,away=self.command("away-token")
        self.assertEqual(code,202)
        self.assertEqual(away["team"],1)
        self.assertEqual(away["revision"],1)
        self.assertEqual(self.command("home-token","request-456")[0],409)
        self.assertEqual(self.call("home-token","/broadcast?round=0")[1]["commandState"],"waiting-for-engine")
        self.assertEqual(self.call("home-token","/broadcast?round=0")[1]["appliedRevision"],0)
        self.session.ingest(self.frame(2,revisions=(1,0)))
        self.assertEqual(self.call("home-token","/broadcast?round=0")[1]["appliedRevision"],1)
        self.assertEqual(self.call("away-token","/broadcast?round=0")[1]["appliedRevision"],0)
        self.assertEqual((self.mailbox/"team-0.txt").read_text().split()[1],"1")
    def test_final_hidden_until_archive_validated(self):
        final=self.frame(2,done=True,score=(2,1))
        self.session.ingest(final)
        code,view=self.call("home-token","/broadcast?round=0")
        self.assertEqual(code,200)
        self.assertFalse(view["frame"]["done"])
        self.assertFalse(view["canControl"])
        self.assertTrue(view["finalizing"])
        self.assertEqual(self.command("home-token")[0],409)
        native_live.remove(self.key)
        self.assertIsNone(self.call("home-token","/broadcast?round=0")[1]["frame"])
        raw=("\n".join(map(json.dumps,[self.frame(1),final]))+"\n").encode()
        self.assertTrue(native_shadow.commit_shadow_result(self.path,self.key,self.sha,"short-match",1,raw,{"engine":"league-soccer","score":[2,1]}))
        for token in ("home-token","away-token"):
            code,view=self.call(token,"/broadcast?round=0")
            self.assertEqual(code,200)
            self.assertEqual(view["phase"],"finished")
            self.assertTrue(view["frame"]["done"])
            self.assertFalse(view["authoritative"])
            self.assertEqual(view["frame"]["score"],[2,1])
        self.assertEqual(self.command("home-token")[0],409)
        with closing(server.db()) as db:
            self.assertIsNone(db.execute("SELECT final_state FROM live_matches").fetchone()[0])
            self.assertEqual(tuple(db.execute("SELECT home_score,away_score FROM fixtures").fetchone()),(None,None))

if __name__=="__main__":unittest.main()
