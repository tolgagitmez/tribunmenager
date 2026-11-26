"""Private, durable AV pilot queue tied to frozen league fixtures; never settles official scores."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import uuid
import tempfile
import math
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import native_av_season

HERE=Path(__file__).resolve().parent
SCHEMA="""
CREATE TABLE IF NOT EXISTS native_av_jobs(
 league TEXT NOT NULL, round INTEGER NOT NULL, home INTEGER NOT NULL, away INTEGER NOT NULL,
 kickoff REAL NOT NULL, config_sha TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','running','ready','failed')),
 attempt TEXT, started REAL, finished REAL, report TEXT, error TEXT,
 PRIMARY KEY(league,round,home,away)
);
CREATE INDEX IF NOT EXISTS native_av_due ON native_av_jobs(state,kickoff);
""" + native_av_season.SCHEMA
KEY="league=? AND round=? AND home=? AND away=?"

def canonical(raw):
    return json.dumps(json.loads(raw) if isinstance(raw,str) else raw,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def digest(raw):
    return hashlib.sha256(canonical(raw).encode()).hexdigest()

def sync(db, now):
    # Only frozen server-owned fixtures, already due. No schedule is generated here.
    rows=db.execute("""SELECT l.league,l.round,l.home,l.away,l.kickoff,l.config
        FROM live_matches l JOIN fixtures f USING(league,round,home,away)
        WHERE l.kickoff<=? AND f.home_score IS NULL ORDER BY l.kickoff,l.league,l.round,l.home""",(now,)).fetchall()
    count=0
    for league,round_,home,away,kickoff,raw in rows:
        count+=db.execute("""INSERT OR IGNORE INTO native_av_jobs
            (league,round,home,away,kickoff,config_sha) VALUES(?,?,?,?,?,?)""",
            (league,round_,home,away,kickoff,digest(raw))).rowcount
    return count

def claim(path, slots, now=None):
    if type(slots) is not int or not 1<=slots<=16:return None
    now=time.time() if now is None else now
    with closing(sqlite3.connect(path,timeout=20)) as db,db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT count(*) FROM native_av_jobs WHERE state='running'").fetchone()[0]>=slots:return None
        row=db.execute("""SELECT n.league,n.round,n.home,n.away,n.config_sha,l.config
            FROM native_av_jobs n JOIN live_matches l USING(league,round,home,away)
            WHERE n.state='queued' AND n.kickoff<=? ORDER BY n.kickoff,n.league,n.round,n.home,n.away LIMIT 1""",(now,)).fetchone()
        if not row:return None
        key=tuple(row[:4]);sha,raw=row[4:]
        if digest(raw)!=sha:
            db.execute("UPDATE native_av_jobs SET state='failed',error='Frozen config mismatch' WHERE "+KEY,key)
            return None
        attempt=uuid.uuid4().hex
        db.execute("UPDATE native_av_jobs SET state='running',attempt=?,started=? WHERE "+KEY,(attempt,now,*key))
        return key,sha,json.loads(raw),attempt

def finish(path,key,sha,attempt,report=None,error=None):
    if (report is None)==(error is None):raise ValueError('Exactly one completion required')
    if report is not None:
        if report.get('authoritative') is not False or report.get('configSha256')!=sha or report.get('verified') is not True or not isinstance(report.get('season'),dict):
            raise ValueError('Unverified or authoritative AV result')
    with closing(sqlite3.connect(path,timeout=20)) as db,db:
        db.row_factory=sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT config FROM live_matches WHERE "+KEY,key).fetchone()
        if not row or digest(row[0])!=sha:return False
        updated=db.execute("""UPDATE native_av_jobs SET state=?,finished=?,report=?,error=? WHERE """+KEY+
            " AND state='running' AND config_sha=? AND attempt=?",
            ('ready' if report is not None else 'failed',time.time(),canonical(report) if report is not None else None,
             error,*key,sha,attempt)).rowcount==1
        if updated and report is not None:
            native_av_season.apply(db,key,report)
        return updated

def verify_output(out,sha):
    return verify_recording(out/'fixture.json',out/'run',sha)

def verify_recording(fixture_path,directory,sha,*,control_source='local-diagnostic'):
    fixture=json.loads(fixture_path.read_text())
    if digest(fixture)!=sha:raise ValueError('Fixture mismatch')
    native=json.loads((directory/'live-report.json').read_text())
    browser=json.loads((directory/'browser-playback-report.json').read_text())
    trace=directory/'match.ndjson'
    if trace.stat().st_size>100*1024*1024:raise ValueError('Trace too large')
    raw=trace.read_bytes()
    final=json.loads(raw.splitlines()[-1])
    score=final.get('score')
    if not (native.get('status')=='local-live-evidence' and native.get('authoritative') is False
            and native.get('controlSource','local-diagnostic')==control_source
            and native['nativeClock']['nativeElapsedMs']==300000 and native['mediaTimeline']['timelinePassed'] is True
            and native['audio']['nonSilentCoveragePassed'] is True and native['audioOwnership']['verified'] is True
            and type(native['checks']['observedWallSeconds']) in (int,float) and 295<=native['checks']['observedWallSeconds']<=305
            and native['fixtureSha256']==hashlib.sha256(fixture_path.read_bytes()).hexdigest()
            and native['traceSha256']==hashlib.sha256(raw).hexdigest() and browser.get('passed') is True
            and browser.get('ended') is True and browser.get('playlistComplete') is True
            and browser['coverageFraction']>=.95 and browser['videoWidth']==1280 and browser['videoHeight']==720
            and final.get('engine')=='league-soccer' and final.get('done') is True
            and isinstance(score,list) and len(score)==2 and all(type(x) is int and x>=0 for x in score)):
        raise ValueError('Incomplete AV evidence')
    control=native['control']; evidence=control['traceEvidence']
    if not (control['submitted']==control['applied']==[1,1] and control['pending']==[False,False] and control['formations']==[442,4231]
            and evidence['consistent'] is True and evidence['allSubmittedObserved'] is True
            and len(evidence['acknowledgements'])==2 and all(a['formationTargetsVerified'] is True for a in evidence['acknowledgements'])):
        raise ValueError('Incomplete command evidence')
    manifest=json.loads(Path(str(trace)+'.fixture.json').read_text())
    # Rebuild the roster manifest from the actual frozen fixture; no substituted IDs.
    with tempfile.TemporaryDirectory(prefix='tribun-verify-') as tmp:
        dest=Path(tmp)/'fixture.txt'
        subprocess.run(['node',str(HERE/'fixture-adapter.cjs'),str(fixture_path),str(dest)],check=True,timeout=30,capture_output=True)
        expected=json.loads(Path(str(dest)+'.json').read_text())
    if manifest!=expected:raise ValueError('Native manifest differs from frozen fixture')
    sidecar=json.loads(Path(str(trace)+'.season.json').read_text())
    season=native_av_season.verify_candidate(final,manifest,sidecar)
    return {'authoritative':False,'verified':True,'configSha256':sha,'score':score,'season':season,
            'traceSha256':native['traceSha256'],'coverage':browser['coverageFraction'],'audioOwnershipVerified':True,'controlSource':control_source,'engine':'league-soccer'}

def run_match(runtime, root, job):
    key,sha,config,attempt=job
    out=root/attempt;out.mkdir(mode=0o700)
    (out/'fixture.json').write_text(canonical(config))
    env={k:v for k,v in os.environ.items() if not k.startswith(('TRIBUN_GPU_','TRIBUN_AV_','TRIBUN_EXPECT_'))}
    env.update(TRIBUN_EXPECT_AUDIO='1',TRIBUN_EXPECT_CONTROL='1',TRIBUN_EXPECT_FULL_PLAYBACK='1',TRIBUN_PLAYBACK_MIN_SECONDS='300')
    with (out/'native.log').open('wb') as n,(out/'browser.log').open('wb') as b:
        native=subprocess.Popen(['python3',str(HERE/'native-live-video.py'),str(runtime),str(out/'fixture.json'),str(out/'run'),'--audio','--interactive','--linger','60'],env=env,stdout=n,stderr=subprocess.STDOUT)
        browser=None
        try:
            browser=subprocess.Popen(['node',str(HERE/'native-live-video-browser.cjs'),str(out/'run/local-url.txt')],env=env,stdout=b,stderr=subprocess.STDOUT,start_new_session=True)
            deadline=time.monotonic()+1200
            while native.poll() is None or browser.poll() is None:
                if time.monotonic()>deadline:raise TimeoutError('AV job timed out')
                if (native.poll() not in (None,0)) or (browser.poll() not in (None,0)):raise RuntimeError('AV child failed')
                time.sleep(.5)
            if native.returncode or browser.returncode:raise RuntimeError('AV child failed')
        finally:
            import signal
            if browser is not None and browser.poll() is None:os.killpg(browser.pid,signal.SIGTERM)
            if native.poll() is None:native.terminate()
            for p in (native,browser):
                if p is None:continue
                try:p.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    if p is browser:os.killpg(p.pid,signal.SIGKILL)
                    else:p.kill()
                    p.wait()
    return verify_output(out,sha)

def main():
    from native_admission import identity,verified_slots,pressure_ok,sample_host
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('database',type=Path);p.add_argument('runtime',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args()
    db=a.database.resolve();runtime=a.runtime.resolve();out=a.output.resolve()
    if not db.is_file():p.error('Existing dev league database required')
    out.mkdir(mode=0o700,parents=True,exist_ok=True)
    slots=verified_slots(json.loads(a.evidence.read_text()),identity(runtime))
    if not slots or not pressure_ok(sample_host(out)):p.error('No verified local capacity or insufficient resources')
    # One execution per invocation; atomic reservation coordinates other workers.
    job=claim(db,slots)
    if not job:return
    key,sha,_,attempt=job
    try:
        report=run_match(runtime,out,job)
        if not finish(db,key,sha,attempt,report=report):raise RuntimeError('AV reservation lost')
    except BaseException as exc:
        finish(db,key,sha,attempt,error=type(exc).__name__)
        raise

if __name__=='__main__':main()
