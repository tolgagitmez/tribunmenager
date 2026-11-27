"""Read native league autosave results after exit, without writing engine data."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile

MAX_SAVES = 20
MAX_RESULTS = 100
MAX_DB_BYTES = 64 * 1024 * 1024

QUERY = """
SELECT m.calendar_id, m.team1_id, m.team2_id, h.name, a.name,
       m.team1_goals, m.team2_goals, c.timestamp
FROM match_results m
JOIN calendar c ON c.id=m.calendar_id
  AND c.team1_id=m.team1_id AND c.team2_id=m.team2_id
JOIN teams h ON h.id=m.team1_id
JOIN teams a ON a.id=m.team2_id
WHERE m.played=1 AND (
  m.team1_id=(SELECT team_id FROM settings ORDER BY id LIMIT 1)
  OR m.team2_id=(SELECT team_id FROM settings ORDER BY id LIMIT 1))
ORDER BY c.timestamp DESC, m.calendar_id DESC
LIMIT ?
"""


def read_save(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_DB_BYTES:
        raise ValueError('Unsupported native save')
    # This is called after the native process exits; reject sidecar journals
    # instead of asking SQLite to recover or write them.
    for suffix in ('-wal','-shm','-journal'):
        if Path(str(path)+suffix).exists():
            raise ValueError('Unsettled native save journal')
    conn=sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        conn.execute('PRAGMA trusted_schema=OFF')
        conn.execute('PRAGMA query_only=ON')
        rows=conn.execute(QUERY,(MAX_RESULTS+1,)).fetchall()
    finally:
        conn.close()
    results=[]
    ids=set()
    for fixture,home,away,hn,an,hg,ag,date in rows[:MAX_RESULTS]:
        if (any(type(x) is not int for x in (fixture,home,away,hg,ag)) or
                min(fixture,home,away)<=0 or home==away or min(hg,ag)<0 or
                max(hg,ag)>99 or fixture in ids or
                not all(isinstance(x,str) and 0<len(x)<=256 for x in (hn,an,date))):
            raise ValueError('Invalid or ambiguous native result')
        ids.add(fixture)
        results.append(dict(nativeFixtureId=fixture,homeTeamId=home,awayTeamId=away,
            homeTeam=hn,awayTeam=an,homeGoals=hg,awayGoals=ag,nativeDate=date))
    return dict(results=results,truncated=len(rows)>MAX_RESULTS)


def collect(session, revision, exit_code):
    report=dict(schema=1,revision=revision,exitCode=exit_code,
                source='native-league-autosave',automaticLeagueImport=False,
                provesRenderedMatch=False,saves=[],skippedSaves=0)
    saves=Path(session)/'saves'
    if exit_code!=0 or not saves.is_dir() or saves.is_symlink():
        return report
    candidates=sorted(saves.iterdir())
    report['saveLimitReached']=len(candidates)>MAX_SAVES
    for folder in candidates[:MAX_SAVES]:
        db=folder/'autosave.sqlite'
        if folder.is_symlink() or not folder.is_dir() or not db.is_file():
            continue
        try:
            result=read_save(db)
        except (OSError,sqlite3.Error,ValueError):
            report['skippedSaves']+=1
            continue
        report['saves'].append(dict(saveName=folder.name[:128],**result))
    return report


def store(report,path):
    path=Path(path)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                     prefix='.native-results-',delete=False) as f:
        temp=Path(f.name)
        try:
            json.dump(report,f,ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        except Exception:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)
