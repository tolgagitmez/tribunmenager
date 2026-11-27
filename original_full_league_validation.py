"""Opt-in interactive full native league match validation, with pristine settings.

Creates an isolated fresh runtime. Never touches the user's persistent save store.
A single 3D match history record must correspond to one completed own fixture.
No automated input, acceleration, or native code/config patches.
"""
from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile

import original_engine as engine
import original_results as results
from original_native_saves_probe import populate, save_manifest


def read_history(path):
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
            FROM match_history ORDER BY id LIMIT 2""").fetchall()
    if len(rows)!=1:
        raise ValueError('Expected exactly one finished 3D match in fresh runtime')
    home,away,hg,ag,clock,s1,s2,t1,t2,pos1,pos2,p1,p2,c1,c2,f1,f2=rows[0]
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


def verify(session):
    session=Path(session)
    history_path=session/'data/saves/match_history.sqlite'
    before=engine.digest(history_path)
    saves_before=save_manifest(session/'saves')
    history=read_history(history_path)
    report=results.collect(session,engine.REVISION,0)
    if len(report['saves'])!=1 or report['skippedSaves']:
        raise ValueError('Expected one readable isolated league save')
    save=report['saves'][0]
    if save['truncated'] or len(save['results'])!=1:
        raise ValueError('Expected exactly one completed managed-club fixture')
    match=save['results'][0]
    keys=('homeTeam','awayTeam','homeGoals','awayGoals')
    if any(match[k]!=history[k] for k in keys):
        raise ValueError('3D history score does not match saved league fixture')
    if not save.get('standings'):
        raise ValueError('Saved standings unavailable')
    if before!=engine.digest(history_path) or saves_before!=save_manifest(session/'saves'):
        raise RuntimeError('Read-only verification changed native data')
    return dict(native3DHistoryMatchesLeagueResult=True,fixture=match,history=history,
                scope='Single isolated match, matching team names and score; no shared match ID in history',
                automaticLeagueImport=False,hardwareFpsVerified=False)


def main():
    env=engine.clean_env(os.environ)
    work=engine.cache_root()/engine.REVISION
    build=engine.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='tribun-full-league-validation-') as tmp:
        session=Path(tmp)/'session'
        populate(build,session)
        engine.check_config(work/'source',session)
        if (session/'saves').exists() or (session/'data/saves/match_history.sqlite').exists():
            raise RuntimeError('Fresh test runtime unexpectedly contains previous match data')
        print('Geçici test: League Mode > yeni lig > Play next match > Kick off.',flush=True)
        print('Varsayılan süre/zorluğu değiştirme. Bir 3D maçı bitir, Continue seç, normal menüden oyunu kapat.',flush=True)
        print('Hızlı simülasyon veya ikinci maç yapma. Bu test kişisel lig kayıtlarını kullanmaz.',flush=True)
        code=subprocess.run([str(session/'gameplayfootball')],cwd=session,env=env).returncode
        if code!=0:
            raise RuntimeError('Native game did not exit normally')
        report=verify(session)
        report['defaultConfigAtLaunch']=True
        report['commandArgumentCount']=0
        report['sessionConfigByteUnchanged']=((session/'football.config').read_bytes()==(work/'source/data/football.config').read_bytes())
        report['normalExitVerified']=True
        engine.verify_install(work,env)
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
