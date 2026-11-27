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


def validate_lineup(db,team_id,rows,slot_order):
    """Only reorder against the native formation, never rewrite its XML.
    slot_order is an explicit list of 11 local indices in native p1..p11 order.
    """
    from original_catalog import formation
    if not isinstance(slot_order,list) or len(slot_order)!=11 or any(type(i) is not int for i in slot_order) or len(set(slot_order))!=11:
        raise ValueError('Exactly eleven unique native slot assignments required')
    by_index={r['localIndex']:r for r in rows}
    if any(i not in by_index for i in slot_order):
        raise ValueError('Lineup includes an unmapped player')
    selected=db.execute('SELECT formation_xml FROM teams WHERE id=?',(team_id,)).fetchone()
    if selected is None:
        raise ValueError('Native formation unavailable')
    slots=formation(selected[0])
    if [s['slot'] for s in slots]!=list(range(1,12)) or any(s['role'] not in NATIVE_ROLES for s in slots):
        raise ValueError('Complete native formation required')
    for slot,index in zip(slots,slot_order):
        if slot['role']!=by_index[index]['nativeRole']:
            raise ValueError('Explicit player role does not match native slot '+str(slot['slot']))
    # Reject national-team collisions because TeamData also selects
    # nationalteam_id, and uses formationorder for club mode.
    if db.execute('SELECT COUNT(*) FROM players WHERE nationalteam_id=? AND (team_id IS NULL OR team_id!=?)',(team_id,team_id)).fetchone()[0]:
        raise ValueError('Native team selection includes additional national players')
    starters=[by_index[i]['nativePlayerId'] for i in slot_order]
    bench=sorted(r['nativePlayerId'] for r in rows if r['localIndex'] not in slot_order)
    return starters+bench


def build_pack(runtime,team_id,rows,*,skill_pilot=False,slot_order=None):
    runtime=Path(runtime)
    original=runtime/'databases/default'
    target=runtime/'databases/tribun-roster-pilot'
    if original.is_symlink() or target.exists() or target.is_symlink():
        raise ValueError('Require a fresh alternative database directory')
    before=digest(original/'database.sqlite')
    with closing(connect(original/'database.sqlite')) as db:
        updates=validate_mapping(db,team_id,rows)
        lineup=validate_lineup(db,team_id,rows,slot_order) if slot_order is not None else None
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
                if lineup is not None:
                    # Two-phase updates avoid intermediate duplicate ordering.
                    old=db.execute('SELECT MIN(formationorder) FROM players WHERE team_id=?',(team_id,)).fetchone()[0]
                    if type(old) is not int or old<-(2**31)+256:
                        raise ValueError('Invalid native formation order')
                    db.executemany('UPDATE players SET formationorder=? WHERE id=? AND team_id=?',[(min(old,0)-i-1,ident,team_id) for i,ident in enumerate(lineup)])
                    db.executemany('UPDATE players SET formationorder=? WHERE id=? AND team_id=?',[(i,ident,team_id) for i,ident in enumerate(lineup)])
                    ordered=[r[0] for r in db.execute('SELECT id FROM players WHERE team_id=? ORDER BY formationorder,id',(team_id,))]
                    if ordered!=lineup:
                        raise RuntimeError('Native lineup did not roundtrip')
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
                skillEquivalenceVerified=False,experimentalLineupWritten=lineup is not None,
                nativeFormationImported=False,nativeTacticsImported=False,
                nativeMenuLoadVerified=False,defaultDatabaseUnchanged=True)
