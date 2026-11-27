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
    if not isinstance(save_name,str) or not save_name or len(save_name)>128 or save_name in ('.','..') or '/' in save_name or '\\' in save_name:
        raise ValueError('Explicit native save name required')
    if not isinstance(fixture,dict) or not isinstance(reviewed,dict):
        raise ValueError('Explicit fixture mapping required')
    league=fixture.get('league')
    if (not isinstance(league,str) or not 0<len(league)<=64 or
        any(type(fixture.get(k)) is not int or fixture[k]<0 for k in ('round','home','away')) or
        fixture['home']==fixture['away']):
        raise ValueError('Invalid web fixture identity')
    now=time.time() if now is None else now
    with locked_store(root) as root:
        snapshot=current_snapshot(root)
        if snapshot is None:
            return dict(claimed=False,reason='no-closed-native-save',automaticLaunch=False)
        folder=snapshot/save_name
        path=folder/'autosave.sqlite'
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError('Native save folder unavailable')
        if reviewed.get('snapshotId')!=snapshot.name or reviewed.get('saveName')!=save_name:
            return dict(claimed=False,reason='stale-reviewed-snapshot',automaticLaunch=False)
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
                result=db.execute('INSERT OR IGNORE INTO claims VALUES(?,?,?,?,?,?)',
                    (key,payload,snapshot.name,save_name,before,now))
                created=result.rowcount==1
        return dict(claimed=created,reason='reserved-for-review' if created else 'already-reserved',
                    fixtureKey=key,automaticLaunch=False,scoreWritten=False,
                    requiresReconciliation=True)
