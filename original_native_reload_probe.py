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


def press_key(key,env):
    # The native GUI samples current key state, not every X11 key event.
    # A default xdotool tap can be shorter than the slow software-rendered frame.
    e.call(['xdotool','keydown','--clearmodifiers',key],env)
    try:
        time.sleep(.24)
    finally:
        e.call(['xdotool','keyup',key],env)
    time.sleep(2)


def diagnostic_frame(label,env):
    # Only test frames from this disposable display; no user desktop.
    output=os.environ.get('RUNNER_TEMP')
    if not output:
        return
    folder=Path(output)/'native-reload-diagnostics'
    folder.mkdir(exist_ok=True)
    try:
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','x11grab',
            '-video_size','1280x1024','-i',env['DISPLAY'],'-frames:v','1',
            '-threads','1',str(folder/(label+'.png'))],env=env,timeout=8,check=True)
    except (OSError,subprocess.SubprocessError) as exc:
        print('Diagnostic frame unavailable: '+str(exc),file=sys.stderr)


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
            diagnostic_frame('00-start',env)
            for index,key in enumerate(('Return','Down','Return','Return','Return','Return'),1):
                press_key(key,env)
                print('Native navigation step '+str(index)+': '+key,flush=True)
                diagnostic_frame(f'{index:02d}-{key}',env)
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
            diagnostic_frame('99-failure',env)
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
