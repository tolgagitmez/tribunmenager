"""Stage-two pilot: build an alternate native roster data package.

Explicit slot mapping only. Native player IDs, age, appearance, skills,
formation order, teams and tactics remain intact by default. Optional skill
pilot writes only explicitly mapped profile values. No production launch hook.
"""
from contextlib import closing
import shutil
import sqlite3
from pathlib import Path
import tempfile

from original_engine import digest
from original_catalog import connect

NATIVE_ROLES={'GK','CB','LB','RB','DM','CM','LM','RM','AM','CF'}
ROLE_OPTIONS={'ST':{'CF'},'LW':{'LM'},'RW':{'RM'},'LWB':{'LB'},'RWB':{'RB'}}


def validate_mapping(db,team_id,rows):
    if type(team_id) is not int or team_id<=0 or not isinstance(rows,list) or not 11<=len(rows)<=128:
        raise ValueError('Explicit complete club mapping required')
    native=db.execute('SELECT id FROM players WHERE team_id=? ORDER BY id',(team_id,)).fetchall()
    native_ids={r[0] for r in native}
    ids=set()
    indices=set()
    updates=[]
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError('Invalid mapping row')
        ident,index=row.get('nativePlayerId'),row.get('localIndex')
        first,last=row.get('firstName'),row.get('lastName')
        source,role=row.get('webRole'),row.get('nativeRole')
        if (type(ident) is not int or ident not in native_ids or ident in ids or
            type(index) is not int or index<0 or index in indices or
            not isinstance(first,str) or not isinstance(last,str) or
            len(first)>64 or not 0<len(last)<=64 or first!=first.strip() or last!=last.strip() or
            any(ord(c)<32 for c in first+last) or
            not isinstance(source,str) or not isinstance(role,str) or role not in NATIVE_ROLES or
            role not in ({source} if source in NATIVE_ROLES else ROLE_OPTIONS.get(source,set()))):
            raise ValueError('Invalid, duplicate or unmapped native player')
        ids.add(ident)
        indices.add(index)
        updates.append((first,last,role,ident,team_id))
    if ids!=native_ids:
        raise ValueError('Every existing native club slot must be explicitly mapped')
    return updates


def build_pack(runtime,team_id,rows,*,skill_pilot=False):
    runtime=Path(runtime)
    original=runtime/'databases/default'
    target=runtime/'databases/tribun-roster-pilot'
    if original.is_symlink() or target.exists() or target.is_symlink():
        raise ValueError('Require a fresh alternative database directory')
    before=digest(original/'database.sqlite')
    with closing(connect(original/'database.sqlite')) as db:
        updates=validate_mapping(db,team_id,rows)
        profiles=[]
        if skill_pilot:
            from original_skill_mapping import plan_profile
            for row in rows:
                ident=row['nativePlayerId']
                base,age,xml=db.execute('SELECT base_stat,age,profile_xml FROM players WHERE id=? AND team_id=?',(ident,team_id)).fetchone()
                plan=plan_profile(base,age,xml,row.get('webValues'))
                if plan['unresolved'] or not plan['proposed']:
                    raise ValueError('Unresolved skill mapping for native player '+str(ident))
                profiles.append((plan['profileXml'],ident,team_id))
    # The original database and graphics are untouched; only the new pack
    # is published after SQL and integrity validation succeed.
    with tempfile.TemporaryDirectory(prefix='.roster-pack-',dir=target.parent) as tmp:
        pack=Path(tmp)/'pack'
        shutil.copytree(original,pack)
        with closing(sqlite3.connect(pack/'database.sqlite')) as db:
            with db:
                db.executemany('UPDATE players SET firstname=?,lastname=?,role=? WHERE id=? AND team_id=?',updates)
                if profiles:
                    db.executemany('UPDATE players SET profile_xml=? WHERE id=? AND team_id=?',profiles)
                    for xml,ident,team in profiles:
                        if db.execute('SELECT profile_xml FROM players WHERE id=? AND team_id=?',(ident,team)).fetchone()!=(xml,):
                            raise RuntimeError('Skill profile did not roundtrip')
                if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
                    raise ValueError('Alternative database integrity failed')
                for first,last,role,ident,team in updates:
                    if db.execute('SELECT firstname,lastname,role FROM players WHERE id=? AND team_id=?',(ident,team)).fetchone()!=(first,last,role):
                        raise RuntimeError('Player mapping did not roundtrip')
        if digest(original/'database.sqlite')!=before:
            raise RuntimeError('Default database was changed')
        pack.rename(target)
    return dict(sourceDatabase=target.name,teamId=team_id,mappedPlayers=len(updates),
                nativeSkillsImported=False,experimentalSkillProfilesWritten=len(profiles),
                skillEquivalenceVerified=False,nativeFormationImported=False,nativeTacticsImported=False,
                nativeMenuLoadVerified=False,defaultDatabaseUnchanged=True)
