"""Read-only guards for a normal native game's final whistle and Continue action.

GameOverPage writes history before Continue; LeagueConsumePlayedFixture is
called by Continue, not the upstream smoke auto-quit. Never synthesize a score.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
from original_catalog import connect
from original_engine import digest
from original_match_history import read_rows,validate,HISTORY_PATH
from original_full_league_validation import completed_own

def expected_names(path,fixture):
    with closing(connect(path)) as db:
        names=[]
        for team in (fixture['homeTeamId'],fixture['awayTeamId']):
            rows=db.execute('SELECT name FROM teams WHERE id=?',(team,)).fetchall()
            if len(rows)!=1 or not isinstance(rows[0][0],str) or not rows[0][0]:
                raise ValueError('Missing native fixture team name')
            names.append(rows[0][0])
        if names[0]==names[1]:
            raise ValueError('Ambiguous equal native team names')
        return tuple(names)

def fresh_history(session,names):
    """Return None while history has not appeared or is still being written.

    A fresh private runtime must contain no history before match launch.
    A successful read requires one full match, correct side order and stable bytes.
    """
    path=Path(session)/HISTORY_PATH
    if path.is_symlink():
        raise ValueError('Unexpected history symlink')
    if not path.exists() or any(Path(str(path)+s).exists() for s in ('-wal','-shm','-journal')):
        return None
    before=digest(path)
    try:
        rows=read_rows(path,2)
    except sqlite3.OperationalError:
        # EnsureTable may be running; retry only until the outer bounded deadline.
        return None
    if not rows or digest(path)!=before:
        return None
    if len(rows)!=1:
        raise ValueError('Expected exactly one fresh native history row')
    result=validate(rows[0])
    if (result['homeTeam'],result['awayTeam'])!=tuple(names):
        raise ValueError('Native history teams differ from reserved fixture')
    if result['nativeMatchClockMs']<5400000:
        raise ValueError('Native history did not reach regulation full time')
    return dict(history=result,historySha256=before)

def reserved_score_saved(path,fixture,before,history):
    """Read live autosave conservatively; require final closed recheck later."""
    path=Path(path)
    if any(Path(str(path)+s).exists() for s in ('-wal','-shm','-journal')):
        return None
    old=digest(path)
    after=completed_own(path)
    if digest(path)!=old:
        return None
    if any(after.get(i)!=row for i,row in before.items()):
        raise ValueError('Previously completed fixture changed')
    new=set(after)-set(before)
    if not new:
        return None
    if new!={fixture['nativeFixtureId']}:
        raise ValueError('Unexpected completed managed fixture')
    row=after[fixture['nativeFixtureId']]
    if row[1:4]!=(fixture['homeTeamId'],fixture['awayTeamId'],fixture['nativeDate']):
        raise ValueError('Reserved fixture identity changed')
    if row[4:]!=(history['homeTeam'],history['awayTeam'],history['homeGoals'],history['awayGoals']):
        raise ValueError('Native autosave score differs from final 3D history')
    return dict(nativeFixtureId=row[0],homeGoals=row[6],awayGoals=row[7],saveSha256=old)
