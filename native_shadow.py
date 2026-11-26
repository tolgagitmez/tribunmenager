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
import native_live

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
""" + native_live.SCHEMA

def connect(path):
    return sqlite3.connect(path, timeout=20)

def canonical(config):
    return json.dumps(config, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

def digest(config):
    return hashlib.sha256(canonical(config).encode()).hexdigest()

def enabled():
    return os.environ.get("TRIBUN_NATIVE_SHADOW") == "1"

def worker_count(raw=None):
    raw=os.environ.get("TRIBUN_NATIVE_WORKERS","1") if raw is None else raw
    if raw not in ("1","2","3"):
        raise ValueError("TRIBUN_NATIVE_WORKERS must be 1, 2 or 3")
    return int(raw)

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
    if os.environ.get("TRIBUN_NATIVE_INTERACTIVE")=="1":
        db.execute("INSERT OR IGNORE INTO native_interactive_matches VALUES(?,?,?,?)",key)

def recover(path):
    # Single dev-server process is required; don't run multiple schedulers on this database.
    with closing(connect(path)) as db, db:
        db.execute("""UPDATE native_shadow_matches SET state=CASE WHEN attempts<2 AND NOT EXISTS(SELECT 1 FROM native_interactive_matches i WHERE i.league=native_shadow_matches.league AND i.round=native_shadow_matches.round AND i.home=native_shadow_matches.home AND i.away=native_shadow_matches.away) THEN 'queued'
            ELSE 'failed' END, error='Interrupted native process' WHERE state='running'""")

def claim(path):
    with closing(connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT n.league,n.round,n.home,n.away,n.config_sha,n.profile,l.config,n.attempts
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
        return key, sha, profile, config, row[7]+1

def execute_native(config, profile, stop=None, interactive_key=None):
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
        # A trusted local command mailbox must not leak into frozen league shadow jobs.
        env.pop("TRIBUN_LEAGUE_SOCCER_COMMAND_DIR", None)
        env.pop("TRIBUN_NATIVE_REALTIME",None)
        env.pop("TRIBUN_NATIVE_CLOCK_SCALE",None)
        env.pop("TRIBUN_NATIVE_QUICK_RESTARTS",None)
        env.pop("TRIBUN_NATIVE_FIXED_DURATION",None)
        env.pop("TRIBUN_NATIVE_FINAL_THIRD_RETENTION",None)
        env.pop("TRIBUN_NATIVE_BOX_LANE_RUNS",None)
        env.pop("TRIBUN_NATIVE_TIMED_ATTACK",None)
        env.pop("TRIBUN_NATIVE_EXPERIMENTAL_SUBSTITUTIONS",None)
        # Diagnostic renderer flags must never leak into ordinary/interactive matches.
        for flag in ("TRIBUN_NATIVE_NO_DRAW","TRIBUN_NATIVE_NO_UPLOAD","TRIBUN_NATIVE_NULL_RENDERER","TRIBUN_NATIVE_SHARED_ASSETS","TRIBUN_NATIVE_LEAN_SCENE","TRIBUN_NATIVE_VISUAL_RNG","TRIBUN_NATIVE_SKIP_PITCH_TEXTURE","TRIBUN_NATIVE_TASK_WORKERS","TRIBUN_NATIVE_POSITION_SKINNING","TRIBUN_NATIVE_DETERMINISM","TRIBUN_NATIVE_ORDERED_POSE","TRIBUN_NATIVE_COLLISION_POSE","TRIBUN_NATIVE_CONTACT_INTERVAL_MS","TRIBUN_NATIVE_ADAPTIVE_CONTACT","TRIBUN_NATIVE_SURFACE_IMPACT","TRIBUN_NATIVE_ANGULAR_IMPACT","TRIBUN_NATIVE_SWEPT_IMPACT","TRIBUN_NATIVE_SPLIT_IMPACT","TRIBUN_NATIVE_CHAIN_IMPACT","TRIBUN_NATIVE_LIMB_IMPACT","TRIBUN_NATIVE_LINE_BREAK","TRIBUN_NATIVE_RUN_LANES","TRIBUN_NATIVE_TRIANGLE","TRIBUN_NATIVE_CREATIVE_CARRY","TRIBUN_NATIVE_DUEL","TRIBUN_NATIVE_HOLD_UP","TRIBUN_NATIVE_FINISH","TRIBUN_NATIVE_KEEPER_AI","TRIBUN_NATIVE_DEFENSE_SHAPE"):
            env.pop(flag,None)
        env.setdefault("LP_NUM_THREADS","2")
        env.setdefault("OMP_NUM_THREADS","1")
        tail=None
        if interactive_key is not None:
            directory=root/"commands"
            directory.mkdir(mode=0o700)
            session=native_live.Session(config,directory)
            native_live.register(interactive_key,session)
            tail=native_live.Tail(trace,session)
            env["TRIBUN_LEAGUE_SOCCER_COMMAND_DIR"]=str(directory)
            env["TRIBUN_NATIVE_REALTIME"]="1"
        resource_file=root/"resources.json"
        command=["bash",str(INTEGRATION/"run-frozen.sh"),runtime,str(config_path),str(trace)]
        # GNU time: peak single-process RSS, not aggregate memory.
        if Path("/usr/bin/time").is_file():
            command=["/usr/bin/time","-o",str(resource_file),"-f",'{"userSeconds":%U,"systemSeconds":%S,"maxRssKiB":%M,"elapsedSeconds":%e}',*command]
        launch=time.monotonic()
        with (root / "native.log").open("wb") as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 900
            try:
                while process.poll() is None:
                    if tail:tail.drain()
                    if trace.exists() and trace.stat().st_size>MAX_TRACE:
                        raise RuntimeError("Native trace exceeded size budget")
                    if stop is not None and stop.wait(.2):
                        raise RuntimeError("Native worker stopped")
                    if stop is None:
                        time.sleep(.2)
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Native worker timed out")
                if tail:tail.drain()
                if process.returncode:
                    raise RuntimeError("Native worker failed validation or execution")
            finally:
                if tail:session.close()
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        elapsed=round((time.monotonic()-launch)*1000)
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
        report["runtimeMetrics"]={"processWallMs":elapsed,"traceBytes":len(raw),"interactiveTiming":session.timing() if tail else None}
        if resource_file.is_file():
            try:
                metrics=json.loads(resource_file.read_text())
                if all(type(v) in (float,int) and math.isfinite(v) and v>=0 for v in metrics.values()):
                    report["runtimeMetrics"]["resources"]=metrics
            except (ValueError,OSError,AttributeError):
                pass
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

def commit_shadow_result(path, key, sha, profile, attempt, raw, report):
    """Publish only the currently leased attempt, atomically with its frame index."""
    validate_result(raw, report)
    if report.get("authoritative") is True:
        raise ValueError("Shadow result cannot be authoritative")
    rows = frame_rows(raw)
    packed = gzip.compress(raw, compresslevel=3, mtime=0)
    trace_sha = hashlib.sha256(raw).hexdigest()
    # Bind the report to the frozen configuration and specific execution attempt.
    bound = {**report, "authoritative":False, "provenance":{
        "configSha256":sha, "traceSha256":trace_sha, "profile":profile, "attempt":attempt}}
    with closing(connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        current = db.execute("""SELECT n.state,n.config_sha,n.profile,n.attempts,l.config
            FROM native_shadow_matches n JOIN live_matches l USING(league,round,home,away)
            WHERE n.league=? AND n.round=? AND n.home=? AND n.away=?""", key).fetchone()
        if not current or tuple(current[:4]) != ("running",sha,profile,attempt):
            return False
        if digest(json.loads(current[4])) != sha:
            raise ValueError("Frozen config changed after claim")
        updated=db.execute(f"""UPDATE native_shadow_matches SET state='ready',finished=?,trace_sha=?,
            trace=?,report=?,error=NULL WHERE {KEY} AND state='running' AND config_sha=? AND profile=? AND attempts=?""",
            (time.time(),trace_sha,packed,canonical(bound),*key,sha,profile,attempt))
        if updated.rowcount!=1:
            raise RuntimeError("Native lease lost inside transaction")
        index_frames(db,key,rows)
        return True

def fail_shadow_attempt(path,key,sha,profile,attempt,error):
    """A late failure must not invalidate a newer attempt or a ready result."""
    with closing(connect(path)) as db, db:
        return db.execute(f"""UPDATE native_shadow_matches SET state='failed',finished=?,error=?
            WHERE {KEY} AND state='running' AND config_sha=? AND profile=? AND attempts=?""",
            (time.time(),error,*key,sha,profile,attempt)).rowcount==1

def process_one(path, runner=execute_native, stop=None):
    job = claim(path)
    if not job:
        return False
    key, sha, profile, config, attempt = job
    try:
        with closing(connect(path)) as db:
            interactive=native_live.is_interactive(db,key)
        if interactive:
            if runner is not execute_native:raise RuntimeError("Interactive pilot requires native runner")
            raw, report = runner(config, profile, stop, interactive_key=key)
        else:
            raw, report = runner(config, profile, stop)
        if not commit_shadow_result(path,key,sha,profile,attempt,raw,report):
            print("Native shadow: discarded stale completion",key,attempt,flush=True)
    except Exception as exc:
        # No old-engine fallback masquerades as native output.
        fail_shadow_attempt(path,key,sha,profile,attempt,type(exc).__name__)
        print("Native shadow:", type(exc).__name__, str(exc), flush=True)
    finally:
        native_live.remove(key)
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
            names.append({"nativeId":team*11+slot+1,"name":p.get("name",""),"number":p.get("number",slot+1),"slot":slot,"team":team,"position":p.get("subposition") or p.get("pos"),"rating":p.get("rating"),"startFitness":p.get("fitness"),"reserve":False})
        reserves=[p for p in config.get(roster_key,[]) if p["id"] not in config.get(starters_key,[]) and p.get("owned") is not False and not p.get("season",{}).get("suspended")][:7]
        for i,p in enumerate(reserves):
            names.append({"nativeId":23+team*7+i,"name":p.get("name",""),"number":p.get("number",12+i),"slot":11+i,"team":team,"position":p.get("subposition") or p.get("pos"),"rating":p.get("rating"),"startFitness":p.get("fitness"),"reserve":True})
    result.update(frame=frame, sequence=seq, players=names,
                  homeName=config.get("homeName","Ev sahibi"),awayName=config.get("awayName","Deplasman"))
    return result

def interactive_broadcast(db,key,side):
    session=native_live.lookup(key)
    if session:
        return session.read(side)
    row=db.execute(f"SELECT state FROM native_shadow_matches WHERE {KEY}",key).fetchone()
    state=row[0] if row else "not-enabled"
    result=dict(engine="league-soccer",authoritative=False,source="interactive-native",state=state,
                phase="waiting",frame=None,side=side,canControl=False)
    if state=="ready":
        final=db.execute(f"SELECT seq,snapshot FROM native_shadow_frames WHERE {KEY} ORDER BY seq DESC LIMIT 1",key).fetchone()
        config=db.execute(f"SELECT config FROM live_matches WHERE {KEY}",key).fetchone()
        if not final or not config:raise ValueError("Missing validated final")
        frame=json.loads(gzip.decompress(final[1]))
        if not frame.get("done"):raise ValueError("Missing final frame")
        result.update(phase="finished",frame=frame,sequence=final[0],**native_live.metadata(json.loads(config[0])))
    return result
