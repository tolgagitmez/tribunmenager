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
