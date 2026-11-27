"""Private, reviewed result ledger and provisional season table.

Never writes the native save or the production web league. Only a closed
isolated session with fresh 3D history and exactly the reserved new fixture
can supply a candidate. League identifiers must include the season.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3

from original_catalog import connect
from original_engine import digest
from original_fixture_dispatch import NATIVE_FIELDS
from original_full_league_validation import completed_own,verify_restored_fixture
from original_saves import locked_store
from original_match_history import HISTORY_PATH

def stage_result(root,key,session,*,operator_reviewed=False):
    if operator_reviewed is not True or not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):
        raise ValueError('Explicit reviewed fixture reservation required')
    session=Path(session)
    with locked_store(root) as root:
        with closing(connect(root/'fixture-dispatch.sqlite3')) as db:
            claim=db.execute('SELECT mapping,snapshot,save_name,save_sha256 FROM claims WHERE key=?',(key,)).fetchone()
        if claim is None:
            raise ValueError('Unknown fixture reservation')
        raw,snapshot,save_name,source_hash=claim
        mapping=json.loads(raw)
        if not re.fullmatch(r'snapshot-[0-9a-f]{32}',snapshot) or not save_name or save_name in ('.','..') or '/' in save_name or chr(92) in save_name:
            raise ValueError('Invalid reserved save identity')
        original=root/snapshot/save_name/'autosave.sqlite'
        saved=session/'saves'/save_name/'autosave.sqlite'
        history=session/HISTORY_PATH
        for path in (original,saved,history):
            if path.is_symlink() or not path.is_file() or path.parent.is_symlink() or any(Path(str(path)+s).exists() for s in ('-wal','-shm','-journal')):
                raise ValueError('Closed regular database required')
        if digest(original)!=source_hash:
            raise ValueError('Reserved source save changed')
        hashes=(digest(saved),digest(history))
        expected={k:mapping[k] for k in NATIVE_FIELDS}
        report=verify_restored_fixture(session,expected,completed_own(original))
        if hashes!=(digest(saved),digest(history)) or digest(original)!=source_hash:
            raise RuntimeError('Evidence changed during verification')
        h=report['history']
        payload=json.dumps(dict(fixtureKey=key,league=mapping['league'],round=mapping['round'],
            home=mapping['home'],away=mapping['away'],nativeFixture=expected,
            homeGoals=h['homeGoals'],awayGoals=h['awayGoals'],history=h,
            sourceSha256=source_hash,saveSha256=hashes[0],historySha256=hashes[1]),
            sort_keys=True,separators=(',',':'))
        path=root/'verified-result-candidates.sqlite3'
        fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        os.close(fd)
        with closing(sqlite3.connect(path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS candidates(key TEXT PRIMARY KEY, history_sha TEXT UNIQUE NOT NULL, payload TEXT NOT NULL)')
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT payload FROM candidates WHERE key=?',(key,)).fetchone()
            if existing:
                if existing[0]!=payload:
                    raise ValueError('Conflicting result for same fixture')
                created=False
            else:
                if db.execute('SELECT 1 FROM candidates WHERE history_sha=?',(hashes[1],)).fetchone():
                    raise ValueError('History already used by another fixture')
                db.execute('INSERT INTO candidates VALUES(?,?,?)',(key,hashes[1],payload))
                created=True
        return dict(created=created,result=json.loads(payload),productionScoreWritten=False,
                    automaticProductionImport=False,operatorReviewed=True)

def provisional_table(root,league):
    """Recompute from immutable staged rows, never add points twice."""
    if not isinstance(league,str) or not league:
        raise ValueError('Season-specific league key required')
    path=Path(root)/'verified-result-candidates.sqlite3'
    if not path.exists():
        return dict(league=league,fixtures=0,rows=[],provisional=True)
    with closing(connect(path)) as db:
        matches=[json.loads(r[0]) for r in db.execute('SELECT payload FROM candidates ORDER BY key')]
    rows={}
    count=0
    for m in matches:
        if m['league']!=league:
            continue
        count+=1
        for team,gf,ga in ((m['home'],m['homeGoals'],m['awayGoals']),(m['away'],m['awayGoals'],m['homeGoals'])):
            r=rows.setdefault(team,dict(teamId=team,played=0,won=0,drawn=0,lost=0,goalsFor=0,goalsAgainst=0,points=0))
            r['played']+=1
            r['won']+=int(gf>ga);r['drawn']+=int(gf==ga);r['lost']+=int(gf<ga)
            r['goalsFor']+=gf;r['goalsAgainst']+=ga
            r['points']+=3 if gf>ga else 1 if gf==ga else 0
    for r in rows.values():
        r['goalDifference']=r['goalsFor']-r['goalsAgainst']
    ordered=sorted(rows.values(),key=lambda r:(-r['points'],-r['goalDifference'],r['teamId']))
    return dict(league=league,fixtures=count,rows=ordered,provisional=True,
                includesOnlyStagedFixtures=True,productionStandingsWritten=False)
