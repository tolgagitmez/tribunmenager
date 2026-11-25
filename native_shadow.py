"""Opt-in native shadow fixture queue. Never writes league results or player season data."""
from __future__ import annotations
from contextlib import closing
import gzip
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

def process_one(path, runner=execute_native, stop=None):
    job = claim(path)
    if not job:
        return False
    key, sha, profile, config = job
    try:
        raw, report = runner(config, profile, stop)
        validate_result(raw, report)
        packed = gzip.compress(raw, compresslevel=3, mtime=0)
        trace_sha = hashlib.sha256(raw).hexdigest()
        with closing(connect(path)) as db, db:
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
    row = db.execute(f"""SELECT n.state,n.profile,n.attempts,n.report,n.trace_sha,l.kickoff
        FROM native_shadow_matches n JOIN live_matches l USING(league,round,home,away)
        WHERE n.league=? AND n.round=? AND n.home=? AND n.away=?""", key).fetchone()
    if not row:
        return {"engine": "league-soccer", "state": "not-enabled", "authoritative": False}
    state, profile, attempts, report, sha, kickoff = row
    # No final result disclosed during the official five-minute window.
    visible = state == "ready" and now >= kickoff + 300
    return {"engine": "league-soccer", "state": state, "profile": profile,
            "attempts": attempts, "authoritative": False,
            "report": json.loads(report) if visible else None, "traceSHA256": sha if visible else None}
