"""One authoritative, recoverable simulation for every league fixture."""
from __future__ import annotations

from contextlib import closing
import json
import math
from pathlib import Path
from queue import Empty, Queue
import shutil
import sqlite3
import season_state
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parent
PRESENCE_SECONDS = 6
DECISION_SECONDS = 12
STEP_SECONDS = 1 / 60
MAX_STEPS = 120
FIXTURE_KEY = "league=? AND round=? AND home=? AND away=?"

SCHEMA = """
CREATE TABLE IF NOT EXISTS live_matches(
    league TEXT NOT NULL, round INT NOT NULL, home INT NOT NULL, away INT NOT NULL,
    kickoff REAL NOT NULL, config TEXT NOT NULL, final_state TEXT,
    PRIMARY KEY(league, round, home, away)
);
CREATE TABLE IF NOT EXISTS live_match_lineup_issues(
    league TEXT NOT NULL, round INT NOT NULL, home INT NOT NULL, away INT NOT NULL,
    message TEXT NOT NULL,
    PRIMARY KEY(league, round, home, away)
);
CREATE TABLE IF NOT EXISTS live_match_operations(
    seq INTEGER PRIMARY KEY, league TEXT NOT NULL, round INT NOT NULL,
    home INT NOT NULL, away INT NOT NULL, operation TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS live_match_operations_fixture
ON live_match_operations(league, round, home, away, seq);
-- Periodic position/ball snapshots make the persistent command history useful
-- for future highlights and substitution timelines without client authority.
CREATE TABLE IF NOT EXISTS live_match_frames(
    league TEXT NOT NULL, round INT NOT NULL, home INT NOT NULL, away INT NOT NULL,
    step INT NOT NULL, snapshot TEXT NOT NULL,
    PRIMARY KEY(league, round, home, away, step)
);
"""


class LiveMatchError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


class ReplayMismatch(LiveMatchError):
    def __init__(self):
        super().__init__("Kayıtlı canlı maç bu motor sürümüyle aynı konumdan devam edemiyor. Maç kaydı korunuyor.", 409)


def matches_checkpoint(expected, actual):
    if actual is None:
        return False
    try:
        exact = ("score", "cards", "reds", "ownerId", "period")
        if any(expected[key] != actual[key] for key in exact):
            return False
        if not math.isclose(expected["time"], actual["time"], rel_tol=0, abs_tol=1e-7):
            return False
        return all(math.isclose(expected["ball"][axis], actual["ball"][axis], rel_tol=0, abs_tol=1e-7)
                   for axis in ("x", "y", "z", "vx", "vy", "vz"))
    except (KeyError, TypeError):
        return False


def connect(path):
    return sqlite3.connect(path, timeout=20)


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class Worker:
    def __init__(self):
        node = shutil.which("node")
        if not node:
            raise LiveMatchError("Canlı lig maçı için sunucuda Node.js gerekli.")
        try:
            self.process = subprocess.Popen(
                [node, str(ROOT / "live-match-worker.cjs")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                encoding="utf-8", bufsize=1,
            )
        except OSError as exc:
            raise LiveMatchError("Maç motoru başlatılamadı.") from exc
        self.replies = Queue()

        def receive():
            try:
                for line in self.process.stdout:
                    self.replies.put(line)
            finally:
                self.replies.put(None)

        self.reader = threading.Thread(target=receive, daemon=True)
        self.reader.start()

    def request(self, action):
        try:
            self.process.stdin.write(encode(action) + "\n")
            self.process.stdin.flush()
            response = json.loads(self.replies.get(timeout=10) or "null")
        except (Empty, OSError, ValueError) as exc:
            raise LiveMatchError("Maç motoruna ulaşılamadı. Yeniden bağlanmayı dene.") from exc
        if not response or not response.get("ok"):
            raise LiveMatchError("Maç motoru komutu tamamlayamadı.")
        return response

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.reader.join()
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()


class LiveMatch:
    def __init__(self, path, key, kickoff, config):
        self.path = path
        self.key = key
        self.kickoff = kickoff
        self.config = config
        self.worker = None
        self.state = None
        self.lock = threading.RLock()
        self.presence = [0, 0]
        self.decision_id = None
        self.deadline = 0
        self.next_step = None
        self.catchup_steps = 0
        self.step_index = 0
        self.last_frame_step = -120
        self.replay_incompatible = False

    def initialize(self, now):
        if self.state is not None:
            return
        if self.replay_incompatible:
            raise ReplayMismatch()
        with closing(connect(self.path)) as database:
            final, = database.execute(
                f"SELECT final_state FROM live_matches WHERE {FIXTURE_KEY}", self.key
            ).fetchone()
            operations = database.execute(
                f"SELECT operation FROM live_match_operations WHERE {FIXTURE_KEY} ORDER BY seq", self.key
            ).fetchall()
            latest_frame = database.execute(
                f"SELECT step,snapshot FROM live_match_frames WHERE {FIXTURE_KEY} ORDER BY step DESC LIMIT 1", self.key
            ).fetchone()
        self.last_frame_step = latest_frame[0] if latest_frame else -120
        if final is not None:
            self.state = json.loads(final)
            return
        self.worker = Worker()
        advanced = 0
        try:
            state = self.worker.request({"op": "init", "config": self.config})["state"]
            checkpoint = state if self.last_frame_step == 0 else None
            for raw, in operations:
                operation = json.loads(raw)
                reply = self.worker.request(operation)
                state = reply["state"]
                if operation["op"] == "advance":
                    if reply.get("steps") != operation["steps"]:
                        raise ReplayMismatch()
                    advanced += operation["steps"]
                elif operation["op"] != "kick" or reply.get("accepted") is not True:
                    raise ReplayMismatch()
                if advanced == self.last_frame_step:
                    checkpoint = state  # a kick can update the frame at the same step
            if state.get("done") or (latest_frame and not matches_checkpoint(json.loads(latest_frame[1]), checkpoint)):
                raise ReplayMismatch()
        except Exception as exc:
            self.discard_worker()
            if isinstance(exc, ReplayMismatch):
                self.replay_incompatible = True
            raise
        self.state = state
        self.step_index = advanced
        self.next_step = now
        # Kickoff is a wall-clock timestamp; 'now' is monotonic for the running
        # worker. After a restart or late spectator, catch up only the steps
        # that were not already committed. No replay needs a client to join.
        elapsed_steps = max(0, int((time.time() - self.kickoff) / STEP_SECONDS))
        self.catchup_steps = max(0, elapsed_steps - advanced)
        if self.last_frame_step < 0:
            with closing(connect(self.path)) as database, database:
                database.execute("""INSERT OR IGNORE INTO live_match_frames
                    (league,round,home,away,step,snapshot) VALUES(?,?,?,?,?,?)""",
                    (*self.key, 0, encode(state)))
            self.last_frame_step = 0
        self.remember_prompt(now)

    def discard_worker(self):
        if self.worker is not None:
            self.worker.close()
            self.worker = None
        self.state = None

    def remember_prompt(self, now):
        offer = self.state.get("pendingManagerKick")
        prompt_id = offer["id"] if offer else None
        if prompt_id != self.decision_id:
            self.decision_id = prompt_id
            self.deadline = now + DECISION_SECONDS if prompt_id is not None else 0

    def apply(self, operation, now):
        try:
            reply = self.worker.request(operation)
            if operation["op"] == "kick" and not reply["accepted"]:
                return reply
            state = reply["state"]
            if operation["op"] == "advance":
                operation = {**operation, "steps": reply["steps"]}
            new_index = self.step_index + (reply["steps"] if operation["op"] == "advance" else 0)
            with closing(connect(self.path)) as database, database:
                # Keep the COMPLETE deterministic operation ledger after
                # full time. Replaying frozen config plus this log regenerates
                # ball, positions, refereeing and future decisions.
                database.execute("""INSERT INTO live_match_operations
                    (league,round,home,away,operation) VALUES (?,?,?,?,?)""",
                    (*self.key, encode(operation)))
                if state["done"]:
                    home, away = state["score"]
                    hy, ay = state["cards"]
                    hr, ar = state["reds"]
                    updated = database.execute(f"""UPDATE fixtures SET home_score=?,away_score=?,
                        home_yellows=?,away_yellows=?,home_reds=?,away_reds=?
                        WHERE {FIXTURE_KEY} AND home_score IS NULL""",
                        (home, away, hy, ay, hr, ar, *self.key))
                    if updated.rowcount:
                        # Appearances, fitness and disciplinary bans commit in
                        # the SAME transaction as the authoritative result.
                        # Crashes cause replay; UNIQUE fixture-player keys
                        # prevent duplicate minutes and yellow/red cards.
                        season_state.apply_fixture(database, self.key, state.get("appearances", []))
                    database.execute(f"UPDATE live_matches SET final_state=? WHERE {FIXTURE_KEY}",
                                     (encode(state), *self.key))
                if state["done"] or operation["op"] == "kick" or new_index - self.last_frame_step >= 120:
                    database.execute("""INSERT INTO live_match_frames
                        (league,round,home,away,step,snapshot) VALUES(?,?,?,?,?,?)
                        ON CONFLICT(league,round,home,away,step)
                        DO UPDATE SET snapshot=excluded.snapshot""",
                        (*self.key, new_index, encode(state)))
        except Exception:
            # If a process or write fails before the commit, replay the saved
            # operations before accepting another decision.
            self.discard_worker()
            raise
        self.state = state
        self.step_index = new_index
        if state["done"] or operation["op"] == "kick" or new_index - self.last_frame_step >= 120:
            self.last_frame_step = new_index
        self.remember_prompt(now)
        if state["done"]:
            self.worker.close()
            self.worker = None
        return reply

    def expire_prompt(self, now):
        offer = self.state.get("pendingManagerKick")
        if not offer:
            return
        self.next_step = now
        if now >= self.deadline or now >= self.presence[offer["team"]]:
            self.apply({"op": "kick", "id": offer["id"], "input": None}, now)

    def tick(self):
        with self.lock:
            if self.replay_incompatible:
                return False
            now = time.monotonic()
            self.initialize(now)
            if self.state["done"]:
                return True
            self.expire_prompt(now)
            if self.state.get("pendingManagerKick"):
                return False
            # Catch up to kickoff for every fixture, whether or not someone
            # ever opens a tab. Subsequent play runs at 60 fixed steps/s.
            if self.catchup_steps:
                for _ in range(4):
                    steps = min(MAX_STEPS, self.catchup_steps)
                    reply = self.apply({"op": "advance", "steps": steps, "teams": []}, now)
                    self.catchup_steps -= reply["steps"]
                    if not self.catchup_steps or self.state["done"]:
                        break
                return self.state["done"]
            steps = min(MAX_STEPS, int((now - self.next_step) / STEP_SECONDS))
            if steps > 0:
                teams = [team for team, expiry in enumerate(self.presence) if expiry > now]
                reply = self.apply({"op": "advance", "steps": steps, "teams": teams}, now)
                self.next_step += reply["steps"] * STEP_SECONDS
                if self.decision_id is not None:
                    self.next_step = now
            return self.state["done"]

    def read(self, side):
        with self.lock:
            now = time.monotonic()
            self.initialize(now)
            self.expire_prompt(now)
            self.presence[side] = now + PRESENCE_SECONDS
            return self.view(side, now)

    def kick(self, side, prompt_id, control):
        with self.lock:
            now = time.monotonic()
            self.initialize(now)
            self.expire_prompt(now)
            offer = self.state.get("pendingManagerKick")
            if not offer or offer["id"] != prompt_id or offer["team"] != side:
                raise LiveMatchError("Bu vuruş artık seçilemiyor veya diğer takıma ait.", 409)
            reply = self.apply({"op": "kick", "id": prompt_id, "input": control}, now)
            if not reply["accepted"]:
                raise LiveMatchError("Vuruş seçimi geçerli aralığın dışında.", 400)
            self.next_step = now
            self.presence[side] = now + PRESENCE_SECONDS
            return self.view(side, now)

    def view(self, side, now):
        return {
            "state": self.state, "side": side, "homeName": self.config["homeName"],
            "awayName": self.config["awayName"], "homeFormation": self.config["formation"],
            "awayFormation": self.config["awayFormation"],
            "fixture": dict(zip(("league", "round", "home", "away", "kickoff"), (*self.key, self.kickoff))),
            "opponentPresent": self.presence[1 - side] > now and not self.state["done"],
            "decisionSeconds": max(0, math.ceil(self.deadline - now)) if self.decision_id is not None else None,
            "catchingUp": self.catchup_steps > 0 and not self.state["done"],
        }


def kick_control(body):
    if not isinstance(body, dict) or type(body.get("id")) is not int or not 0 < body["id"] < 2**53:
        raise LiveMatchError("Geçerli bir vuruş seçimi gerekli.", 400)
    control = body.get("input")
    if "input" not in body:
        raise LiveMatchError("Vuruş seçimi eksik.", 400)
    if control is not None:
        fields = ("angle", "power", "contactX", "contactY")
        if not isinstance(control, dict) or not all(
            type(control.get(key)) in (int, float) and -1000 <= control[key] <= 1000
            for key in fields
        ):
            raise LiveMatchError("Vuruş değerleri geçersiz.", 400)
        control = {key: control[key] for key in fields}
        if not 0 <= control["power"] <= 1 or math.hypot(control["contactX"], control["contactY"]) > 1 + 1e-6:
            raise LiveMatchError("Güç veya temas noktası geçersiz.", 400)
    return body["id"], control


class Registry:
    def __init__(self):
        self.matches = {}
        self.lock = threading.Lock()

    def get(self, path, key, kickoff, config):
        identity = (path, key)
        with self.lock:
            session = self.matches.get(identity)
            if session is None:
                session = self.matches[identity] = LiveMatch(path, key, kickoff, config)
            return session

    def restore(self, path):
        with closing(connect(path)) as database:
            rows = database.execute("""SELECT league,round,home,away,kickoff,config
                                       FROM live_matches WHERE final_state IS NULL""").fetchall()
        for *key, kickoff, config in rows:
            self.get(path, tuple(key), kickoff, json.loads(config))

    def tick(self):
        with self.lock:
            matches = tuple(self.matches.items())
        for identity, session in matches:
            try:
                if session.tick():
                    with self.lock:
                        self.matches.pop(identity, None)
            except (LiveMatchError, sqlite3.Error) as exc:
                print("Canlı maç:", str(exc), flush=True)

    def close(self):
        with self.lock:
            matches, self.matches = self.matches, {}
        for session in matches.values():
            with session.lock:
                session.discard_worker()
