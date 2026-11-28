"""Persistent local fixture-to-replay schedule, independent of viewers.

This schedules a reviewed completed recording, not a native match launch.
No native save or web league score is changed.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from contextlib import closing
from original_shared_replay import ReplayServer

def fixture_identity(fixture):
    if not isinstance(fixture,dict):
        raise ValueError('Explicit fixture required')
    league=fixture.get('league')
    if (not isinstance(league,str) or not 0<len(league)<=64 or
        any(type(fixture.get(k)) is not int or fixture[k]<0 for k in ('round','home','away')) or
        fixture['home']==fixture['away']):
        raise ValueError('Invalid fixture identity')
    kickoff=fixture.get('kickoff')
    if type(kickoff) not in (int,float) or not math.isfinite(kickoff) or kickoff<=0:
        raise ValueError('Invalid UTC kickoff')
    identity=json.dumps([fixture[k] for k in ('league','round','home','away')],
                        ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(identity.encode()).hexdigest(),identity,kickoff

def ledger(root):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Private schedule directory required')
    path=root/'replay-schedule.sqlite3'
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    os.close(fd)
    db=sqlite3.connect(path,timeout=5)
    try:
        db.execute('''CREATE TABLE IF NOT EXISTS schedule(
          fixture_key TEXT PRIMARY KEY, identity TEXT NOT NULL,
          kickoff REAL NOT NULL, replay_sha TEXT NOT NULL UNIQUE)''')
        db.commit()
        return db
    except Exception:
        db.close()
        raise

def schedule_replay(root,fixture,reviewed):
    """Register explicit operator-reviewed association before kickoff.

    Review is not native result provenance. Refuse replacement/rescheduling
    rather than silently reset the clock or reuse a recording for another match.
    """
    key,identity,kickoff=fixture_identity(fixture)
    if not isinstance(reviewed,dict) or reviewed.get('operatorReviewed') is not True:
        raise ValueError('Explicit recording review required')
    if reviewed.get('fixtureKey')!=key or reviewed.get('kickoff')!=kickoff:
        raise ValueError('Review does not match fixture and kickoff')
    sha=reviewed.get('replaySha256')
    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):
        raise ValueError('Invalid replay digest')
    with closing(ledger(root)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT identity,kickoff,replay_sha FROM schedule WHERE fixture_key=?',(key,)).fetchone()
        if row is not None:
            if row!=(identity,kickoff,sha):
                raise ValueError('Fixture replay schedule is immutable')
            return dict(fixtureKey=key,created=False,kickoff=kickoff,replaySha256=sha,scoreWritten=False)
        if db.execute('SELECT 1 FROM schedule WHERE replay_sha=?',(sha,)).fetchone():
            raise ValueError('Recording already associated with another fixture')
        db.execute('INSERT INTO schedule VALUES(?,?,?,?)',(key,identity,kickoff,sha))
    return dict(fixtureKey=key,created=True,kickoff=kickoff,replaySha256=sha,scoreWritten=False)

def schedule_status(root,key,now=None):
    if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):
        raise ValueError('Invalid fixture key')
    now=time.time() if now is None else now
    if type(now) not in (int,float) or not math.isfinite(now):
        raise ValueError('Invalid UTC clock')
    with closing(ledger(root)) as db:
        row=db.execute('SELECT kickoff,replay_sha FROM schedule WHERE fixture_key=?',(key,)).fetchone()
    if row is None:
        raise ValueError('Unknown fixture schedule')
    kickoff,sha=row
    elapsed=now-kickoff
    return dict(fixtureKey=key,kickoff=kickoff,replaySha256=sha,
                phase='waiting' if elapsed<0 else 'finished' if elapsed>=300 else 'playing',
                positionSeconds=min(300,max(0,elapsed)),durationSeconds=300,
                nativeKickoffVerified=False,nativeResultVerified=False,
                scoreWritten=False,liveSimulation=False)

def open_scheduled_replay(root,key,path,port=0):
    state=schedule_status(root,key)
    return ReplayServer(path,state['replaySha256'],port=port,
                        scheduled_epoch=state['kickoff'],fixture_key=key)

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('fixture',type=Path,help='Reviewed local fixture JSON')
    parser.add_argument('review',type=Path,help='Explicit local replay review JSON')
    parser.add_argument('recording',type=Path)
    parser.add_argument('--port',type=int,default=8766)
    args=parser.parse_args()
    fixture=json.loads(args.fixture.read_text())
    review=json.loads(args.review.read_text())
    # Validate the actual recording before persisting the schedule.
    key,_,kickoff=fixture_identity(fixture)
    with ReplayServer(args.recording,review.get('replaySha256',''),
                      port=args.port,scheduled_epoch=kickoff,fixture_key=key) as server:
        schedule_replay(args.root,fixture,review)
        print(json.dumps(schedule_status(args.root,key)),flush=True)
        print(f'Private replay: http://127.0.0.1:{server.server_port}/viewer',flush=True)
        server.serve_forever()

if __name__=='__main__':
    main()
