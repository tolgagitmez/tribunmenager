"""Opt-in proof of the upstream custom league database selection interface.

Only creates a disposable alternative source database; no engine code,
default database, normal save store or configuration changes.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile

import original_engine as engine
from original_native_saves_probe import populate

PACK='tribun-interface-test'
MARKER='Tribun Interface Test'


def prepare_pack(runtime):
    runtime=Path(runtime)
    original=runtime/'databases/default'
    target=runtime/'databases'/PACK
    before=engine.digest(original/'database.sqlite')
    shutil.copytree(original,target)
    dbpath=target/'database.sqlite'
    with closing(sqlite3.connect(dbpath)) as db:
        with db:
            row=db.execute("""SELECT p.id,p.team_id,t.name,p.firstname,p.lastname
                FROM players p JOIN teams t ON t.id=p.team_id
                WHERE p.team_id>0 ORDER BY p.id LIMIT 1""").fetchone()
            if row is None:
                raise ValueError('No native club player for interface probe')
            player,team,name,first,last=row
            # A visible, isolated player-data marker, not a skill/AI/tactic change.
            db.execute('UPDATE players SET lastname=? WHERE id=?',(MARKER,player))
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
                raise ValueError('Alternative database integrity failed')
    if engine.digest(original/'database.sqlite')!=before:
        raise RuntimeError('Default native database changed')
    return dict(playerId=player,teamId=team,teamName=name,firstName=first,originalLastName=last)


def verify(runtime,expected):
    runtime=Path(runtime)
    candidates=list((runtime/'saves').glob('*/autosave.sqlite'))
    if len(candidates)!=1:
        raise ValueError('Create exactly one league from the alternative database')
    path=candidates[0]
    if path.is_symlink() or any(Path(str(path)+s).exists() for s in ('-wal','-shm','-journal')):
        raise ValueError('Close the native league database normally')
    before=engine.digest(path)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
            raise ValueError('Native league integrity failed')
        row=db.execute('SELECT team_id,firstname,lastname FROM players WHERE id=?',(expected['playerId'],)).fetchone()
        if row!=(expected['teamId'],expected['firstName'],MARKER):
            raise ValueError('Selected league did not retain alternative player data')
        if db.execute('SELECT COUNT(*) FROM settings').fetchone()[0]!=1:
            raise ValueError('Native league was not initialized')
        if db.execute('SELECT COUNT(*) FROM calendar').fetchone()[0]<1:
            raise ValueError('Native fixture generation missing')
    if engine.digest(path)!=before:
        raise RuntimeError('Read-only verification changed native league')
    return dict(customDatabasePlayerRoundtripVerified=True,sourceDatabase=PACK,
                markerPlayerId=expected['playerId'],markerTeam=expected['teamName'],
                nativeConfigModifiedByBridge=False,automaticRosterImport=False)


def run_private_menu(runtime,pack=PACK):
    """CI-only real keyboard path. Never used by production launch."""
    import time
    from original_native_reload_probe import wait_for,press_key,diagnostic_frame,opened_database
    env=engine.clean_env(os.environ)
    runtime=Path(runtime).resolve()
    if not env.get('DISPLAY','').startswith(':'):
        raise RuntimeError('Private Xvfb display required')
    with tempfile.TemporaryFile() as log:
        game=subprocess.Popen([str(runtime/'gameplayfootball')],cwd=runtime,env=env,
                              stdout=log,stderr=subprocess.STDOUT)
        try:
            def window():
                p=subprocess.run(['xdotool','search','--onlyvisible','--pid',str(game.pid),
                    '--name','^League Soccer$'],env=env,capture_output=True,text=True,timeout=5)
                return p.stdout.strip().splitlines()[0] if p.returncode==0 and p.stdout.strip() else None
            wid=wait_for(window,60,game)
            time.sleep(5)
            engine.call(['xdotool','windowfocus','--sync',wid],env)
            step=0
            def keys(sequence):
                nonlocal step
                for key in sequence:
                    if game.poll() is not None:
                        break
                    press_key(key,env)
                    step+=1
                    print(f'Custom database menu step {step}: {key}',flush=True)
                    diagnostic_frame(f'custom-{step:02d}-{key}',env)
            # Intro -> League -> New -> source browser. Pinned upstream
            # file browser sorts directory names; default precedes the test pack.
            dirs=sorted(p.name for p in (runtime/'databases').iterdir() if p.is_dir())
            if dirs!=['default',pack]:
                raise RuntimeError('Unexpected custom database menu entries')
            keys(('Return','Down','Return','Down','Return','Return','Down','Return'))
            # Source selector -> team -> currency -> difficulty -> save name
            # -> manager name -> Proceed. Do not change any control values.
            keys(('Down',)*6+('Return',))
            def autosave_open():
                files=list((runtime/'saves').glob('*/autosave.sqlite'))
                return files[0] if len(files)==1 and opened_database(game.pid,files[0].resolve()) else None
            wait_for(autosave_open,20,game)
            keys(('Return',))
            # League hub: Play next match is focused, Return to main menu
            # is at row 1, column 1. Main menu defaults to Quick Match.
            keys(('Right','Down','Return')+('Down',)*5+('Return','Return'))
            if game.wait(timeout=30)!=0:
                raise RuntimeError('Native custom source session did not exit normally')
        except Exception:
            diagnostic_frame('custom-99-failure',env)
            log.seek(0)
            print(log.read()[-8000:].decode(errors='replace'),flush=True)
            raise
        finally:
            if game.poll() is None:
                game.terminate()
                try:
                    game.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    game.kill()
                    game.wait()


def main(ci=False):
    env=engine.clean_env(os.environ)
    work=engine.cache_root()/engine.REVISION
    build=engine.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='tribun-custom-source-probe-') as tmp:
        runtime=Path(tmp)/'runtime'
        populate(build,runtime)
        engine.check_config(work/'source',runtime)
        original_digest=engine.digest(runtime/'databases/default/database.sqlite')
        expected=prepare_pack(runtime)
        print('Geçici veri aktarım testi: League Mode > New League.',flush=True)
        print('Kaynak veritabanı olarak '+PACK+' seç, bir lig oluştur ve normal şekilde kapat.',flush=True)
        print('Deneme oyuncusu: '+expected['teamName']+' / '+MARKER,flush=True)
        if ci:
            import sys
            engine.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',sys.executable,
                Path(__file__).resolve(),'--inside-private-menu',runtime],env)
            code=0
        else:
            code=subprocess.run([str(runtime/'gameplayfootball')],cwd=runtime,env=env).returncode
        if code!=0:
            raise RuntimeError('Native game did not exit normally')
        if engine.digest(runtime/'databases/default/database.sqlite')!=original_digest:
            raise RuntimeError('Default database changed during source selection probe')
        engine.verify_install(work,env)
        print(json.dumps(verify(runtime,expected),ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    import sys
    if len(sys.argv) in (3,4) and sys.argv[1]=='--inside-private-menu':
        run_private_menu(sys.argv[2],sys.argv[3] if len(sys.argv)==4 else PACK)
    elif sys.argv[1:]==['--ci']:
        main(ci=True)
    elif len(sys.argv)==1:
        main()
    else:
        raise SystemExit('Usage: original_custom_database_probe.py [--ci]')
