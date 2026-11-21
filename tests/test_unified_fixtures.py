"""All due league fixtures share the authoritative, persisted Match worker."""
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

import live_match
import server


@unittest.skipUnless(shutil.which("node"), "Node.js is needed for authoritative league fixtures")
class AllFixturesOneEngine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tribun-unified-fixtures-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "league.sqlite3"
        self.registry = live_match.Registry()
        self.addCleanup(self.registry.close)
        patched = patch.multiple(server, DATA=self.path, LIVE_MATCHES=self.registry, TRANSFERS_ENABLED=False)
        patched.start()
        self.addCleanup(patched.stop)
        server.init_db()
        self.league = server.new_league("Owner")
        self.kickoff = time.time() - .2
        with server.db() as db:
            db.execute("UPDATE fixtures SET kickoff=? WHERE league=? AND round=0",
                       (self.kickoff, self.league["code"]))
            db.execute("UPDATE teams SET formation='4-4-2',tactics=? WHERE league=? AND slot=0",
                       (server.serialize_tactics({"press": 87, "tempo": 66}), self.league["code"]))

    def short_config(self, database, key, now, kickoff):
        original = server.live_config(database, key, now, kickoff)
        # Short real Match clock for a quick, fully physical integration test.
        return {**original, "rules": {"periodSeconds": 3, "halftimeSeconds": 0,
                                      "addedTime": False}}

    def provision(self):
        with patch.object(server, "live_config", side_effect=self.short_config):
            return server.settle_due(self.kickoff + .15)

    def test_kickoff_persists_all_three_configs_without_a_single_watcher(self):
        self.assertEqual(self.provision(), 3)
        self.assertEqual(self.registry.matches.keys().__len__(), 3)
        with server.db() as db:
            rows = db.execute("""SELECT league,round,home,away,config,final_state FROM live_matches
                                  ORDER BY home,away""").fetchall()
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(r["final_state"] is None for r in rows))
            fixtures = db.execute("""SELECT home_score FROM fixtures
                                      WHERE league=? AND round=0""", (self.league["code"],)).fetchall()
            self.assertTrue(all(r["home_score"] is None for r in fixtures),
                            "no approximated score may be written at kickoff")
            home = next(json.loads(r["config"]) for r in rows if r["home"] == 0)
            self.assertEqual(home["formation"], "4-4-2")
            self.assertEqual(home["tactics"]["press"], 87)
            self.assertEqual(home["snapshotAt"], self.kickoff)
            self.assertNotIn("catchupSteps", home)
            self.assertEqual(self.provision(), 0)
            self.assertEqual(len(self.registry.matches), 3)
            db.execute("""UPDATE teams SET formation='5-3-2',tactics=?
                          WHERE league=? AND slot=0""",
                       (server.serialize_tactics({"press": 15}), self.league["code"]))
            saved = db.execute("""SELECT config FROM live_matches
                WHERE league=? AND round=0 AND home=0""", (self.league["code"],)).fetchone()
            frozen = json.loads(saved["config"])
            self.assertEqual(frozen["formation"], "4-4-2")
            self.assertEqual(frozen["tactics"]["press"], 87)
        # Even a real authenticated tactics edit during an unfinished match
        # cannot mutate any configuration already frozen at kickoff.
        with self.assertRaises(ValueError):
            server.update_tactics(self.league["token"], {"press": 10}, "5-3-2")

    def test_unwatched_fixture_completes_with_true_score_and_replay_log(self):
        self.assertEqual(self.provision(), 3)
        with server.db() as db:
            row = db.execute("""SELECT league,round,home,away,kickoff,config
                                 FROM live_matches ORDER BY home,away LIMIT 1""").fetchone()
        key = (row["league"],row["round"],row["home"],row["away"])
        match = self.registry.matches[(self.path.resolve(),key)]
        # Normal scheduler ticks, not HTTP GET and not a fake score update.
        for _ in range(140):
            match.next_step = time.monotonic() - 2.1
            finished = match.tick()
            if finished:
                break
        self.assertTrue(match.state["done"], "unwatched fixture must finish via Match")
        self.assertEqual(match.presence, [0,0])
        final = match.state
        with server.db() as db:
            fixture = db.execute(f"SELECT * FROM fixtures WHERE {live_match.FIXTURE_KEY}", key).fetchone()
            self.assertEqual(final["score"], [fixture["home_score"],fixture["away_score"]])
            self.assertEqual(final["cards"], [fixture["home_yellows"],fixture["away_yellows"]])
            self.assertEqual(final["reds"], [fixture["home_reds"],fixture["away_reds"]])
            rows = db.execute(f"""SELECT operation FROM live_match_operations
                               WHERE {live_match.FIXTURE_KEY} ORDER BY seq""",key).fetchall()
            frames = db.execute(f"""SELECT step,snapshot FROM live_match_frames
                                WHERE {live_match.FIXTURE_KEY} ORDER BY step""",key).fetchall()
            stored = db.execute(f"SELECT final_state FROM live_matches WHERE {live_match.FIXTURE_KEY}",
                                key).fetchone()
        self.assertGreater(len(rows), 1, "all operations must survive completion")
        self.assertGreater(len(frames), 1, "actual ball/player frames must be retained")
        self.assertEqual(frames[0]["step"], 0)
        self.assertTrue(json.loads(frames[-1]["snapshot"])["done"])
        self.assertEqual(json.loads(stored["final_state"]), final)
        self.assertEqual(json.loads(frames[-1]["snapshot"])["ball"], final["ball"])
        self.assertEqual(len(json.loads(frames[-1]["snapshot"])["players"]), 23)
        # Replay the *real* Match from immutable kickoff inputs and recorded
        # commands. No Python score simulator, and no client time source.
        worker = live_match.Worker()
        try:
            state = worker.request({"op":"init","config":json.loads(row["config"])})["state"]
            for operation in rows:
                state = worker.request(json.loads(operation["operation"]))["state"]
            self.assertEqual(state, final)
        finally:
            worker.close()

    def test_worker_recovery_reuses_frozen_ledger_without_restarting_at_zero(self):
        self.assertEqual(self.provision(), 3)
        key = next(identity[1] for identity in self.registry.matches)
        match = self.registry.matches[(self.path.resolve(),key)]
        match.initialize(time.monotonic())
        self.assertEqual(match.step_index, 0)
        self.assertGreater(match.catchup_steps, 0)
        match.apply({"op":"advance","steps":120,"teams":[]},time.monotonic())
        before = match.state
        index = match.step_index
        match.discard_worker()
        match.initialize(time.monotonic())
        self.assertEqual(match.state, before)
        self.assertEqual(match.step_index, index)
        self.assertLess(match.catchup_steps, 1000)
        self.assertEqual(match.presence, [0,0])


if __name__ == "__main__":
    unittest.main()
