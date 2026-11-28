"""Experimental five-minute clock configuration in a disposable native league.

The original source and release package remain byte-identical. Debugger
observations prove phase identity, not release FPS or exact wall-clock timing.
"""
import json
import math
import os
from pathlib import Path
import re
import sys
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

def summarize(path,fixture,history):
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
    return dict(normalLeaguePhaseSequenceVerified=True,expectedFixtureIndependentlyConfirmedInMatch=True,
                configuredInPlayMinutes=5,smokeAccelerationDisabled=True,
                observedRegulationPhaseSpanSeconds=round(duration,3),
                differenceFrom300Seconds=round(duration-300,3),
                observedHalftimeMenuSeconds=round(by['half-continue']['monotonic']-by['half-menu']['monotonic'],3),
                firstHalfEndClockMs=half['clockMs'],secondHalfEndClockMs=end['clockMs'],
                debuggerTimingOnly=True,realTime300SecondMatchVerified=False,
                productionImportAllowed=False,performanceVerified=False)

def trial_config(raw):
    # MatchDurationGameTimeFromRealMilliseconds clamps the normal setting to
    # 5-90 minutes. This sets only the disposable game's supported options.
    values={'match_duration_minutes':'5.000000','menu_smoke_match_time_scale':'1.0',
            'match_extra_time':'false','menu_smoke_test_full_match':'false'}
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

def run_trial(work,build,env,output):
    output=Path(output).resolve()
    if output.exists():
        raise ValueError('New trial evidence directory required')
    output.mkdir(mode=0o700)
    release=e.verify_install(work,env)
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
