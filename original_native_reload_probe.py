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


def run(session,kickoff=False,finish=False):
    env=e.clean_env(os.environ)
    if not env.get('DISPLAY','').startswith(':'):
        raise RuntimeError('Private CI display required')
    session=Path(session).resolve()
    autosaves=list((session/'saves').glob('*/autosave.sqlite'))
    if len(autosaves)!=1 or autosaves[0].is_symlink():
        raise RuntimeError('Expected exactly one restored native league')
    expected=autosaves[0].resolve()
    fixture=None
    if finish and not kickoff:
        raise ValueError('Full-time monitor requires kickoff mode')
    if kickoff:
        from original_fixture_gate import next_native_fixture
        fixture=next_native_fixture(expected)
        if fixture is None:
            raise RuntimeError('No eligible native fixture in test save')
    if finish:
        from original_match_history import HISTORY_PATH
        from original_full_league_validation import completed_own,verify_restored_fixture
        from original_native_finish_gate import expected_names,fresh_history,reserved_score_saved
        if (session/HISTORY_PATH).exists() or (session/HISTORY_PATH).is_symlink():
            raise RuntimeError('Finish monitor requires a fresh history database')
        previous=completed_own(expected)
        names=expected_names(expected,fixture)
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
            if kickoff:
                # Only the pinned, disposable menu sequence; never send keys
                # to an operator's desktop. Upstream logs match construction
                # without requiring any config flag or test instrumentation.
                def match_created():
                    log.seek(0)
                    data=log.read()
                    return (b'[Notice] in [Match::Match]: Starting Match' in data and
                            b'[Notice] in [Match::Match]: Done creating match!' in data)
                if match_created():
                    raise RuntimeError('Unexpected match before menu kickoff')
                for step,key in enumerate(('Return','Return','Return'),1):
                    press_key(key,env)
                    diagnostic_frame(f'kickoff-{step:02d}',env)
                wait_for(match_created,120,game)
                time.sleep(5)
                if game.poll() is not None or not opened_database(game.pid,expected):
                    raise RuntimeError('Native match session lost its restored league')
                diagnostic_frame('kickoff-04-created',env)
                print(json.dumps(dict(nativeMatchConstructionVerified=True,
                    nativeMenuKickoffSequenceVerified=True,expectedFixture=fixture,
                    expectedFixtureIndependentlyConfirmedInMatch=False,
                    defaultConfigLaunch=True,commandArgumentCount=0,
                    matchCompleted=False,normalExitVerified=False,
                    automaticProductionKickoff=False,
                    scope='Disposable UI input, upstream match constructor logs and open autosave; not completed match or independent team identity evidence')),flush=True)
                if finish:
                    # No guessed timer or keypress at halftime: normal native
                    # settings do not expose a verified halftime log marker.
                    print('At halftime, continue the match in the private display. Do not start another match.',flush=True)
                    final=wait_for(lambda: fresh_history(session,names),5400,game)
                    diagnostic_frame('finish-01-native-history',env)
                    # GameOverPage saves fresh history and focuses Continue.
                    # Only act after the native full-time row is verified.
                    if not opened_database(game.pid,expected):
                        raise RuntimeError('Reserved autosave lost at full time')
                    time.sleep(1)
                    if fresh_history(session,names)!=final:
                        raise RuntimeError('Native full-time history changed before Continue')
                    e.call(['xdotool','windowfocus','--sync',wid],env)
                    press_key('Return',env)
                    candidate=wait_for(lambda: reserved_score_saved(expected,fixture,previous,final['history']),60,game)
                    diagnostic_frame('finish-02-score-saved',env)
                    print(json.dumps(dict(nativeContinueScoreCandidate=candidate,automaticFinalContinue=True,
                                          automaticHalftimeVerified=False,scoreWrittenByBridge=False)),flush=True)
                    print('Exit the native game normally from its menus without playing another match.',flush=True)
                    if game.wait(timeout=300)!=0:
                        raise RuntimeError('Native game did not close normally')
                    report=verify_restored_fixture(session,fixture,previous)
                    if report['history']!=final['history']:
                        raise RuntimeError('Closed history changed after final Continue')
                    report.update(normalExitVerified=True,automaticFinalContinue=True,
                                  automaticHalftimeVerified=False,automaticProductionKickoff=False,
                                  scoreWrittenByBridge=False,defaultConfigLaunch=True)
                    print(json.dumps(report),flush=True)
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
    if len(sys.argv) in (3,4) and sys.argv[1]=='--inside-private-display' and (len(sys.argv)==3 or sys.argv[3] in ('--kickoff','--finish')):
        run(sys.argv[2],kickoff=len(sys.argv)==4,finish='--finish' in sys.argv)
    elif len(sys.argv) in (2,3) and (len(sys.argv)==2 or sys.argv[2]=='--kickoff'):
        e.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                sys.executable,Path(__file__).resolve(),'--inside-private-display',
                Path(sys.argv[1]).resolve(),*sys.argv[2:]],e.clean_env(os.environ))
    else:
        raise SystemExit('Usage: original_native_reload_probe.py <disposable-runtime> [--kickoff]; --finish requires an explicitly managed private display')
