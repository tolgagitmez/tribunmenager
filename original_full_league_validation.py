"""Opt-in interactive full native league match validation, with pristine settings.

Creates an isolated fresh runtime. Never touches the user's persistent save store.
A single 3D match history record must correspond to one completed own fixture.
No automated input, acceleration, or native code/config patches.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

import original_engine as engine
import original_results as results
from original_native_saves_probe import populate, save_manifest


from original_match_history import read_single as read_history


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


def completed_own(path):
    """Read the complete bounded managed-club result set, with stable IDs."""
    from contextlib import closing
    from original_catalog import connect
    with closing(connect(path)) as db:
        settings=db.execute('SELECT team_id FROM settings LIMIT 2').fetchall()
        if len(settings)!=1:
            raise ValueError('Expected one managed club')
        team=settings[0][0]
        rows=db.execute("""SELECT m.calendar_id,m.team1_id,m.team2_id,c.timestamp,
                h.name,a.name,m.team1_goals,m.team2_goals
            FROM match_results m JOIN calendar c ON c.id=m.calendar_id
                AND c.team1_id=m.team1_id AND c.team2_id=m.team2_id
            JOIN teams h ON h.id=m.team1_id JOIN teams a ON a.id=m.team2_id
            WHERE m.played=1 AND (m.team1_id=? OR m.team2_id=?)
            ORDER BY m.calendar_id LIMIT 10001""",(team,team)).fetchall()
        total=db.execute('SELECT COUNT(*) FROM match_results WHERE played=1 AND (team1_id=? OR team2_id=?)',(team,team)).fetchone()[0]
        if len(rows)!=total or len(rows)>10000 or len({r[0] for r in rows})!=len(rows):
            raise ValueError('Incomplete or ambiguous managed result history')
    return {r[0]:r for r in rows}


def verify_restored_fixture(session,expected,before):
    """Match exactly one new own result to a fresh 3D history and reserved IDs."""
    session=Path(session)
    saves=list((session/'saves').glob('*/autosave.sqlite'))
    if len(saves)!=1 or saves[0].parent.is_symlink():
        raise ValueError('Expected one isolated restored league')
    path=saves[0]
    history_path=session/'data/saves/match_history.sqlite'
    hashes=(engine.digest(path),engine.digest(history_path))
    from contextlib import closing
    from original_catalog import connect
    with closing(connect(path)) as db:
        if db.execute('SELECT team_id FROM settings LIMIT 2').fetchall()!=[(expected['managedTeamId'],)]:
            raise ValueError('Managed club changed')
    after=completed_own(path)
    if any(after.get(i)!=row for i,row in before.items()):
        raise ValueError('Previously completed fixture changed')
    new=set(after)-set(before)
    if new!={expected['nativeFixtureId']}:
        raise ValueError('Expected exactly the reserved native fixture to complete')
    row=after[expected['nativeFixtureId']]
    if row[1:4]!=(expected['homeTeamId'],expected['awayTeamId'],expected['nativeDate']):
        raise ValueError('Reserved fixture identity changed')
    history=read_history(history_path)
    if (history['homeTeam'],history['awayTeam'],history['homeGoals'],history['awayGoals'])!=row[4:]:
        raise ValueError('Fresh 3D history does not match reserved result')
    if history['nativeMatchClockMs']<5400000:
        raise ValueError('History does not show full regulation match time')
    if hashes!=(engine.digest(path),engine.digest(history_path)):
        raise RuntimeError('Read-only verification changed native data')
    return dict(reservedFixtureResultVerified=True,expectedFixture=expected,history=history,
                previousOwnResultsPreserved=len(before),newOwnResults=1,
                nativeHistorySharedFixtureId=False,automaticLeagueImport=False,
                automaticKickoffVerified=False)


def restored_main():
    """Interactive isolated continuation from the user's closed native save."""
    from original_saves import locked_store,restore
    from original_fixture_gate import next_native_fixture
    env=engine.clean_env(os.environ)
    work=engine.cache_root()/engine.REVISION
    build=engine.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='tribun-reserved-full-match-') as tmp:
        session=Path(tmp)/'session'
        populate(build,session)
        engine.check_config(work/'source',session)
        # Copy under lock, then release. No commits to the real save store.
        with locked_store(engine.save_root_path()) as root:
            restore(root,session)
        files=list((session/'saves').glob('*/autosave.sqlite'))
        if len(files)!=1 or (session/'data/saves/match_history.sqlite').exists():
            raise ValueError('One closed native league and fresh history required')
        expected=next_native_fixture(files[0])
        if expected is None:
            raise ValueError('No next native fixture')
        before=completed_own(files[0])
        print(json.dumps(expected,ensure_ascii=False),flush=True)
        print('Geçici kopyada League Mode > Load Saved > Play next match > Kick off > Start.',flush=True)
        print('Sadece sıradaki 3D maçı tamamla, Continue ile kaydet ve normal menüden çık. Süre/zorluk ayarlarına dokunma.',flush=True)
        if subprocess.run([str(session/'gameplayfootball')],cwd=session,env=env).returncode!=0:
            raise RuntimeError('Native game did not exit normally')
        report=verify_restored_fixture(session,expected,before)
        report['normalExitVerified']=True
        report['defaultConfigAtLaunch']=True
        report['persistentSaveChangedByBridge']=False
        engine.verify_install(work,env)
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


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
    import sys
    if sys.argv[1:]==['--restored']:
        restored_main()
    elif len(sys.argv)==1:
        main()
    else:
        raise SystemExit('Usage: original_full_league_validation.py [--restored]')
