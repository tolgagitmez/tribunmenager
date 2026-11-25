import json
import tempfile
import unittest
import sqlite3
from pathlib import Path
import native_live as n
import native_shadow as shadow
from live_match import SCHEMA

def frame(seq=1,done=False):
    return dict(schema=1,engine="league-soccer",done=done,elapsedMs=seq*100,matchMs=5400000 if done else seq*1000,score=[0,0],players=[{"team":t} for t in (0,1) for _ in range(11)],managerTactics=[{"team":0,"revision":0},{"team":1,"revision":0}])

class LiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.now=10
        self.s=n.Session({},self.root,clock=lambda:self.now)
        self.values=(75,65,50,70,80,442)
    def test_team_scope_and_idempotent_request(self):
        self.s.ingest(frame())
        a=self.s.command(0,"request-1",self.values)
        self.assertEqual(a,self.s.command(0,"request-1",self.values))
        self.assertEqual(self.s.command(1,"request-1",self.values)["revision"],1)
        with self.assertRaises(n.ControlError):self.s.command(0,"request-2",self.values)
        with self.assertRaises(n.ControlError):self.s.command(0,"request-1",(20,*self.values[1:]))
        self.assertEqual(self.s.read(0)["appliedRevision"],0)
        self.now+=3
        self.assertEqual(self.s.command(0,"request-2",self.values)["revision"],2)
    def test_tail_partial_and_final_hidden(self):
        path=self.root/"trace"
        tail=n.Tail(path,self.s)
        line=json.dumps(frame())
        path.write_text(line)
        tail.drain()
        self.assertIsNone(self.s.read(0)["frame"])
        with path.open("a") as f:f.write("\n")
        tail.drain()
        self.assertEqual(self.s.read(0)["sequence"],0)
        with path.open("a") as f:f.write(json.dumps(frame(2,True))+"\n")
        tail.drain()
        self.assertFalse(self.s.read(0)["frame"]["done"])
        self.assertFalse(self.s.read(0)["canControl"])
    def test_stale_short_handed_and_invalid(self):
        self.s.ingest(frame())
        self.now+=6
        with self.assertRaises(n.ControlError):self.s.command(0,"request-1",self.values)
        f=frame(2);f["players"].pop(0);self.s.ingest(f)
        with self.assertRaises(n.ControlError):self.s.command(0,"request-1",self.values)
        self.assertEqual(self.s.command(0,"request-1",(*self.values[:-1],0))["revision"],1)
        with self.assertRaises(n.ControlError):n.validate_command({"round":0,"requestId":"request-1","team":1,"tactics":{}})
    def test_restart_fails_closed(self):
        dbpath=self.root/"db.sqlite"
        key=("L",0,0,1)
        with sqlite3.connect(dbpath) as db:
            db.executescript(SCHEMA+shadow.SCHEMA)
            db.execute("INSERT INTO native_shadow_matches(league,round,home,away,config_sha,profile,state,attempts) VALUES(?,?,?,?,?,?,'running',1)",(*key,"sha","baseline"))
            db.execute("INSERT INTO native_interactive_matches VALUES(?,?,?,?)",key)
        shadow.recover(dbpath)
        with sqlite3.connect(dbpath) as db:
            self.assertEqual(db.execute("SELECT state FROM native_shadow_matches").fetchone()[0],"failed")
if __name__=="__main__":unittest.main()
