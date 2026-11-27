"""Persistent external fixture dispatch ledger; no native DB writes or launch.

A claim is intentionally never auto-retried, even after a crash. Native result
reconciliation must precede a future retry mechanism.
"""
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import time

from original_fixture_gate import eligibility,next_native_fixture
from original_engine import digest
from original_saves import locked_store,current_snapshot

WEB_FIELDS=('league','round','home','away','kickoff')
NATIVE_FIELDS=('nativeFixtureId','homeTeamId','awayTeamId','nativeDate','managedTeamId')


def claim_fixture(root,save_name,fixture,reviewed,now=None):
    """Claim a due fixture against the current *closed* native save.

    All callers must use the same per-revision store. This is a dispatch
    reservation only, not proof that a match has started or completed.
    """
    now=time.time() if now is None else now
    with locked_store(root) as root:
        return claim_locked(root,save_name,fixture,reviewed,now)


def claim_locked(root,save_name,fixture,reviewed,now):
    """Internal dispatch operation; caller must hold the native store lock."""
    if not isinstance(save_name,str) or not save_name or len(save_name)>128 or save_name in ('.','..') or '/' in save_name or '\\' in save_name:
        raise ValueError('Explicit native save name required')
    if not isinstance(fixture,dict) or not isinstance(reviewed,dict):
        raise ValueError('Explicit fixture mapping required')
    league=fixture.get('league')
    if (not isinstance(league,str) or not 0<len(league)<=64 or
        any(type(fixture.get(k)) is not int or fixture[k]<0 for k in ('round','home','away')) or
        fixture['home']==fixture['away']):
        raise ValueError('Invalid web fixture identity')
    snapshot=current_snapshot(root)
    if snapshot is None:
        return dict(claimed=False,reason='no-closed-native-save',automaticLaunch=False)
    folder=snapshot/save_name
    path=folder/'autosave.sqlite'
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('Native save folder unavailable')
    if reviewed.get('snapshotId')!=snapshot.name or reviewed.get('saveName')!=save_name:
        return dict(claimed=False,reason='stale-reviewed-snapshot',automaticLaunch=False)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Invalid native autosave')
    before=digest(path)
    if reviewed.get('saveSha256')!=before:
        return dict(claimed=False,reason='stale-reviewed-save',automaticLaunch=False)
    native=next_native_fixture(path)
    gate=eligibility(fixture,reviewed,native,now)
    if not gate['eligible']:
        return dict(claimed=False,reason=gate['reason'],automaticLaunch=False)
    if digest(path)!=before:
        raise RuntimeError('Native save changed before claim')
    # Use the web fixture identity without kickoff: rescheduling must not
    # create a second claim for the same league/round/home/away.
    identity=json.dumps([fixture[k] for k in WEB_FIELDS[:-1]],ensure_ascii=False,separators=(',',':'))
    key=hashlib.sha256(identity.encode()).hexdigest()
    payload=json.dumps({k:reviewed[k] for k in WEB_FIELDS+NATIVE_FIELDS},ensure_ascii=False,sort_keys=True)
    ledger=root/'fixture-dispatch.sqlite3'
    if ledger.is_symlink() or ledger.exists() and not ledger.is_file():
        raise ValueError('Invalid external dispatch ledger')
    fd=os.open(ledger,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    os.close(fd)
    with closing(sqlite3.connect(ledger)) as db:
        with db:
            db.execute('''CREATE TABLE IF NOT EXISTS claims(
                key TEXT PRIMARY KEY, mapping TEXT NOT NULL,
                snapshot TEXT NOT NULL, save_name TEXT NOT NULL,
                save_sha256 TEXT NOT NULL, claimed_at REAL NOT NULL)''')
            # The same native fixture must not be assigned to another web
            # fixture, even when its snapshot ID or scheduled time changes.
            for old_key,old_mapping in db.execute('SELECT key,mapping FROM claims WHERE save_name=?',(save_name,)):
                previous=json.loads(old_mapping)
                if old_key!=key and all(previous.get(k)==reviewed[k] for k in NATIVE_FIELDS):
                    return dict(claimed=False,reason='native-fixture-already-reserved',automaticLaunch=False)
            result=db.execute('INSERT OR IGNORE INTO claims VALUES(?,?,?,?,?,?)',
                (key,payload,snapshot.name,save_name,before,now))
            created=result.rowcount==1
    return dict(claimed=created,reason='reserved-for-review' if created else 'already-reserved',
                fixtureKey=key,automaticLaunch=False,scoreWritten=False,
                requiresReconciliation=True)


def reconcile_locked(root,key):
    """Inspect the exact reserved result, never infer a rendered match or write a score."""
    from original_catalog import connect
    with closing(connect(root/'fixture-dispatch.sqlite3')) as ledger:
        claim=ledger.execute('SELECT mapping,snapshot,save_name,save_sha256 FROM claims WHERE key=?',(key,)).fetchone()
    if claim is None:
        raise ValueError('Unknown fixture reservation')
    mapping,old_snapshot,save_name,old_hash=claim
    mapping=json.loads(mapping)
    snapshot=current_snapshot(root)
    result=dict(fixtureKey=key,scoreWritten=False,renderedMatchVerified=False,requiresReconciliation=True)
    if snapshot is None or snapshot.name==old_snapshot:
        return dict(result,reason='no-new-closed-save')
    path=snapshot/save_name/'autosave.sqlite'
    if path.parent.is_symlink() or not path.is_file() or path.is_symlink():
        return dict(result,reason='reserved-save-missing')
    before=digest(path)
    with closing(connect(path)) as db:
        settings=db.execute('SELECT team_id FROM settings LIMIT 2').fetchall()
        fixture=db.execute('SELECT team1_id,team2_id,timestamp FROM calendar WHERE id=?',(mapping['nativeFixtureId'],)).fetchall()
        if settings!=[(mapping['managedTeamId'],)] or fixture!=[(mapping['homeTeamId'],mapping['awayTeamId'],mapping['nativeDate'])]:
            return dict(result,reason='native-fixture-mismatch')
        rows=db.execute('SELECT team1_id,team2_id,team1_goals,team2_goals FROM match_results WHERE calendar_id=? AND played=1',(mapping['nativeFixtureId'],)).fetchall()
    if digest(path)!=before:
        raise RuntimeError('Native save changed during reconciliation')
    if not rows:
        return dict(result,reason='no-completed-native-result')
    if len(rows)!=1 or rows[0][:2]!=(mapping['homeTeamId'],mapping['awayTeamId']) or any(type(v) is not int or not 0<=v<=99 for v in rows[0][2:]):
        return dict(result,reason='ambiguous-native-result')
    return dict(result,reason='native-result-candidate',nativeFixtureId=mapping['nativeFixtureId'],
                homeGoals=rows[0][2],awayGoals=rows[0][3],requiresRenderedMatchEvidence=True)


def launch_reviewed(root,build,env,save_name,fixture,reviewed,now=None):
    """Opt-in local desktop session only; not unattended kickoff.

    Claim and launch share the same store lock. No arbitrary engine arguments.
    A crash keeps the claim and prevents an automatic retry.
    """
    import original_engine
    with locked_store(root) as root:
        claim=claim_locked(root,save_name,fixture,reviewed,time.time() if now is None else now)
        if not claim['claimed']:
            return claim
        # The native menu remains the operator's responsibility.
        code=original_engine.launch_session(build,env,None,root)
        outcome=dict(claim,desktopSessionLaunched=True,exitCode=code,
                     automaticKickoff=False)
        if code==0:
            outcome['reconciliation']=reconcile_locked(root,claim['fixtureKey'])
        return outcome
