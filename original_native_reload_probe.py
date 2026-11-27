"""CI-only native UI reload test, on a disposable Xvfb and runtime copy."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import original_engine as e


def wait_for(predicate, seconds, game):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline and game.poll() is None:
        value=predicate()
        if value:
            return value
        time.sleep(.2)
    raise RuntimeError('Expected native UI state not observed')


def opened_database(pid, expected):
    # The upstream Database::Load uses sqlite3_open_v2 on the actual file.
    # A persistent process FD proves the game opened this restored database.
    for fd in Path(f'/proc/{pid}/fd').iterdir():
        try:
            if fd.readlink()==expected:
                return True
        except (FileNotFoundError,PermissionError):
            continue
    return False


def run(session):
    env=e.clean_env(os.environ)
    if not env.get('DISPLAY','').startswith(':'):
        raise RuntimeError('Private CI display required')
    session=Path(session).resolve()
    autosaves=list((session/'saves').glob('*/autosave.sqlite'))
    if len(autosaves)!=1 or autosaves[0].is_symlink():
        raise RuntimeError('Expected exactly one restored native league')
    expected=autosaves[0].resolve()
    with tempfile.TemporaryFile() as log:
        game=subprocess.Popen([str(session/'gameplayfootball')],cwd=session,
                              env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            def window():
                p=subprocess.run(['xdotool','search','--onlyvisible','--pid',str(game.pid),
                                  '--name','^League Soccer$'],env=env,capture_output=True,
                                 text=True,timeout=5)
                return p.stdout.strip().splitlines()[0] if p.returncode==0 and p.stdout.strip() else None

            wid=wait_for(window,60,game)
            time.sleep(5)
            e.call(['xdotool','windowfocus','--sync',wid],env)
            if opened_database(game.pid,expected):
                raise RuntimeError('Restored DB opened before UI selection')
            # Intro -> main menu; Quick Match initially focused. One Down
            # selects League Mode; Load Saved is focused on the next page.
            # The sole save entry is focused; the confirmation defaults to Load.
            for keys in (['Return'],['Down'],['Return'],['Return'],['Return'],['Return']):
                e.call(['xdotool','key','--clearmodifiers',*keys],env)
                time.sleep(2)
                if opened_database(game.pid,expected):
                    break
            wait_for(lambda: opened_database(game.pid,expected),15,game)
            time.sleep(2)
            if game.poll() is not None or not opened_database(game.pid,expected):
                raise RuntimeError('Native restored database did not remain open')
            print(json.dumps(dict(nativeMenuReopenVerified=True,restoredAutosaveOpened=True,
                  defaultConfigLaunch=True,commandArgumentCount=0,
                  gameProcessAlive=True,normalExitVerified=False,
                  scope='Native UI keyboard navigation and process file descriptor; not a full resumed match.')),
                  flush=True)
        except Exception:
            log.seek(0)
            print(log.read()[-6000:].decode(errors='replace'),file=sys.stderr)
            raise
        finally:
            if game.poll() is None:
                game.terminate()
                try:
                    game.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    game.kill()
                    game.wait()


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--inside-private-display':
        run(sys.argv[2])
    elif len(sys.argv)==2:
        e.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                sys.executable,Path(__file__).resolve(),'--inside-private-display',
                Path(sys.argv[1]).resolve()],e.clean_env(os.environ))
    else:
        raise SystemExit('Usage: original_native_reload_probe.py <disposable-runtime>')
