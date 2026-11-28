"""Experimental five-minute clock configuration in a disposable native league.

The original source and release package remain byte-identical. Debugger
observations prove phase identity, not release FPS or exact wall-clock timing.
"""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import tempfile

import original_engine as e
from original_native_saves_probe import populate,save_manifest
from original_saves import locked_store,commit,current_snapshot,restore

ORDER=('ready','first-half','half-boundary','half-menu','half-continue','regulation-end','fulltime')

def trace_records(path):
    path=Path(path)
    if not path.exists():
        return []
    if path.is_symlink() or path.stat().st_size>65536:
        raise ValueError('Invalid phase trace file')
    raw=path.read_bytes()
    # The writer flushes whole records. Ignore only an unfinished final line.
    rows=[json.loads(x) for x in raw.split(b'\n')[:-1]]
    if any(x.get('kind')=='error' for x in rows):
        raise ValueError('Native phase observer error: '+str(next(x for x in rows if x.get('kind')=='error')))
    if tuple(x.get('kind') for x in rows)!=ORDER[:len(rows)]:
        raise ValueError('Native phase sequence differs')
    times=[x.get('monotonic') for x in rows]
    if any(type(t) not in (int,float) or not math.isfinite(t) or t<0 for t in times) or any(b<a for a,b in zip(times,times[1:])):
        raise ValueError('Invalid native phase timing')
    return rows

def event(path,kind):
    return next((x for x in trace_records(path) if x['kind']==kind),None)

def regulation_timing(first,half,end):
    """Separate advancing clock, unpaused non-playing ticks and wall residual.

    The pinned engine increments actualTime_ms by 10 only when unpaused,
    and matchTime_ms by 180 only in play (five-minute setting, scale 1).
    SetMatchPhase resets the second-half clock to 45 minutes, so each
    period must be evaluated separately. Wall residual includes pauses,
    menu input, replays and scheduling/debugger overhead, not just CPU time.
    """
    actual=[row.get('actualTimeMs') for row in (first,half,end)]
    if any(type(v) is not int or v<0 or v%10 for v in actual):
        raise ValueError('Invalid native unpaused tick clock')
    if not actual[0]<=actual[1]<=actual[2]:
        raise ValueError('Native unpaused tick clock went backwards')
    factor=90/first['durationMinutes']*first['timeScale']
    periods=[]
    for name,start,stop,game_start in (
            ('firstHalf',first,half,0),
            ('secondHalf',half,end,2700000)):
        advancing=(stop['clockMs']-game_start)/factor/1000
        ticks=(stop['actualTimeMs']-start['actualTimeMs'])/1000
        wall=stop['monotonic']-start['monotonic']
        if advancing<0 or ticks+0.011<advancing:
            raise ValueError('Native tick clock cannot account for advancing match clock')
        periods.append(dict(period=name,wallSeconds=round(wall,3),
                            unpausedSimulationSeconds=round(ticks,3),
                            clockAdvancingSimulationSeconds=round(advancing,3),
                            nonAdvancingSimulationSeconds=round(ticks-advancing,3),
                            wallMinusSimulationSeconds=round(wall-ticks,3)))
    metrics=('wallSeconds','unpausedSimulationSeconds','clockAdvancingSimulationSeconds',
             'nonAdvancingSimulationSeconds','wallMinusSimulationSeconds')
    total={key:round(sum(period[key] for period in periods),3) for key in metrics}
    total['addedTimeSimulationSeconds']=round(total['clockAdvancingSimulationSeconds']-300,3)
    return dict(periods=periods,total=total,
                scope='Read-only debugger phase boundary timing; residual is not a measured CPU or FPS bottleneck')


def summarize(path,fixture,history,resumed=None):
    rows=trace_records(path)
    if len(rows)!=len(ORDER):
        raise ValueError('Incomplete normal league phase evidence')
    by={x['kind']:x for x in rows}
    first,half,end,final=[by[k] for k in ('first-half','half-boundary','regulation-end','fulltime')]
    ids=[fixture['homeTeamId'],fixture['awayTeamId']]
    if first['teamIds']!=ids or final['teamIds']!=ids or first['durationMinutes']!=5 or first['timeScale']!=1:
        raise ValueError('Wrong native fixture or five-minute clock configuration')
    if not 2700000<=half['clockMs']<=3600000 or not 5400000<=end['clockMs']<=6300000:
        raise ValueError('Invalid regulation boundaries')
    if final['clockMs']!=history['nativeMatchClockMs'] or final['score']!=[history['homeGoals'],history['awayGoals']]:
        raise ValueError('Native final observation differs from closed history')
    duration=end['monotonic']-first['monotonic']
    timing=regulation_timing(first,half,end)
    if resumed is not None:
        start=resumed.get('monotonic')
        if (resumed.get('kind')!='resumed' or resumed.get('humanCounts')!=[0,0] or
                type(start) not in (int,float) or not first['monotonic']<=start<=half['monotonic']):
            raise ValueError('Invalid CPU match resume boundary')
        timing.update(firstHalfStartToCpuResumeSeconds=round(start-first['monotonic'],3),
                      cpuResumeToRegulationEndSeconds=round(end['monotonic']-start,3),
                      cpuResumeToFulltimeScreenSeconds=round(final['monotonic']-start,3))
    return dict(normalLeaguePhaseSequenceVerified=True,expectedFixtureIndependentlyConfirmedInMatch=True,
                configuredInPlayMinutes=5,smokeAccelerationDisabled=True,
                observedRegulationPhaseSpanSeconds=round(duration,3),
                differenceFrom300Seconds=round(duration-300,3),
                regulationTiming=timing,
                observedHalftimeMenuSeconds=round(by['half-continue']['monotonic']-by['half-menu']['monotonic'],3),
                firstHalfEndClockMs=half['clockMs'],secondHalfEndClockMs=end['clockMs'],
                debuggerTimingOnly=True,realTime300SecondMatchVerified=False,
                productionImportAllowed=False,performanceVerified=False)

def trial_config(raw):
    # MatchDurationGameTimeFromRealMilliseconds clamps the normal setting to
    # 5-90 minutes. This sets only the disposable game's supported options.
    values={'match_duration_minutes':'5.000000','menu_smoke_match_time_scale':'1.0',
            'match_extra_time':'false','menu_smoke_test_full_match':'false',
            # SDL pumps input on the render thread. Keep software-rendered
            # frames short enough to sample a single menu arrow pulse.
            'context_x':'640','context_y':'360'}
    lines=[]
    for line in raw.decode('utf-8').splitlines():
        m=re.match(r'^\s*"([^"]+)"\s+',line)
        if m and m.group(1) in values:
            continue
        if m and m.group(1).startswith('menu_smoke_') and m.group(1) not in values:
            raise ValueError('Unexpected smoke option in default native configuration')
        lines.append(line)
    lines.extend(f'"{key}" "{value}"' for key,value in values.items())
    return ('\n'.join(lines)+'\n').encode('utf-8')

def release_timing_report(events,history):
    from original_capture_probe import FULL,match_intervals
    halves,full_line,extra=match_intervals(events)
    score=f"{history['homeTeam']} {history['homeGoals']} - {history['awayGoals']} {history['awayTeam']}"
    if full_line!=f'{FULL} {score}' or history['nativeMatchClockMs']<5400000:
        raise ValueError('Release full-time signal differs from saved match history')
    return dict(source='release-quick-match',debuggerAttached=False,clockScale=1,
                configuredMinutes=5,leagueFixtureVerified=False,history=history,
                activeToFulltimeMarkerSeconds=round(halves[-1][1]-halves[0][0],3),
                observedHalvesSeconds=[round(end-start,3) for start,end in halves],
                extraGameplayEntries=extra)


def measure_release_quick_match(build,source,env,output):
    from original_capture_probe import ACTIVE,HALF,FULL,DONE
    from original_match_history import HISTORY_PATH,read_single
    with tempfile.TemporaryDirectory(prefix='release-match-timing-') as tmp:
        session=Path(tmp)/'game'
        populate(build,session)
        history=session/HISTORY_PATH
        if history.exists():
            raise ValueError('Fresh release match history required')
        # Match the league pilot clock and viewport. The native Quick Match
        # menu driver handles CPU selection and halftime without a debugger.
        config=(source/'data/menu_smoke_full_match.config').read_bytes()
        accelerated=b'"menu_smoke_match_time_scale" "6.0"'
        if (config.count(accelerated)!=1 or b'"match_duration_minutes" "5.000000"' not in config
                or b'"menu_smoke_test_full_match" "true"' not in config):
            raise ValueError('Unexpected pinned Quick Match configuration')
        config_path=session/'release-timing.config'
        config_path.write_bytes(config.replace(accelerated,b'"menu_smoke_match_time_scale" "1.0"')
                                +b'\n"context_x" "640"\n"context_y" "360"\n"menu_smoke_quit_delay_ms" "0"\n')
        events=[]
        command=['timeout','--kill-after=10s','1200s','stdbuf','-oL','-eL',
                 str(session/'gameplayfootball'),str(config_path)]
        with subprocess.Popen(command,cwd=session,env=env,stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,text=True,errors='replace') as game:
            for line in game.stdout:
                line=line.strip()
                for marker in (ACTIVE,HALF,FULL,DONE):
                    if line.startswith(marker):
                        events.append((time.monotonic(),marker,line))
                        print('Release timing: '+line,flush=True)
                        break
            if game.wait()!=0:
                raise RuntimeError('Release timing process failed: '+str(game.returncode))
        result=release_timing_report(events,read_single(history))
        result.update(revision=e.REVISION,binarySha256=e.digest(build/'gameplayfootball'),
                      configSha256=e.digest(config_path),markerEvents=events)
        (output/'release-timing.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)


def run_trial(work,build,env,output):
    output=Path(output).resolve()
    if output.exists():
        raise ValueError('New trial evidence directory required')
    output.mkdir(mode=0o700)
    release=e.verify_install(work,env)
    measure_release_quick_match(release,work/'source',env,output)
    with tempfile.TemporaryDirectory(prefix='native-normal-league-pilot-') as tmp:
        base=Path(tmp); setup=base/'setup'; session=base/'session'
        populate(release,setup)
        e.call(['bash',work/'source/tests/run_menu_smoke.sh',setup/'gameplayfootball',
                work/'source/data/menu_smoke_league.config','90',
                '[menu-smoke] Main menu ready, opening League Mode',
                '[menu-smoke] League save created, entering league page',
                '[menu-smoke] League page flow succeeded'],env,setup)
        with locked_store(base/'store') as root:
            if not commit(root,setup,0):
                raise RuntimeError('No closed native league save')
            snapshot=current_snapshot(root); before=save_manifest(snapshot)
            populate(build,session)
            e.check_config(work/'source',session)
            restore(root,session)
            if save_manifest(session/'saves')!=before:
                raise RuntimeError('Native trial restore differs')
            raw=(session/'football.config').read_bytes()
            config=trial_config(raw)
            for path in (session/'football.config',session/'data/football.config'):
                path.write_bytes(config)
            (output/'trial-config.txt').write_bytes(config)
            try:
                e.call([sys.executable,Path(__file__).with_name('original_native_reload_probe.py'),
                        '--private-debugger-league',session,output/'phases.jsonl'],env)
            finally:
                if current_snapshot(root)!=snapshot or save_manifest(snapshot)!=before:
                    raise RuntimeError('Native trial changed retained snapshot')
                e.verify_install(work,env)
    result=json.loads((output/'phases.json').read_text())
    if not result.get('normalLeaguePhaseSequenceVerified') or not result.get('normalExitVerified'):
        raise RuntimeError('Incomplete normal league pilot result')
    print(json.dumps(result),flush=True)
