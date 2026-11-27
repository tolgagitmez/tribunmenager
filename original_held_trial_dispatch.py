"""Connect an explicitly held web fixture to an isolated native kickoff proof.

No production scheduling, result import or automatic fallback. A durable
native claim is consumed by the existing probe before it launches the game.
"""
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

from original_fixture_dispatch import WEB_FIELDS,NATIVE_FIELDS
from original_scheduled_kickoff_probe import probe_due

REVIEW_FIELDS=WEB_FIELDS+NATIVE_FIELDS+('snapshotId','saveName','saveSha256')

def review_digest(reviewed):
    if not isinstance(reviewed,dict) or any(k not in reviewed for k in REVIEW_FIELDS):
        raise ValueError('Complete reviewed fixture mapping required')
    data=json.dumps({k:reviewed[k] for k in REVIEW_FIELDS},ensure_ascii=False,
                    sort_keys=True,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()

def held_fixture(web_db,reviewed,now):
    """Read the actual web database, not a caller-supplied fixture snapshot."""
    if type(now) not in (int,float) or not math.isfinite(now):
        raise ValueError('Invalid dispatch clock')
    expected=review_digest(reviewed)
    key=tuple(reviewed[k] for k in WEB_FIELDS[:-1])
    path=Path(web_db)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Existing web league database required')
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        predicate='league=? AND round=? AND home=? AND away=?'
        fixture=db.execute('SELECT kickoff,home_score,away_score FROM fixtures WHERE '+predicate,key).fetchone()
        hold=db.execute('SELECT kickoff,review_sha256 FROM native_fixture_holds WHERE '+predicate,key).fetchone()
        legacy=db.execute('SELECT 1 FROM live_matches WHERE '+predicate,key).fetchone()
        if fixture is None or hold is None:
            return None,'missing-native-hold'
        if fixture[0]!=reviewed['kickoff'] or hold!=(fixture[0],expected):
            return None,'reviewed-hold-mismatch'
        if legacy is not None:
            return None,'legacy-worker-conflict'
        if fixture[1] is not None or fixture[2] is not None:
            return None,'already-scored'
        if now<fixture[0]:
            return None,'not-due'
        if db.execute('SELECT 1 FROM fixtures WHERE league=? AND round<? AND (home_score IS NULL OR away_score IS NULL) LIMIT 1',key[:2]).fetchone():
            return None,'prior-round-unfinished'
    return dict(zip(WEB_FIELDS,(*key,fixture[0]))),'ready-for-isolated-kickoff'

def dispatch_held_trial(web_db,root,work,build,env,reviewed,*,experimental=False,now=None):
    if experimental is not True:
        raise ValueError('Explicit experimental isolated kickoff required')
    now=time.time() if now is None else now
    fixture,reason=held_fixture(web_db,reviewed,now)
    base=dict(probeOnly=True,automaticProductionKickoff=False,scoreWritten=False,
              automaticFallback=False,matchCompleted=False)
    if fixture is None:
        return dict(base,claimed=False,reason=reason)
    # The web hold is immutable. The native probe rechecks the retained save,
    # acquires its store lock, and durably claims before sending native input.
    # On error the claim remains; never call the legacy worker as fallback.
    report=probe_due(root,work,build,env,reviewed['saveName'],fixture,reviewed,now)
    return dict(base,**report,webHoldMatched=True,reviewSha256=review_digest(reviewed))
