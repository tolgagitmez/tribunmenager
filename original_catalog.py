"""Inspect original default database, never write tactical or squad settings."""
from pathlib import Path
import math
import sqlite3
import xml.etree.ElementTree as ET

KNOWN_TACTICS={
    'position_offense_depth_factor':'Hücum derinliği',
    'position_defense_depth_factor':'Savunma derinliği',
    'position_offense_width_factor':'Hücum genişliği',
    'position_defense_width_factor':'Savunma genişliği',
    'position_offense_midfieldfocus':'Orta sahanın hücuma katılımı',
    'position_defense_midfieldfocus':'Savunmada orta saha konumu',
    'position_offense_sidefocus_strength':'Hücumda ileri yönelim',
    'position_defense_sidefocus_strength':'Savunmada geri yönelim',
    'position_offense_microfocus_strength':'Hücumda top çevresinde yoğunluk',
    'position_defense_microfocus_strength':'Savunmada top çevresinde yoğunluk',
    'dribble_offensiveness':'Top taşıyan oyuncunun ileri yönelimi',
    'dribble_centermagnet':'Driplingde merkez tercihi',
    'counter_attack':'Kontra atak',
    'support_distance':'Destek mesafesi',
    'team_pressure':'Alan baskısı',
}
MAX_TEAMS=1000
MAX_PLAYERS=128


def connect(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>128*1024*1024:
        raise ValueError('Orijinal veri tabanı bulunamadı veya geçersiz.')
    if any(Path(str(path)+ext).exists() for ext in ('-wal','-shm','-journal')):
        raise ValueError('Veri tabanı temiz kapanmamış.')
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    db.execute('PRAGMA trusted_schema=OFF')
    db.execute('PRAGMA query_only=ON')
    return db


def xml_fragment(value):
    if not isinstance(value,str) or len(value)>65536 or '<!' in value:
        raise ValueError('Desteklenmeyen orijinal XML.')
    return ET.fromstring('<root>'+value+'</root>')


def tactics(raw):
    result=[]
    for node in xml_fragment(raw):
        if node.tag not in KNOWN_TACTICS:
            continue
        if any(t['key']==node.tag for t in result) or len(node):
            raise ValueError('Belirsiz taktik verisi.')
        value=float(node.text or '')
        if not math.isfinite(value):
            raise ValueError('Geçersiz taktik değeri.')
        result.append(dict(key=node.tag,label=KNOWN_TACTICS[node.tag],value=value,source='database'))
    # Exactly the three neutral defaults documented in upstream TeamData.
    for key in ('counter_attack','support_distance','team_pressure'):
        if not any(t['key']==key for t in result):
            result.append(dict(key=key,label=KNOWN_TACTICS[key],value=.5,source='upstream-memory-default'))
    return result


def formation(raw):
    slots=[]
    for node in xml_fragment(raw):
        if node.tag not in {f'p{i}' for i in range(1,12)}:
            continue
        slot=int(node.tag[1:])
        if any(s['slot']==slot for s in slots):
            raise ValueError('Çift diziliş yuvası.')
        role=node.findtext('role')
        position=node.findtext('position')
        xy=[float(x) for x in position.split(',')] if position else None
        if xy is not None and (len(xy) not in (2,3) or not all(math.isfinite(x) for x in xy)):
            raise ValueError('Geçersiz diziliş koordinatı.')
        slots.append(dict(slot=slot,role=role,rawPosition=xy))
    return sorted(slots,key=lambda s:s['slot'])


def catalog(path, team_id=None):
    db=connect(path)
    try:
        if team_id is None:
            rows=db.execute('SELECT id,name FROM teams ORDER BY name,id LIMIT ?',(MAX_TEAMS+1,)).fetchall()
            return dict(teams=[dict(id=i,name=n) for i,n in rows[:MAX_TEAMS]],truncated=len(rows)>MAX_TEAMS)
        if type(team_id) is not int or team_id<=0:
            raise ValueError('Geçersiz takım kimliği.')
        row=db.execute('SELECT id,name,formation_xml,tactics_xml FROM teams WHERE id=?',(team_id,)).fetchone()
        if row is None:
            raise ValueError('Orijinal takım bulunamadı.')
        players=db.execute("""SELECT id,firstname,lastname,role,formationorder
            FROM players WHERE team_id=? ORDER BY formationorder,id LIMIT ?""",
            (team_id,MAX_PLAYERS+1)).fetchall()
        return dict(id=row[0],name=row[1],formation=formation(row[2] or ''),
            tactics=tactics(row[3] or ''),players=[dict(id=i,name=' '.join(filter(None,(first,last))),
                role=role,formationOrder=order) for i,first,last,role,order in players[:MAX_PLAYERS]],
            truncated=len(players)>MAX_PLAYERS,source='original-default-database',
            readOnly=True,representsLiveLineup=False)
    finally:
        db.close()
