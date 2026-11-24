"""Real HTTP, worker and SQLite verification for a shared fixture."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import live_match
import server


class LiveReplayCompatibilityTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "replay.sqlite3"
        self.key = ("REPLAY", 0, 0, 1)
        self.kickoff = time.time()
        with closing(live_match.connect(self.path)) as database, database:
            database.executescript(live_match.SCHEMA)
            database.execute("INSERT INTO live_matches VALUES(?,?,?,?,?,?,?)",
                             (*self.key, self.kickoff, "{}", None))

    def fixture_state(self, seconds, *, x=0, score=None):
        return {"time": seconds, "score": score or [0, 0], "cards": [0, 0], "reds": [0, 0],
                "ownerId": 1, "period": 1, "done": False,
                "ball": {"x": x, "y": .11, "z": 0, "vx": 1, "vy": 0, "vz": 0}}

    def load_replay(self, operations, step, checkpoint):
        with closing(live_match.connect(self.path)) as database, database:
            database.execute("DELETE FROM live_match_operations")
            database.execute("DELETE FROM live_match_frames")
            database.executemany("""INSERT INTO live_match_operations(league,round,home,away,operation)
                VALUES(?,?,?,?,?)""", [(*self.key, live_match.encode(item)) for item in operations])
            database.execute("INSERT INTO live_match_frames VALUES(?,?,?,?,?,?)",
                             (*self.key, step, live_match.encode(checkpoint)))
        return live_match.LiveMatch(self.path, self.key, self.kickoff, {})

    def test_replay_keeps_the_latest_same_step_checkpoint_and_allows_visual_changes(self):
        operations = [{"op": "advance", "steps": 60, "teams": [0]},
                      {"op": "kick", "id": 1, "input": None},
                      {"op": "advance", "steps": 12, "teams": []}]
        stored = self.fixture_state(1, x=4)
        session = self.load_replay(operations, 60, stored)
        final = self.fixture_state(1.2, x=4.1)
        with patch.object(live_match, "Worker") as worker:
            worker.return_value.request.side_effect = [
                {"state": self.fixture_state(0)},
                {"steps": 60, "state": self.fixture_state(1, x=2)},
                {"accepted": True, "state": {**self.fixture_state(1, x=4 + 1e-8), "contacts": [], "telemetry": {}}},
                {"steps": 12, "state": final},
            ]
            session.initialize(0)
            self.assertEqual(session.state, final)
            self.assertEqual(session.step_index, 72)
            self.assertEqual(session.last_frame_step, 60)
            worker.return_value.close.assert_not_called()
            session.discard_worker()

    def test_replay_refuses_divergent_results_without_touching_the_saved_fixture(self):
        advance = {"op": "advance", "steps": 60, "teams": [0]}
        kick = {"op": "kick", "id": 1, "input": None}
        stored = self.fixture_state(1, x=4)
        cases = (
            ([advance], [{"steps": 59, "state": stored}]),
            ([advance, kick], [{"steps": 60, "state": stored}, {"accepted": False, "state": stored}]),
            ([advance], [{"steps": 60, "state": self.fixture_state(1, x=4.03)}]),
            ([advance], [{"steps": 60, "state": self.fixture_state(1, x=4, score=[1, 0])}]),
            ([advance], [{"steps": 60, "state": {**stored, "done": True}}]),
        )
        for index, (operations, replies) in enumerate(cases):
            with self.subTest(case=index):
                session = self.load_replay(operations, 60, stored)
                with patch.object(live_match, "Worker") as worker:
                    worker.return_value.request.side_effect = [{"state": self.fixture_state(0)}, *replies]
                    with self.assertRaises(live_match.ReplayMismatch) as problem:
                        session.initialize(0)
                    self.assertEqual(problem.exception.status, 409)
                    self.assertIsNone(session.state)
                    self.assertIsNone(session.worker)
                    self.assertEqual(session.step_index, 0)
                    worker.return_value.close.assert_called_once()
                    with self.assertRaises(live_match.ReplayMismatch):
                        session.initialize(1)
                    self.assertFalse(session.tick())
                    worker.assert_called_once()
                with closing(live_match.connect(self.path)) as database:
                    self.assertEqual(database.execute("SELECT final_state FROM live_matches").fetchone(), (None,))
                    self.assertEqual(database.execute("SELECT snapshot FROM live_match_frames").fetchone(),
                                     (live_match.encode(stored),))
                    self.assertEqual(database.execute("SELECT operation FROM live_match_operations ORDER BY seq").fetchall(),
                                     [(live_match.encode(item),) for item in operations])


@unittest.skipUnless(shutil.which("node"), "Node.js is required for the live fixture")
class LiveMatchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = live_match.Registry()
        self.addCleanup(self.registry.close)
        self.path = Path(self.temp.name) / "league.sqlite3"
        values = patch.multiple(server, DATA=self.path, LIVE_MATCHES=self.registry, TRANSFERS_ENABLED=False)
        values.start()
        self.addCleanup(values.stop)
        server.init_db()
        self.league = server.new_league("Ev Sahibi")
        self.home = self.league["token"]
        with server.db() as database:
            fixture = database.execute("SELECT * FROM fixtures WHERE home=0 AND round=0").fetchone()
        self.key = tuple(fixture[field] for field in ("league", "round", "home", "away"))
        self.kickoff = time.time() - .02
        with server.db() as database:
            database.execute(f"UPDATE fixtures SET kickoff=? WHERE {live_match.FIXTURE_KEY}",
                             (self.kickoff, *self.key))
        for i in range(1, fixture["away"] + 1):
            self.away = server.join_league(self.league["code"], f"Menajer {i}")["token"]
        self.http = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_port}/api/league/live-match"
        self.addCleanup(self.close_http)

    def close_http(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()

    def get(self, token, round_number=0):
        request = Request(f"{self.base}?round={round_number}", headers={"Authorization": f"Bearer {token}"})
        with urlopen(request, timeout=20) as response:
            return json.load(response)

    def kick(self, token, prompt, control):
        data = json.dumps({"round": 0, "id": prompt, "input": control}).encode()
        request = Request(f"{self.base}/kick", data=data,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urlopen(request, timeout=20) as response:
            return json.load(response)

    def assert_http(self, code, method, *args):
        with self.assertRaises(HTTPError) as error:
            method(*args)
        with error.exception as response:
            self.assertEqual(response.code, code)
            self.assertIn("error", json.load(response))

    def scenario(self, database, key, now, kickoff):
        config = self.original_config(database, key, now, kickoff)
        # Each selected seed is a real physical match, not an injected
        # restart. Home seed 5 and away seed 9 cover independent live prompts.
        tactics = {"playstyle": "wing", "crossing": "early", "tempo": 90,
                   "mentality": "attacking", "aggression": 80, "press": 76, "passing": "direct"}
        for field in ("players", "starters", "awayPlayers", "awayStarters"):
            config.pop(field)
        return {**config, "seed": getattr(self, "match_seed", 5), "catchupSteps": 0, "awayFormation": "4-2-3-1",
                "tactics": tactics, "awayTactics": tactics,
                "rules": {"periodSeconds": 45, "halftimeSeconds": 0, "addedTime": False}}

    def next_state(self, condition, *, side_tokens, iterations=52):
        session = self.session
        for step in range(iterations):
            if step % 3 == 0:
                for token in side_tokens:
                    self.get(token)
            with session.lock:
                session.next_step = time.monotonic() - 2.01
            session.tick()
            if condition(session.state):
                return session.state
        self.fail(f"Match condition did not happen by {session.state['time']:.2f}s")

    def test_away_free_kick_manual_control_is_authoritative_and_replayable(self):
        # Real seed 9 naturally offers an away free kick in period two.
        # It is independent of seed 5's home prompt; no restart is injected.
        self.match_seed = 9
        self.original_config = server.live_config
        with patch.object(server, "live_config", self.scenario):
            home = self.get(self.home)
            away = self.get(self.away)
        self.session = self.registry.matches[(self.path, self.key)]
        self.assertEqual(home["state"], away["state"])
        away_state = self.next_state(
            lambda x: x.get("pendingManagerKick"), side_tokens=(self.home, self.away))
        away_offer = away_state["pendingManagerKick"]
        self.assertEqual(away_offer["team"], 1)
        self.assertEqual(away_offer["kind"], "free-kick")
        self.assertEqual(away_state["period"], 2)
        self.assert_http(409, self.kick, self.home, away_offer["id"], None)
        control = {"angle": away_offer["angle"], "power": .9,
                   "contactX": .4, "contactY": -.55}
        accepted = self.kick(self.away, away_offer["id"], control)
        self.assertIsNone(accepted["state"]["pendingManagerKick"])
        with patch.object(server, "settle_due", side_effect=AssertionError("already running")):
            self.assertEqual(accepted["state"], self.get(self.home)["state"])
        self.assert_http(409, self.kick, self.away, away_offer["id"], control)
        self.session.discard_worker()
        self.assertEqual(accepted["state"], self.get(self.home)["state"])
        next_release = self.next_state(
            lambda x: x["releaseSerial"] > accepted["state"]["releaseSerial"],
            side_tokens=(), iterations=8)
        self.assertGreater(next_release["releaseSerial"],
                           accepted["state"]["releaseSerial"])
        self.session.presence[:] = [0, 0]
        final = self.next_state(lambda x: x["done"], side_tokens=())
        self.assertEqual(final, self.get(self.home)["state"])
        with server.db() as database:
            result = database.execute(
                f"SELECT * FROM fixtures WHERE {live_match.FIXTURE_KEY}", self.key).fetchone()
            self.assertEqual(final["score"], [result["home_score"], result["away_score"]])
            self.assertTrue(database.execute(
                f"SELECT final_state FROM live_matches WHERE {live_match.FIXTURE_KEY}",
                self.key).fetchone()["final_state"])

    def test_authoritative_fixture_kicks_disconnect_and_table(self):
        self.original_config = server.live_config
        # Invalid requests and kicks for a fixture that has not started must
        # not run kickoff scheduling before the request is authorized.
        with patch.object(server, "settle_due", side_effect=AssertionError("cannot schedule")):
            self.assert_http(403, self.get, "not-a-token")
            self.assert_http(409, self.get, self.home, 1)
            self.assert_http(409, self.kick, self.home, 1, None)
        with patch.object(server, "live_config", self.scenario):
            home = self.get(self.home)
            away = self.get(self.away)
        self.session = self.registry.matches[(self.path, self.key)]
        self.assertEqual((home["side"], away["side"]), (0, 1))
        self.assertEqual(home["fixture"], away["fixture"])
        self.assertEqual(home["state"], away["state"])
        self.assertTrue(away["opponentPresent"])
        sides = (self.home, self.away)
        state = self.next_state(lambda x: x.get("pendingManagerKick"), side_tokens=sides)
        home_offer = state["pendingManagerKick"]
        self.assertEqual(home_offer["team"], 0)
        self.assertEqual(self.get(self.home)["state"], self.get(self.away)["state"])
        self.assert_http(409, self.kick, self.away, home_offer["id"], None)
        self.assert_http(400, self.kick, self.home, home_offer["id"],
                         {"angle": 0, "power": 1.2, "contactX": 0, "contactY": 0})
        self.session.tick()
        self.assertEqual(self.session.state["time"], state["time"])
        self.assertEqual(server.settle_due(self.kickoff + 301), 0)
        # The taker's presence lease expires. Automatic delegation obeys
        # the same authoritative restart even though their tab left.
        self.session.presence[0] = time.monotonic() - 1
        self.session.tick()
        self.assertIsNone(self.get(self.away)["state"]["pendingManagerKick"])
        self.session.presence[:] = [0, 0]
        final = self.next_state(lambda x: x["done"], side_tokens=())
        self.assertEqual(final, self.get(self.home)["state"])
        self.assertEqual(final, self.get(self.away)["state"])
        with server.db() as database:
            result = database.execute(f"SELECT * FROM fixtures WHERE {live_match.FIXTURE_KEY}",
                                      self.key).fetchone()
            self.assertEqual(final["score"], [result["home_score"], result["away_score"]])
            self.assertEqual(final["cards"], [result["home_yellows"], result["away_yellows"]])
            self.assertEqual(final["reds"], [result["home_reds"], result["away_reds"]])
        self.assertEqual(server.settle_due(self.kickoff + 302), 0)
        self.assertEqual(server.status(self.home)["standings"][0]["played"], 1)
