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


def controller_event(trace,kind):
    path=Path(str(trace)+'.controls')
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size>8192:
        raise ValueError('Invalid controller observation file')
    rows=[json.loads(line) for line in path.read_bytes().split(b'\n')[:-1]]
    if any(row.get('kind')=='error' for row in rows):
        raise RuntimeError('Native controller observation failed: '+str(rows))
    order=('game-ready','pause-menu','controller-menu','cpu-control','resumed')
    if tuple(row.get('kind') for row in rows)!=order[:len(rows)]:
        raise ValueError('Unexpected native controller event sequence')
    return next((row for row in rows if row['kind']==kind),None)


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


def press_until(key,predicate,env,game,attempts=1,hold_seconds=5):
    """Hold a single physical key until the native transition, always release it."""
    for attempt in range(attempts):
        if game.poll() is not None:
            raise RuntimeError('Native process exited before input')
        existing=predicate()
        if existing:
            return existing
        print(json.dumps(dict(nativeInput=key,attempt=attempt+1)),flush=True)
        subprocess.run(['xdotool','keydown','--clearmodifiers',key],env=env,check=True,timeout=5)
        try:
            deadline=time.monotonic()+hold_seconds
            while time.monotonic()<deadline and game.poll() is None:
                value=predicate()
                if value:
                    break
                time.sleep(.1)
            else:
                value=None
        finally:
            subprocess.run(['xdotool','keyup',key],env=env,check=True,timeout=5)
        # The engine polls keyboard state; allow it to consume the release
        # and finish constructing the destination page before any next key.
        time.sleep(2)
        if value:
            return value
        value=predicate()
        if value:
            return value
    raise RuntimeError('Native transition not observed after '+key)


def native_input_records(trace):
    path=Path(str(trace)+'.inputs')
    if not path.exists():
        return []
    if path.is_symlink() or path.stat().st_size>32768:
        raise ValueError('Invalid native input diagnostics')
    return [json.loads(line) for line in path.read_bytes().split(b'\n')[:-1]]


def pause_focus(trace):
    return next((row['name'] for row in reversed(native_input_records(trace)) if row.get('kind')=='pause-focus'),None)


def controller_sides(trace):
    return next((row['sides'] for row in reversed(native_input_records(trace)) if row.get('kind')=='controller-sides'),None)


def changed_value(read,previous):
    value=read()
    return value if value is not None and value!=previous else None


PAUSE_BUTTONS=('button_gameplan','button_setpieces','button_controllerselect','button_camerasettings',
               'button_visualoptions','button_systemsettings','button_replay','button_resume','button_quit')


def pause_navigation_key(focus):
    if focus not in PAUSE_BUTTONS:
        raise RuntimeError('Unknown native pause focus: '+str(focus))
    current=PAUSE_BUTTONS.index(focus)
    target=PAUSE_BUTTONS.index('button_controllerselect')
    return 'Up' if current>target else 'Down' if current<target else None


def diagnostic_frame(label,env,folder=None):
    # Only test frames from this disposable display; no user desktop.
    if folder is None:
        output=os.environ.get('RUNNER_TEMP')
        if not output:
            return
        folder=Path(output)/'native-reload-diagnostics'
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    try:
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','x11grab',
            '-video_size','1280x1024','-i',env['DISPLAY'],'-frames:v','1',
            '-threads','1',str(folder/(label+'.png'))],env=env,timeout=8,check=True)
    except (OSError,subprocess.SubprocessError) as exc:
        print('Diagnostic frame unavailable: '+str(exc),file=sys.stderr)


def run(session,kickoff=False,finish=False,halftime_bundle=None,close_after_score=False,reference_output=None,debug_trace=None):
    env=e.clean_env(os.environ)
    if not env.get('DISPLAY','').startswith(':'):
        raise RuntimeError('Private CI display required')
    session=Path(session).resolve()
    autosaves=list((session/'saves').glob('*/autosave.sqlite'))
    if len(autosaves)!=1 or autosaves[0].is_symlink():
        raise RuntimeError('Expected exactly one restored native league')
    expected=autosaves[0].resolve()
    fixture=None
    half_gate=None
    if halftime_bundle is not None:
        from original_halftime_gate import load_bundle,frame,score
        half_gate=load_bundle(halftime_bundle,e.REVISION,e.digest(session/'football.config'))
    if debug_trace is not None and (not finish or not kickoff or not close_after_score or half_gate is not None or reference_output is not None):
        raise ValueError('Debugger pilot requires isolated full normal league mode')
    if close_after_score and not finish:
        raise ValueError('Automatic close requires final score validation')
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
    reference=None
    if reference_output is not None:
        if not kickoff or finish or halftime_bundle is not None:
            raise ValueError('Reference capture must be a separate kickoff-only session')
        from original_league_reference_capture import ReferenceCapture
        reference=ReferenceCapture(reference_output)
    with tempfile.TemporaryFile() as log:
        command=[str(session/'gameplayfootball')]
        game_env=env
        if debug_trace is not None:
            from original_normal_league_trial import event,summarize
            debug_trace=Path(debug_trace).resolve()
            if debug_trace.exists():
                raise ValueError('New native debugger trace required')
            game_env=dict(env,TRIBUN_LEAGUE_TRACE=str(debug_trace))
            command=['gdb','-nx','-batch','-return-child-result','-ex','set confirm off',
                '-ex','set print thread-events off','-ex','start','-x',
                str(Path(__file__).with_name('original_normal_league_gdb.py')),
                '-ex','continue','--args',*command]
        game=subprocess.Popen(command,cwd=session,env=game_env,stdout=log,
                              stderr=subprocess.STDOUT,start_new_session=debug_trace is not None)
        try:
            native_pid=game.pid
            def capture(label):
                diagnostic_frame(label,env,debug_trace.parent/'screens' if debug_trace is not None else None)
            def wait_debug_phase(kind,seconds):
                # Evidence only: never change the clock, dismiss menus blindly,
                # or treat a timeout as a successful phase transition.
                began=time.monotonic()
                next_sample=[0]
                def observe():
                    if not opened_database(native_pid,expected):
                        raise RuntimeError('Reserved autosave lost while waiting for '+kind)
                    found=event(debug_trace,kind)
                    if found:
                        return found
                    elapsed=int(time.monotonic()-began)
                    if elapsed>=next_sample[0]:
                        from original_normal_league_trial import trace_records
                        rows=trace_records(debug_trace)
                        print(json.dumps(dict(waitingForNativePhase=kind,elapsedSeconds=elapsed,
                            observedPhases=[row['kind'] for row in rows])),flush=True)
                        capture(f'wait-{kind}-{elapsed:04d}')
                        next_sample[0]=elapsed+60
                    return None
                try:
                    return wait_for(observe,seconds,game)
                except Exception as exc:
                    raise RuntimeError('Native phase '+kind+' not verified; see retained trace and screens') from exc
            if debug_trace is not None:
                ready=wait_for(lambda:event(debug_trace,'ready'),45,game)
                candidate_pid=ready['pid']
                if (type(candidate_pid) is not int or candidate_pid<=1 or
                        os.getsid(candidate_pid)!=game.pid or
                        Path(f'/proc/{candidate_pid}/exe').resolve()!=(session/'gameplayfootball').resolve()):
                    raise RuntimeError('Debugger inferior is not the private native executable')
                native_pid=candidate_pid
            def window():
                p=subprocess.run(['xdotool','search','--onlyvisible','--pid',str(native_pid),
                                  '--name','^League Soccer$'],env=env,capture_output=True,
                                 text=True,timeout=5)
                return p.stdout.strip().splitlines()[0] if p.returncode==0 and p.stdout.strip() else None

            wid=wait_for(window,60,game)
            time.sleep(5)
            e.call(['xdotool','windowfocus','--sync',wid],env)
            if opened_database(native_pid,expected):
                raise RuntimeError('Restored DB opened before UI selection')
            # Intro -> main menu; Quick Match initially focused. One Down
            # selects League Mode; Load Saved is focused on the next page.
            # The sole save entry is focused; the confirmation defaults to Load.
            diagnostic_frame('00-start',env)
            for index,key in enumerate(('Return','Down','Return','Return','Return','Return'),1):
                press_key(key,env)
                print('Native navigation step '+str(index)+': '+key,flush=True)
                diagnostic_frame(f'{index:02d}-{key}',env)
                if opened_database(native_pid,expected):
                    break
            wait_for(lambda: opened_database(native_pid,expected),15,game)
            time.sleep(2)
            if game.poll() is not None or not opened_database(native_pid,expected):
                raise RuntimeError('Native restored database did not remain open')
            print(json.dumps(dict(nativeMenuReopenVerified=True,restoredAutosaveOpened=True,
                  defaultConfigLaunch=debug_trace is None,commandArgumentCount=0,
                  gameProcessAlive=True,normalExitVerified=False,
                  scope='Native UI keyboard navigation and process file descriptor; not a full resumed match.')),
                  flush=True)
            if reference is not None:
                for _ in range(3):
                    reference.sample(env,'restored-menu-candidate')
                    time.sleep(.5)
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
                if game.poll() is not None or not opened_database(native_pid,expected):
                    raise RuntimeError('Native match session lost its restored league')
                diagnostic_frame('kickoff-04-created',env)
                print(json.dumps(dict(nativeMatchConstructionVerified=True,
                    nativeMenuKickoffSequenceVerified=True,expectedFixture=fixture,
                    expectedFixtureIndependentlyConfirmedInMatch=False,
                    defaultConfigLaunch=debug_trace is None,commandArgumentCount=0,
                    matchCompleted=False,normalExitVerified=False,
                    automaticProductionKickoff=False,
                    scope='Disposable UI input, upstream match constructor logs and open autosave; not completed match or independent team identity evidence')),flush=True)
                if reference is not None:
                    # Bounded passive collection, never infer the phase from time
                    # or send a Continue command. Review exported frames offline.
                    deadline=time.monotonic()+420
                    while time.monotonic()<deadline and game.poll() is None:
                        if not opened_database(native_pid,expected):
                            raise RuntimeError('Restored league lost during reference collection')
                        reference.sample(env,'post-kickoff-unlabeled')
                        time.sleep(6)
                    if game.poll() is not None:
                        raise RuntimeError('Native game exited during reference collection')
                    print(json.dumps(reference.finish(e.REVISION,e.digest(session/'football.config'),fixture)),flush=True)
                if finish:
                    half_report=None
                    if debug_trace is not None:
                        # League KickOff assigns the keyboard to the managed side.
                        # Use the original pause/controller menu to set No Team,
                        # never modify the debugger inferior or fabricate input scores.
                        ready=wait_for(lambda:controller_event(debug_trace,'game-ready'),120,game)
                        print(json.dumps(dict(nativeGameplayReady=ready)),flush=True)
                        # Confirm the WM has activated the private window before sending input.
                        subprocess.run(['xdotool','windowactivate','--sync',wid],env=env,check=True,timeout=10)
                        if subprocess.check_output(['xdotool','getactivewindow'],env=env,text=True,timeout=5).strip()!=str(wid):
                            raise RuntimeError('Native game window not active before pause')
                        # A 240ms tap was lost in the previous CI run even after
                        # readiness. Hold through the sampled SDL input state.
                        paused=press_until('Escape',lambda:controller_event(debug_trace,'pause-menu'),env,game,attempts=2)
                        if paused['humanCounts']!=ready['humanCounts']:
                            raise RuntimeError('Native controller changed before pause')
                        time.sleep(2)
                        capture('pilot-controller-pause')
                        # Verify the real native focus rather than counting rows.
                        focus=wait_for(lambda:pause_focus(debug_trace),15,game)
                        for _ in range(12):
                            key=pause_navigation_key(focus)
                            if key is None:
                                break
                            previous=focus
                            press_until(key,lambda:changed_value(lambda:pause_focus(debug_trace),previous),env,game,attempts=2)
                            # A held direction can repeat before the host releases it.
                            # Use the latest settled focus, not the first observed step.
                            focus=pause_focus(debug_trace)
                            print(json.dumps(dict(nativePauseFocus=focus)),flush=True)
                        if focus!='button_controllerselect':
                            raise RuntimeError('Native controller button not focused: '+str(focus))
                        menu=press_until('Return',lambda:controller_event(debug_trace,'controller-menu'),env,game)
                        capture('pilot-controller-selected')
                        counts=menu['humanCounts']
                        home=fixture['managedTeamId']==fixture['homeTeamId']
                        if counts!=([1,0] if home else [0,1]):
                            raise RuntimeError('Unexpected initial native controller assignment: '+str(counts))
                        sides=wait_for(lambda:controller_sides(debug_trace),20,game)
                        if sides.count(-1 if home else 1)!=1 or sum(v!=0 for v in sides)!=1:
                            raise RuntimeError('Unexpected native controller menu sides: '+str(sides))
                        for _ in range(4):
                            if all(v==0 for v in sides):
                                break
                            if sum(v!=0 for v in sides)!=1 or any(v not in (-1,0,1) for v in sides):
                                raise RuntimeError('Unexpected controller sides: '+str(sides))
                            key='Right' if -1 in sides else 'Left'
                            previous=sides
                            press_until(key,lambda:changed_value(lambda:controller_sides(debug_trace),previous),env,game,attempts=2)
                            sides=controller_sides(debug_trace)
                        if any(v!=0 for v in sides):
                            raise RuntimeError('Native controller menu did not settle at No Team: '+str(sides))
                        print(json.dumps(dict(nativeNeutralControllerSelection=sides)),flush=True)
                        capture('pilot-controller-neutral')
                        applied=press_until('Escape',lambda:controller_event(debug_trace,'cpu-control'),env,game)
                        if applied['humanCounts']!=[0,0]:
                            raise RuntimeError('Native controller reassignment did not release both teams')
                        resumed=press_until('Escape',lambda:controller_event(debug_trace,'resumed'),env,game)
                        capture('pilot-cpu-resume')
                        print(json.dumps(dict(nativeBothTeamsCpuVerified=True,initialHumanCounts=counts,finalHumanCounts=applied['humanCounts'],nativeResumeVerified=True,resumedClockMs=resumed['clockMs'])),flush=True)
                        wait_debug_phase('half-menu',900)
                        if not opened_database(native_pid,expected):
                            raise RuntimeError('Reserved autosave lost at observed halftime')
                        diagnostic_frame('pilot-half',env)
                        e.call(['xdotool','windowfocus','--sync',wid],env)
                        press_key('Return',env)
                        wait_debug_phase('half-continue',30)
                        half_report=dict(nativePhaseMenuObserved=True,nativeContinueObserved=True,singleContinueSent=True)
                    elif half_gate is None:
                        print('At halftime, continue the match in the private display. Do not start another match.',flush=True)
                    else:
                        def half_ready():
                            if fresh_history(session,names) is not None:
                                raise RuntimeError('Full time reached without verified halftime transition')
                            if not opened_database(native_pid,expected):
                                raise RuntimeError('Reserved autosave lost before halftime')
                            return half_gate.observe(frame(env))
                        wait_for(half_ready,2700,game)
                        half_report=dict(titleButtonScores=half_gate.last_scores,consecutiveSamples=3)
                        diagnostic_frame('half-01-verified-screen',env)
                        # Recheck both regions immediately before the single input.
                        current=frame(env)
                        if min(score(r,current) for r in half_gate.regions)<.98 or not opened_database(native_pid,expected):
                            raise RuntimeError('Halftime screen changed before Continue')
                        e.call(['xdotool','windowfocus','--sync',wid],env)
                        press_key('Return',env)
                        gone=[0]
                        def half_departed():
                            current=frame(env)
                            gone[0]=gone[0]+1 if max(score(r,current) for r in half_gate.regions)<.85 else 0
                            return gone[0]>=3
                        wait_for(half_departed,30,game)
                        half_report.update(singleContinueSent=True,halftimeScreenDeparted=True)
                        print(json.dumps(dict(calibratedHalftimeTransition=half_report,secondHalfGameplayIndependentlyVerified=False)),flush=True)
                    final=wait_for(lambda: fresh_history(session,names),900 if debug_trace is not None else 5400,game)
                    if debug_trace is not None:
                        wait_debug_phase('fulltime',30)
                        summarize(debug_trace,fixture,final['history'])
                    diagnostic_frame('finish-01-native-history',env)
                    # GameOverPage saves fresh history and focuses Continue.
                    # Only act after the native full-time row is verified.
                    if not opened_database(native_pid,expected):
                        raise RuntimeError('Reserved autosave lost at full time')
                    time.sleep(1)
                    if fresh_history(session,names)!=final:
                        raise RuntimeError('Native full-time history changed before Continue')
                    e.call(['xdotool','windowfocus','--sync',wid],env)
                    press_key('Return',env)
                    candidate=wait_for(lambda: reserved_score_saved(expected,fixture,previous,final['history']),60,game)
                    diagnostic_frame('finish-02-score-saved',env)
                    print(json.dumps(dict(nativeContinueScoreCandidate=candidate,automaticFinalContinue=True,
                                          automaticHalftimeVerified=debug_trace is not None,calibratedHalftimeTransition=half_report if debug_trace is None else None,
                                          debuggerHalftimeTransition=half_report if debug_trace is not None else None,scoreWrittenByBridge=False)),flush=True)
                    if close_after_score:
                        # Request graceful closure through the window manager.
                        # Never use xdotool windowkill/windowclose or signals as
                        # evidence of a successful normal shutdown.
                        if window()!=wid or game.poll() is not None:
                            raise RuntimeError('Native window changed before close')
                        protocols=subprocess.check_output(['xprop','-id',wid,'WM_PROTOCOLS'],env=env,text=True,timeout=5)
                        if 'WM_DELETE_WINDOW' not in protocols:
                            raise RuntimeError('Native window has no graceful close protocol')
                        if reserved_score_saved(expected,fixture,previous,final['history'])!=candidate:
                            raise RuntimeError('Native score changed before close')
                        subprocess.run(['wmctrl','-ic',hex(int(wid))],env=env,check=True,timeout=5)
                        print('Graceful window manager close requested after score verification.',flush=True)
                    else:
                        print('Exit the native game normally from its menus without playing another match.',flush=True)
                    if game.wait(timeout=60 if close_after_score else 300)!=0:
                        raise RuntimeError('Native game did not close normally')
                    report=verify_restored_fixture(session,fixture,previous)
                    if report['history']!=final['history']:
                        raise RuntimeError('Closed history changed after final Continue')
                    report.update(normalExitVerified=True,automaticFinalContinue=True,
                                  automaticHalftimeVerified=half_report is not None,calibratedHalftimeTransition=half_report,
                                  automaticProductionKickoff=False,
                                  scoreWrittenByBridge=False,defaultConfigLaunch=True,
                                  gracefulWindowCloseRequested=close_after_score,
                                  automaticNormalExitVerified=close_after_score)
                    if debug_trace is not None:
                        report.update(summarize(debug_trace,fixture,report['history']),
                                      experimentalClockConfiguration=True,defaultConfigLaunch=False,
                                      nativeSourcePatched=False,actualLeagueFixtureVerified=True,
                                      nativeBothTeamsCpuVerified=True,
                                      automaticHalftimeVerified=True,productionScoreWritten=False,
                                      calibratedHalftimeTransition=None,debuggerHalftimeTransition=half_report)
                        with debug_trace.with_suffix('.json').open('x') as out:
                            json.dump(report,out,indent=2,allow_nan=False)
                    print(json.dumps(report),flush=True)
        except Exception:
            capture('99-failure')
            if debug_trace is not None:
                print('Native phase trace at failure: '+(debug_trace.read_text(errors='replace')[-8192:] if debug_trace.exists() else 'missing'),file=sys.stderr)
                control_path=Path(str(debug_trace)+'.controls')
                print('Native controller trace at failure: '+(control_path.read_text(errors='replace')[-8192:] if control_path.exists() else 'missing'),file=sys.stderr)
                input_path=Path(str(debug_trace)+'.inputs')
                print('Native input trace at failure: '+(input_path.read_text(errors='replace')[-16384:] if input_path.exists() else 'missing'),file=sys.stderr)
            log.seek(0)
            print(log.read()[-6000:].decode(errors='replace'),file=sys.stderr)
            raise
        finally:
            if debug_trace is not None and game.poll() is None:
                # Only the inferior launched by this private debugger.
                import signal
                if 'native_pid' in locals() and native_pid!=game.pid:
                    try: os.kill(native_pid,signal.SIGTERM)
                    except ProcessLookupError: pass
            if game.poll() is None:
                game.terminate()
                try:
                    game.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    game.kill()
                    game.wait()


def managed_private_finish(session,bundle=None,debug_trace=None):
    """Run the finish monitor only under a private Xvfb with its own WM."""
    env=e.clean_env(os.environ)
    if not env.get('DISPLAY','').startswith(':'):
        raise RuntimeError('Private display required')
    if (bundle is None)==(debug_trace is None):
        raise ValueError('Exactly one private halftime observation method required')
    if bundle is not None:
        from original_halftime_gate import load_bundle
        load_bundle(bundle,e.REVISION,e.digest(Path(session)/'football.config'),require_league=True)
    wm=subprocess.Popen(['openbox','--sm-disable'],env=env,
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline and wm.poll() is None:
            probe=subprocess.run(['xprop','-root','_NET_SUPPORTING_WM_CHECK'],
                env=env,capture_output=True,text=True,timeout=5)
            if probe.returncode==0 and 'window id # 0x' in probe.stdout and not probe.stdout.rstrip().endswith('0x0'):
                break
            time.sleep(.2)
        else:
            raise RuntimeError('Private window manager unavailable')
        run(session,kickoff=True,finish=True,halftime_bundle=bundle,close_after_score=True,debug_trace=debug_trace)
    finally:
        if wm.poll() is None:
            wm.terminate()
            try:wm.wait(timeout=5)
            except subprocess.TimeoutExpired:
                wm.kill();wm.wait()


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--private-debugger-league':
        e.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                sys.executable,Path(__file__).resolve(),'--inside-debugger-league',
                Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve()],e.clean_env(os.environ))
    elif len(sys.argv)==4 and sys.argv[1]=='--inside-debugger-league':
        managed_private_finish(Path(sys.argv[2]),debug_trace=Path(sys.argv[3]))
    elif len(sys.argv)==4 and sys.argv[1]=='--capture-league-references':
        e.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                sys.executable,Path(__file__).resolve(),'--inside-league-references',
                Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve()],e.clean_env(os.environ))
    elif len(sys.argv)==4 and sys.argv[1]=='--inside-league-references':
        run(sys.argv[2],kickoff=True,reference_output=Path(sys.argv[3]).resolve())
    elif len(sys.argv)==4 and sys.argv[1]=='--private-managed-finish':
        e.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                sys.executable,Path(__file__).resolve(),'--inside-managed-finish',
                Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve()],e.clean_env(os.environ))
    elif len(sys.argv)==4 and sys.argv[1]=='--inside-managed-finish':
        managed_private_finish(Path(sys.argv[2]),Path(sys.argv[3]))
    elif len(sys.argv) in (5,6) and sys.argv[1]=='--inside-private-display' and sys.argv[3]=='--finish-auto-half' and (len(sys.argv)==5 or sys.argv[5]=='--close-after-score'):
        run(sys.argv[2],kickoff=True,finish=True,halftime_bundle=Path(sys.argv[4]).resolve(),
            close_after_score=len(sys.argv)==6)
    elif len(sys.argv) in (3,4) and sys.argv[1]=='--inside-private-display' and (len(sys.argv)==3 or sys.argv[3] in ('--kickoff','--finish')):
        run(sys.argv[2],kickoff=len(sys.argv)==4,finish='--finish' in sys.argv)
    elif len(sys.argv) in (2,3) and (len(sys.argv)==2 or sys.argv[2]=='--kickoff'):
        e.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                sys.executable,Path(__file__).resolve(),'--inside-private-display',
                Path(sys.argv[1]).resolve(),*sys.argv[2:]],e.clean_env(os.environ))
    else:
        raise SystemExit('Usage: original_native_reload_probe.py <disposable-runtime> [--kickoff]; --finish or --finish-auto-half <bundle> requires an explicitly managed private display')
