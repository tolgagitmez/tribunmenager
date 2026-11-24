import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import server
import live_match
from economy import TransferService, EconomyError

def snapshot(t):
    return {"schema":1,"source":"api-football","teamId":t,"teamUid":f"api-football:team:{t}","name":f"Fictional Club {t}","fetchedAt":"2026-11-24T00:00:00Z",
            "players":[{"providerId":t*100+i,"uid":f"api-football:player:{t*100+i}","name":f"Fictional {t} {i}","age":24,
             "pos":"GK" if i<2 else "DEF" if i<9 else "MID" if i<16 else "ATT"} for i in range(22)]}

class LeagueTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"league.sqlite3"
        self.registry=live_match.Registry()
        self.addCleanup(self.registry.close)
        p=patch.multiple(server,DATA=self.path,LIVE_MATCHES=self.registry,TRANSFERS_ENABLED=False)
        p.start();self.addCleanup(p.stop)
        server.init_db()
        self.snaps=[snapshot(i) for i in range(1,7)]

    def test_creation_claim_lineup_and_freeze(self):
        league=server.new_catalog_league(self.snaps,"synthetic-varied")
        code=league["code"]
        self.assertEqual(league["fixtures"],30)
        lobby=server.league_lobby(code)
        self.assertTrue(lobby["catalog"])
        self.assertTrue(all(not c["claimed"] for c in lobby["clubs"]))
        with self.assertRaises(ValueError):server.join_league(code,"No team")
        joined=server.join_league(code,"Manager",3)
        self.assertEqual(joined["club"],"Fictional Club 4")
        with self.assertRaises(ValueError):server.join_league(code,"Duplicate",3)
        token=joined["token"]
        before=server.status(token)
        self.assertTrue(before["catalog"])
        self.assertEqual(before["my_slot"],3)
        self.assertEqual(len(before["catalogPlan"]["players"]),22)
        plan=before["catalogPlan"]
        with self.assertRaises(ValueError):server.update_tactics(token,{},"4-3-3",[0]*11,plan["revision"])
        ids=plan["starters"][:]
        ids[0],ids[1]=ids[1],ids[0]
        server.update_tactics(token,{"press":83},"4-3-3",ids,plan["revision"])
        with self.assertRaises(ValueError):server.update_tactics(token,{},"4-3-3",ids,plan["revision"])
        after=server.status(token)
        self.assertEqual(after["catalogPlan"]["starters"],ids)
        self.assertEqual(after["my_tactics"]["press"],83)
        self.snaps[3]["players"][0]["name"]="Changed externally"
        with server.db() as c:
            f=c.execute("SELECT * FROM fixtures WHERE league=? AND round=0 AND (home=3 OR away=3)",(code,)).fetchone()
            key=tuple(f[k] for k in ("league","round","home","away"))
            config=server.live_config(c,key,time.time(),f["kickoff"])
        side="players" if f["home"]==3 else "awayPlayers"
        self.assertEqual(config[side][0]["name"],"Fictional 4 0")
        self.assertEqual(config["homeRosterSource"],"catalog-roster")
        self.assertEqual(config["awayRosterSource"],"catalog-roster")
        self.assertEqual(config["starters" if side=="players" else "awayStarters"],ids)
        # Real worker, short physics run; never substitute a Python score.
        config["rules"]={"periodSeconds":3,"halftimeSeconds":0,"addedTime":False}
        worker=live_match.Worker()
        try:
            initial=worker.request({"op":"init","config":config})
            self.assertTrue(initial["ok"])
            self.assertEqual(len([p for p in initial["state"]["players"] if p["active"] and not p.get("referee")]),22)
        finally:worker.close()
        with server.db() as c:
            c.execute("UPDATE leagues SET first_kickoff=? WHERE code=?",(time.time()-1,code))
        with self.assertRaises(ValueError):server.join_league(code,"Late",1)

    def test_reject_duplicate_and_keep_demo_separate(self):
        bad=copy.deepcopy(self.snaps)
        bad[1]["players"][0]=copy.deepcopy(bad[0]["players"][0])
        with self.assertRaises(ValueError):server.new_catalog_league(bad)
        with server.db() as c:self.assertEqual(c.execute("SELECT count(*) FROM leagues").fetchone()[0],0)
        demo=server.new_league("Demo")
        self.assertFalse(server.status(demo["token"])["catalog"])
        self.assertFalse(server.league_lobby(demo["code"])["catalog"])

    def test_transfer_profile_cannot_override_catalog_season(self):
        code=server.new_catalog_league(self.snaps)["code"]
        token=server.join_league(code,"Catalog manager",0)["token"]
        service=TransferService(self.path)
        profile=service.create_profile()
        with self.assertRaises(EconomyError):
            service.command(profile["token"],"link-1","link-league",{"leagueToken":token})
        self.assertEqual(server.status(token)["my_rotation_source"],"catalog-roster")
