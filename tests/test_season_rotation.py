"""Real league rotation state: atomic minutes, match bans and next kickoff eligibility."""
from pathlib import Path
import json
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
import live_match
import season_state
import server

class RotationState(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="tribun-rotation-")
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"season.db"
        self.registry=live_match.Registry()
        self.addCleanup(self.registry.close)
        mocked=patch.multiple(server,DATA=self.path,LIVE_MATCHES=self.registry,TRANSFERS_ENABLED=False)
        mocked.start();self.addCleanup(mocked.stop)
        server.init_db()
        self.league=server.new_league("Manager")
        self.code=self.league["code"]
        self.team0={r["round"]:r for r in self.fixtures()}

    def fixtures(self):
        with server.db() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM fixtures WHERE league=? AND (home=0 OR away=0) ORDER BY round",(self.code,))]

    def linked_squad(self):
        players=[{"id":i,"uid":f"unique:{i}","name":f"Player {i}",
                   "pos":"DEF" if i in (6,7,8,9,11) else "MID",
                   "subposition":"CB" if i in (7,8,11) else "LB" if i==6 else "DM",
                   "rating":80,"fitness":95,"form":100,"preferredFoot":"right"} for i in range(14)]
        players[10]["pos"]="GK";players[10]["subposition"]="GK"
        state={"players":players,"starters":list(range(11)),"revision":3}
        with server.db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS transfer_profiles(id TEXT PRIMARY KEY,auth TEXT,state TEXT);
            CREATE TABLE IF NOT EXISTS transfer_league_links(profile TEXT PRIMARY KEY,league TEXT,slot INT);""")
            db.execute("INSERT INTO transfer_profiles VALUES(?,?,?)",
                       ("link","token",json.dumps(state)))
            db.execute("INSERT INTO transfer_league_links VALUES(?,?,?)",("link",self.code,0))

    def appearance(self,player,team=0,yellow=0,red=0,minutes=90,startFitness=95):
        return {"team":team,"rosterId":player,"rosterUid":f"unique:{player}",
                "minutes":minutes,"seconds":minutes/90*6,"sprintSeconds":2,
                "startFitness":startFitness,"yellow":yellow,"red":red}

    def test_suspension_and_fatigue_change_next_fixture_XI_not_past_snapshot(self):
        self.linked_squad()
        first=self.team0[0]
        key=(self.code,0,first["home"],first["away"])
        with server.db() as db:
            before=server.live_config(db,key,first["kickoff"]-1,first["kickoff"])
        self.assertEqual(before["players"][6]["fitness"],95)
        self.assertEqual(before["starters"],list(range(11)))
        with server.db() as db:
            season_state.apply_fixture(db,key,[self.appearance(6,red=1),
                 self.appearance(7,minutes=45)])
            season_state.apply_fixture(db,key,[self.appearance(6,red=1),
                 self.appearance(7,minutes=45)])
        with server.db() as db:
            result=server.live_config(db,tuple(self.team0[1][k] for k in
                        ("league","round","home","away")),self.team0[1]["kickoff"],
                        self.team0[1]["kickoff"])
        players=result["players"] if self.team0[1]["home"]==0 else result["awayPlayers"]
        starters=result["starters"] if self.team0[1]["home"]==0 else result["awayStarters"]
        self.assertNotIn(6,starters,"red-card player must not be selected next game")
        self.assertIn(11,starters,"available bench centre-back replaces suspended fullback")
        self.assertTrue(next(p for p in players if p["id"]==6)["season"]["suspended"])
        self.assertLess(next(p for p in players if p["id"]==7)["fitness"],95)
        self.assertEqual(before["starters"],list(range(11)))
        with server.db() as db:
            r=db.execute("SELECT * FROM season_player_state WHERE league=? AND slot=0 AND player_key='uid:unique:6'",
                         (self.code,)).fetchone()
            self.assertEqual(r["appearances"],1)
            self.assertEqual(r["minutes"],90)
            next_key=tuple(self.team0[2][k] for k in ("league","round","home","away"))
            third=server.live_config(db,next_key,self.team0[2]["kickoff"],self.team0[2]["kickoff"])
        third_players=third["players"] if self.team0[2]["home"]==0 else third["awayPlayers"]
        self.assertFalse(next(p for p in third_players if p["id"]==6)["season"]["suspended"])
        self.assertGreater(next(p for p in third_players if p["id"]==6)["fitness"],
                           next(p for p in players if p["id"]==6)["fitness"])

    def test_yellow_carry_and_ban_after_fifth_yellow(self):
        with server.db() as db:
            for rnd in range(3):
                f=self.team0[rnd];key=tuple(f[k] for k in ("league","round","home","away"))
                side=0 if f["home"]==0 else 1
                season_state.apply_fixture(db,key,[self.appearance(0,team=side,yellow=2 if rnd<2 else 1)])
            d=season_state.status(db,self.code,0,{"id":0,"uid":"unique:0","fitness":95},3)
            self.assertTrue(d["season"]["suspended"])
            self.assertEqual(d["season"]["yellows"],5)
            self.assertEqual(d["season"]["yellowCarry"],0)
            self.assertFalse(season_state.status(db,self.code,0,{"id":0,"uid":"unique:0"},4)["season"]["suspended"])

    @unittest.skipUnless(shutil.which("node"),"Node required")
    def test_overdue_rounds_wait_for_prior_results_before_freezing_fitness(self):
        # Catching up two past matchdays in one call used to freeze both
        # before the first round's recovery/discipline was committed.
        kickoff=time.time()-.3
        with server.db() as db:
            db.execute("UPDATE fixtures SET kickoff=? WHERE league=? AND round IN (0,1)",
                       (kickoff,self.code))
        original=server.live_config
        def short(db,key,now,kickoff):
            return {**original(db,key,now,kickoff),
                    "rules":{"periodSeconds":2,"halftimeSeconds":0,"addedTime":False}}
        with patch.object(server,"live_config",side_effect=short):
            self.assertEqual(server.settle_due(kickoff+.1),3)
            with server.db() as db:
                self.assertEqual(set(r["round"] for r in db.execute("SELECT round FROM live_matches")),{0})
            for session in list(self.registry.matches.values()):
                for _ in range(150):
                    session.next_step=time.monotonic()-2.1
                    if session.tick():break
                self.assertTrue(session.state["done"])
            self.assertEqual(server.settle_due(kickoff+.2),3)
            with server.db() as db:
                self.assertEqual(set(r["round"] for r in db.execute("SELECT round FROM live_matches")),{0,1})
                row=db.execute("""SELECT config FROM live_matches WHERE league=? AND round=1
                      AND (home=0 OR away=0)""",(self.code,)).fetchone()
                game=json.loads(row["config"])
                own=game["players"] if game["homeName"]==server.TEAMS[0] else game["awayPlayers"]
                player=next(p for p in own if p["id"]==0)
                self.assertGreater(player["season"]["appearances"],0)
                self.assertLess(player["fitness"],95)

    @unittest.skipUnless(shutil.which("node"),"Node required")
    def test_real_unwatched_match_seals_score_and_player_season_in_one_transaction(self):
        f=self.team0[0]
        kickoff=time.time()-.2
        with server.db() as db:
            db.execute("UPDATE fixtures SET kickoff=? WHERE league=? AND round=0",(kickoff,self.code))
        original=server.live_config
        def short(db,key,now,kickoff):
            return {**original(db,key,now,kickoff),
                    "rules":{"periodSeconds":2,"halftimeSeconds":0,"addedTime":False}}
        with patch.object(server,"live_config",side_effect=short):
            server.settle_due(kickoff+.1)
        key=tuple(f[k] for k in ("league","round","home","away"))
        session=self.registry.matches[(self.path.resolve(),key)]
        for _ in range(150):
            session.next_step=time.monotonic()-2.1
            if session.tick():break
        self.assertTrue(session.state["done"])
        self.assertGreater(len(session.state["appearances"]),0)
        with server.db() as db:
            score=db.execute("SELECT home_score FROM fixtures WHERE league=? AND round=? AND home=? AND away=?",key).fetchone()
            rows=db.execute("SELECT * FROM season_fixture_appearances WHERE league=? AND round=? AND home=? AND away=?",key).fetchall()
            self.assertIsNotNone(score["home_score"])
            self.assertEqual(len(rows),len(session.state["appearances"]))
            self.assertTrue(all(row["minutes"]>0 for row in rows))
            saved=db.execute("SELECT final_state FROM live_matches WHERE league=? AND round=? AND home=? AND away=?",key).fetchone()
            self.assertEqual(len(json.loads(saved["final_state"])["appearances"]),len(rows))
            # One replayed receipt cannot double-count old minutes.
            season_state.apply_fixture(db,key,session.state["appearances"])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM season_fixture_appearances").fetchone()[0],len(rows))

if __name__=="__main__":unittest.main()
