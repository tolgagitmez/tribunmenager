"""Opt-in native shadow fixture queue. Never writes league results or player season data."""
from __future__ import annotations
from contextlib import closing
import gzip
import math
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent
INTEGRATION = ROOT / "integrations" / "league-soccer"
KEY = "league=? AND round=? AND home=? AND away=?"
MAX_TRACE = 100 * 1024 * 1024
SCHEMA = """
CREATE TABLE IF NOT EXISTS native_shadow_matches(
    league TEXT NOT NULL, round INTEGER NOT NULL, home INTEGER NOT NULL, away INTEGER NOT NULL,
    config_sha TEXT NOT NULL, profile TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0, started REAL, finished REAL,
    trace_sha TEXT, trace BLOB, report TEXT, error TEXT,
    PRIMARY KEY(league,round,home,away)
);
CREATE TABLE IF NOT EXISTS native_shadow_frames(
    league TEXT NOT NULL, round INTEGER NOT NULL, home INTEGER NOT NULL, away INTEGER NOT NULL,
    seq INTEGER NOT NULL, elapsed_ms INTEGER NOT NULL, snapshot BLOB NOT NULL,
    PRIMARY KEY(league,round,home,away,seq)
);
CREATE INDEX IF NOT EXISTS native_shadow_due_frame
ON native_shadow_frames(league,round,home,away,elapsed_ms,seq);
"""

def connect(path):
    return sqlite3.connect(path, timeout=20)

def canonical(config):
    return json.dumps(config, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

def digest(config):
    return hashlib.sha256(canonical(config).encode()).hexdigest()

def enabled():
    return os.environ.get("TRIBUN_NATIVE_SHADOW") == "1"

def enqueue(db, key, config):
    if not enabled():
        return
    # Baseline stays default until the experimental attack benchmark passes.
    profile = os.environ.get("TRIBUN_NATIVE_SHADOW_PROFILE", "baseline")
    if profile not in ("baseline", "short-match"):
        # A pilot misconfiguration must never stop the official kickoff.
        db.execute("""INSERT OR IGNORE INTO native_shadow_matches
            (league,round,home,away,config_sha,profile,state,error) VALUES(?,?,?,?,?,?,'failed','Invalid shadow profile')""",
            (*key, digest(config), profile))
        return
    db.execute("""INSERT OR IGNORE INTO native_shadow_matches
        (league,round,home,away,config_sha,profile) VALUES(?,?,?,?,?,?)""",
        (*key, digest(config), profile))

def recover(path):
    # Single dev-server process is required; don't run multiple schedulers on this database.
    with closing(connect(path)) as db, db:
        db.execute("""UPDATE native_shadow_matches SET state=CASE WHEN attempts<2 THEN 'queued'
            ELSE 'failed' END, error='Interrupted native process' WHERE state='running'""")

def claim(path):
    with closing(connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT n.league,n.round,n.home,n.away,n.config_sha,n.profile,l.config
            FROM native_shadow_matches n JOIN live_matches l USING(league,round,home,away)
            WHERE n.state='queued' ORDER BY l.kickoff,n.league,n.round,n.home LIMIT 1""").fetchone()
        if not row:
            return None
        key, sha, profile, raw = tuple(row[:4]), row[4], row[5], row[6]
        config = json.loads(raw)
        if digest(config) != sha:
            db.execute(f"UPDATE native_shadow_matches SET state='failed',error='Frozen config mismatch' WHERE {KEY}", key)
            return None
        db.execute(f"""UPDATE native_shadow_matches SET state='running',attempts=attempts+1,
            started=?,error=NULL WHERE {KEY}""", (time.time(), *key))
        return key, sha, profile, config

def execute_native(config, profile, stop=None):
    runtime = os.environ.get("TRIBUN_NATIVE_RUNTIME")
    if not runtime:
        raise RuntimeError("Prepared native runtime required")
    # Never write recordings in the public static web directory.
    with tempfile.TemporaryDirectory(prefix="tribun-native-") as tmp:
        root = Path(tmp)
        config_path = root / "config.json"
        config_path.write_text(canonical(config), encoding="utf-8")
        trace = root / "match.ndjson"
        env = {**os.environ, "TRIBUN_LEAGUE_SOCCER_ATTACK": profile}
        with (root / "native.log").open("wb") as log:
            process = subprocess.Popen(["bash", str(INTEGRATION / "run-frozen.sh"), runtime,
                str(config_path), str(trace)], env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 900
            try:
                while process.poll() is None:
                    if stop is not None and stop.wait(.2):
                        raise RuntimeError("Native worker stopped")
                    if stop is None:
                        time.sleep(.2)
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Native worker timed out")
                if process.returncode:
                    raise RuntimeError("Native worker failed validation or execution")
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        if not 0 < trace.stat().st_size <= MAX_TRACE:
            raise RuntimeError("Native trace size invalid")
        raw = trace.read_bytes()
        report = json.loads(Path(str(trace) + ".attack.json").read_text())
        if report.get("engine") != "league-soccer" or not report.get("sampled"):
            raise RuntimeError("Native report incomplete")
        season = json.loads(Path(str(trace) + ".season.json").read_text())
        if season.get("authoritative") is not False or season.get("score") != report.get("score"):
            raise RuntimeError("Native season candidate invalid")
        report["seasonCandidate"] = season
        return raw, report

def validate_result(raw, report):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_TRACE:
        raise ValueError("Invalid native trace")
    lines = raw.splitlines()
    if len(lines) < 2:
        raise ValueError("Incomplete native trace")
    first, last = lines[0], lines[-1]
    initial, final = json.loads(first), json.loads(last)
    if initial.get("engine") != "league-soccer" or final.get("engine") != "league-soccer":
        raise ValueError("Wrong engine")
    if final.get("done") is not True or final.get("matchMs", 0) < 5400000:
        raise ValueError("Incomplete match")
    score = final.get("score")
    if not isinstance(score, list) or len(score) != 2 or any(type(x) is not int or x < 0 for x in score):
        raise ValueError("Invalid score")
    if report.get("score") != score or report.get("engine") != "league-soccer":
        raise ValueError("Report score mismatch")

def frame_rows(raw):
    """Index the already-validated recording; preserve duplicate native times."""
    previous = -1
    rows = []
    for seq, line in enumerate(raw.splitlines()):
        frame = json.loads(line)
        elapsed = frame.get("elapsedMs")
        if type(elapsed) is not int or elapsed < 0 or elapsed < previous:
            raise ValueError("Invalid native frame time")
        previous = elapsed
        rows.append((seq, elapsed, gzip.compress(line, compresslevel=3, mtime=0)))
    if len(rows) < 2 or rows[-1][1] <= rows[0][1]:
        raise ValueError("Invalid native duration")
    return rows

def index_frames(db, key, rows):
    db.execute(f"DELETE FROM native_shadow_frames WHERE {KEY}", key)
    db.executemany("""INSERT INTO native_shadow_frames
        (league,round,home,away,seq,elapsed_ms,snapshot) VALUES(?,?,?,?,?,?,?)""",
        ((*key,*row) for row in rows))

def process_one(path, runner=execute_native, stop=None):
    job = claim(path)
    if not job:
        return False
    key, sha, profile, config = job
    try:
        raw, report = runner(config, profile, stop)
        validate_result(raw, report)
        rows = frame_rows(raw)
        packed = gzip.compress(raw, compresslevel=3, mtime=0)
        trace_sha = hashlib.sha256(raw).hexdigest()
        with closing(connect(path)) as db, db:
            index_frames(db, key, rows)
            db.execute(f"""UPDATE native_shadow_matches SET state='ready',finished=?,trace_sha=?,
                trace=?,report=?,error=NULL WHERE {KEY} AND state='running' AND config_sha=?""",
                (time.time(), trace_sha, packed, canonical(report), *key, sha))
    except Exception as exc:
        # No old-engine fallback masquerades as native output.
        with closing(connect(path)) as db, db:
            db.execute(f"""UPDATE native_shadow_matches SET state='failed',finished=?,error=?
                WHERE {KEY} AND state='running'""", (time.time(), type(exc).__name__, *key))
        print("Native shadow:", type(exc).__name__, str(exc), flush=True)
    return True

def status(db, key, now):
    row = db.execute(f"""SELECT n.state,n.profile,n.attempts,n.report,n.trace_sha,l.kickoff,n.finished
        FROM native_shadow_matches n JOIN live_matches l USING(league,round,home,away)
        WHERE n.league=? AND n.round=? AND n.home=? AND n.away=?""", key).fetchone()
    if not row:
        return {"engine": "league-soccer", "state": "not-enabled", "authoritative": False}
    state, profile, attempts, report, sha, kickoff, finished = row
    # No final result disclosed during the official five-minute window.
    visible = state == "ready" and finished is not None and now >= max(kickoff, finished) + 300
    return {"engine": "league-soccer", "state": state, "profile": profile,
            "attempts": attempts, "authoritative": False,
            "report": json.loads(report) if visible else None, "traceSHA256": sha if visible else None}

def broadcast(db, key, now):
    """Only due frames from a completed shadow recording; never a future score."""
    row = db.execute("""SELECT n.state,n.profile,n.finished,l.kickoff,l.config
        FROM native_shadow_matches n JOIN live_matches l USING(league,round,home,away)
        WHERE n.league=? AND n.round=? AND n.home=? AND n.away=?""", key).fetchone()
    result = {"engine":"league-soccer","authoritative":False,"durationMs":300000,
              "state":"not-enabled","phase":"waiting","frame":None}
    if not row:
        return result
    state, profile, finished, kickoff, raw_config = row
    result.update(state=state, profile=profile)
    if state != "ready" or finished is None:
        return result
    start = max(kickoff, finished)
    elapsed = min(300000, max(0, int((now-start)*1000)))
    phase = "scheduled" if now < start else "finished" if now >= start+300 else "playing"
    result.update(phase=phase, elapsedMs=elapsed, remainingMs=300000-elapsed,
                  broadcastStartMs=int(start*1000))
    if phase == "scheduled":
        return result
    first = db.execute(f"SELECT elapsed_ms FROM native_shadow_frames WHERE {KEY} ORDER BY seq LIMIT 1",key).fetchone()
    last = db.execute(f"SELECT seq,elapsed_ms FROM native_shadow_frames WHERE {KEY} ORDER BY seq DESC LIMIT 1",key).fetchone()
    if not first or not last or last[1] <= first[0]:
        result.update(state="unindexed",phase="waiting")
        return result
    if phase == "finished":
        selected = db.execute(f"SELECT seq,snapshot FROM native_shadow_frames WHERE {KEY} AND seq=?",(*key,last[0])).fetchone()
    else:
        due = first[0]+min(last[1]-first[0]-1, (last[1]-first[0])*elapsed//300000)
        selected = db.execute(f"""SELECT seq,snapshot FROM native_shadow_frames
            WHERE {KEY} AND elapsed_ms<=? AND seq<? ORDER BY elapsed_ms DESC,seq DESC LIMIT 1""",
            (*key,due,last[0])).fetchone()
    if not selected:
        return result
    seq, packed = selected
    frame = json.loads(gzip.decompress(packed))
    if frame.get("done") and phase != "finished":
        raise ValueError("Premature final frame")
    config = json.loads(raw_config)
    # Native ID is assigned in fixture-adapter.cjs by original starting slot.
    names = []
    for team, roster_key, starters_key in ((0,"players","starters"),(1,"awayPlayers","awayStarters")):
        roster = {p["id"]:p for p in config.get(roster_key, [])}
        for slot, ident in enumerate(config.get(starters_key, [])):
            p = roster.get(ident,{})
            names.append({"nativeId":team*11+slot+1,"name":p.get("name",""),"number":p.get("number",slot+1),"slot":slot,"team":team})
    result.update(frame=frame, sequence=seq, players=names,
                  homeName=config.get("homeName","Ev sahibi"),awayName=config.get("awayName","Deplasman"))
    return result
