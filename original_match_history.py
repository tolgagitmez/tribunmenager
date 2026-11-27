"""Read completed native 3D match history only, without mapping it to league fixtures."""
from contextlib import closing
import math
from pathlib import Path
import sqlite3

MAX_HISTORY=30


def read_rows(path,limit):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>64*1024*1024:
        raise ValueError('Native 3D match history missing or invalid')
    if any(Path(str(path)+s).exists() for s in ('-wal','-shm','-journal')):
        raise ValueError('History must be closed cleanly')
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        rows=db.execute("""SELECT team1_name,team2_name,score1,score2,match_time_ms,
            shots1,shots2,shots_on_target1,shots_on_target2,
            possession1_pct,possession2_pct,passes1,passes2,
            passes_completed1,passes_completed2,fouls1,fouls2
            FROM match_history ORDER BY id DESC LIMIT ?""",(limit,)).fetchall()
    return rows


def validate(row):
    home,away,hg,ag,clock,s1,s2,t1,t2,pos1,pos2,p1,p2,c1,c2,f1,f2=row
    if (not all(isinstance(x,str) and 0<len(x)<=256 for x in (home,away)) or
        any(type(x) is not int or x<0 for x in (hg,ag,clock,s1,s2,t1,t2,p1,p2,c1,c2,f1,f2)) or
        max(hg,ag)>99 or clock<=0 or t1>s1 or t2>s2 or c1>p1 or c2>p2 or
        not all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=100 for x in (pos1,pos2)) or
        abs(pos1+pos2-100)>0.1):
        raise ValueError('Invalid 3D match history')
    return dict(homeTeam=home,awayTeam=away,homeGoals=hg,awayGoals=ag,
                nativeMatchClockMs=clock,shots=[s1,s2],shotsOnTarget=[t1,t2],
                possessionPct=[pos1,pos2],passAttempts=[p1,p2],passesCompleted=[c1,c2],
                passAccuracyPct=[round(100*c/p,2) if p else None for c,p in ((c1,p1),(c2,p2))],
                fouls=[f1,f2])



def summarize_teams(records):
    """Descriptive aggregates over displayed history, not league standings.
    History has team names, not stable club IDs or competition identifiers.
    Exclude identical-name pairings because the sides cannot be distinguished.
    """
    totals={}
    excluded=0
    for record in records:
        names=(record['homeTeam'],record['awayTeam'])
        if names[0]==names[1]:
            excluded+=1
            continue
        goals=(record['homeGoals'],record['awayGoals'])
        for side,name in enumerate(names):
            other=1-side
            row=totals.setdefault(name,dict(teamName=name,played=0,won=0,drawn=0,lost=0,
                goals=0,goalsAgainst=0,shots=0,shotsOnTarget=0,passAttempts=0,
                passesCompleted=0,possessionSum=0,fouls=0))
            row['played']+=1
            row['won']+=int(goals[side]>goals[other])
            row['drawn']+=int(goals[side]==goals[other])
            row['lost']+=int(goals[side]<goals[other])
            row['goals']+=goals[side]
            row['goalsAgainst']+=goals[other]
            for key in ('shots','shotsOnTarget','passAttempts','passesCompleted','fouls'):
                row[key]+=record[key][side]
            row['possessionSum']+=record['possessionPct'][side]
    def pct(n,d):
        return round(100*n/d,2) if d else None
    for row in totals.values():
        n=row['played']
        row['goalsPerMatch']=round(row['goals']/n,2)
        row['shotsPerMatch']=round(row['shots']/n,2)
        row['shotsOnTargetPerMatch']=round(row['shotsOnTarget']/n,2)
        row['shotAccuracyPct']=pct(row['shotsOnTarget'],row['shots'])
        row['passAccuracyPct']=pct(row['passesCompleted'],row['passAttempts'])
        row['meanPossessionPct']=round(row.pop('possessionSum')/n,2)
    return dict(scope='valid-recent-history',groupedBy='exact-team-name',
                mixedCompetitions=True,sampleMatches=len(records)-excluded,
                excludedSameNameMatches=excluded,teams=sorted(totals.values(),key=lambda x:x['teamName']))


def read_recent(path):
    rows=read_rows(Path(path),MAX_HISTORY+1)
    records=[]
    skipped=0
    for row in rows[:MAX_HISTORY]:
        try:
            records.append(validate(row))
        except ValueError:
            skipped+=1
    return dict(source='native-3d-match-history',scope='last-closed-session',
                linkedToLeagueFixtures=False,readOnly=True,records=records,
                skipped=skipped,truncated=len(rows)>MAX_HISTORY,
                teamPerformance=summarize_teams(records))


def read_single(path):
    rows=read_rows(Path(path),2)
    if len(rows)!=1:
        raise ValueError('Expected exactly one finished 3D match in fresh runtime')
    return validate(rows[0])


# This file is a separate native persistence unit; never copy data/saves wholesale.
HISTORY_PATH=Path('data/saves/match_history.sqlite')
STORED_NAME='native-match-history.sqlite'


def checked_history(path):
    # Validate the schema and SQLite integrity before publishing or restoring bytes.
    read_rows(path,1)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
            raise ValueError('Native history integrity check failed')


def copy_history(source,destination):
    import os
    import shutil
    import tempfile
    from original_saves import sync_dir
    source,destination=Path(source),Path(destination)
    if source.is_symlink() or source.parent.is_symlink() or destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError('Native history links are not supported')
    checked_history(source)
    with tempfile.NamedTemporaryFile(dir=destination.parent,prefix='.history-',delete=False) as f:
        staged=Path(f.name)
    try:
        shutil.copyfile(source,staged)
        checked_history(staged)
        with staged.open('rb') as f:
            os.fsync(f.fileno())
        os.replace(staged,destination)
        sync_dir(destination.parent)
    finally:
        staged.unlink(missing_ok=True)


def restore_history(root,session):
    source=Path(root)/STORED_NAME
    if not source.exists() and not source.is_symlink():
        return False
    target=Path(session)/HISTORY_PATH
    if target.parent.is_symlink() or target.parent.parent.is_symlink():
        raise ValueError('Invalid native history directory')
    target.parent.mkdir(parents=True,exist_ok=True)
    copy_history(source,target)
    return True


def commit_history(root,session,exit_code):
    source=Path(session)/HISTORY_PATH
    if exit_code!=0 or (not source.exists() and not source.is_symlink()):
        return False
    if source.parent.parent.is_symlink():
        raise ValueError('Invalid native history directory')
    copy_history(source,Path(root)/STORED_NAME)
    return True
