"""Optional full-time debugger probe of the pinned upstream smoke match.

Separate symbol build; original release package, source and config unchanged.
No attachment to other processes, no production league writes, no FPS claims.
"""
import argparse
from collections import Counter
from contextlib import closing
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import re

import original_engine as e
from original_catalog import connect
from original_match_history import read_single,HISTORY_PATH
from original_native_saves_probe import populate

def validate_snapshot(raw,history,database):
    if raw.get('observationPoint')!='GameOverPage::Process' or raw.get('historySaved') is not True:
        raise ValueError('Expected final native observation')
    clock=raw.get('nativeMatchClockMs')
    if type(clock) is not int or clock!=history['nativeMatchClockMs'] or clock<5400000:
        raise ValueError('Native final clock differs from saved history')
    teams=raw.get('teams')
    if not isinstance(teams,list) or len(teams)!=2:
        raise ValueError('Two observed native teams required')
    output=[]
    with closing(connect(database)) as db:
        for side,t in enumerate(teams):
            score=history[('homeGoals','awayGoals')[side]]
            name=history[('homeTeam','awayTeam')[side]]
            tid=t.get('nativeTeamId')
            if type(tid) is not int or tid<=0 or type(t.get('side')) is not int or t['side']!=side or type(t.get('score')) is not int or t['score']!=score:
                raise ValueError('Native observed side or score differs')
            if db.execute('SELECT name FROM teams WHERE id=?',(tid,)).fetchall()!=[(name,)]:
                raise ValueError('Native observed team identity differs')
            roster={row[0] for row in db.execute('SELECT id FROM players WHERE team_id=?',(tid,))}
            rows=t.get('players')
            scorers=t.get('scorerIds')
            if not isinstance(rows,list) or not 11<=len(rows)<=128 or not isinstance(scorers,list) or len(scorers)>score:
                raise ValueError('Invalid observed roster or scorer count')
            ids=[p.get('nativePlayerId') for p in rows]
            if any(type(i) is not int or i not in roster for i in ids) or len(set(ids))!=len(ids):
                raise ValueError('Unknown or duplicate observed player')
            if any(type(i) is not int or i not in ids for i in scorers):
                raise ValueError('Unknown native goal scorer')
            goals=Counter(scorers)
            players=[]
            for p in rows:
                code=p.get('rawCardCode');fatigue=p.get('fatigueFactorInv')
                if type(code) is not int or code not in (0,1,2,3,4) or type(fatigue) not in (int,float) or not math.isfinite(fatigue) or not .01<=fatigue<=1 or type(p.get('activeAtFullTime')) is not bool:
                    raise ValueError('Invalid native card/fatigue/activity field')
                players.append(dict(side=side,nativePlayerId=p['nativePlayerId'],
                    goals=goals[p['nativePlayerId']],assists=None,playedClockMs=None,
                    yellow={0:0,1:1,2:2,3:0,4:1}[code],directRed=int(code>=3),
                    rawCardCode=code,fatigueFactorInv=fatigue,activeAtFullTime=p['activeAtFullTime']))
            if sum(p['activeAtFullTime'] for p in players)>11:
                raise ValueError('Too many active native players')
            output.append(dict(side=side,nativeTeamId=tid,score=score,players=players,
                               goalsWithoutCreditedScorer=score-len(scorers)))
    return dict(nativeMatchClockMs=clock,teams=output,scoreAndClockMatchHistory=True,
                observedIdsMatchDefaultDatabase=True,assistsAvailable=False,minutesAvailable=False,
                nativeFatigueIsWebFitness=False,productionImportAllowed=False)

def parse_log(text):
    prefix='TRIBUN_NATIVE_PLAYER_SNAPSHOT '
    lines=[line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
    if len(lines)!=1 or 'TRIBUN_NATIVE_PLAYER_ERROR ' in text:
        raise ValueError('Expected exactly one successful final debugger snapshot')
    return json.loads(lines[0])

def run(output):
    env=e.clean_env(os.environ)
    if not re.fullmatch(r':\d+(?:\.0)?',env.get('DISPLAY','')):
        raise ValueError('Private display required')
    work=e.cache_root()/e.REVISION
    e.verify_install(work,env)
    source=work/'source'
    with tempfile.TemporaryDirectory(prefix='native-player-symbols-') as tmp:
        build=Path(tmp)/'build'
        # Separate build with upstream's normal CMake configuration; no source
        # changes. A debugger stop and different build preclude FPS evidence.
        e.call(['cmake','-S',source,'-B',build,'-DCMAKE_BUILD_TYPE=RelWithDebInfo','-DBUILD_TESTING=OFF'],env)
        e.call(['cmake','--build',build,'--parallel','2'],env)
        e.check_source(source,env)
        e.check_config(source,build)
        session=Path(tmp)/'runtime'
        populate(build,session)
        observer=Path(__file__).resolve().with_name('original_native_player_gdb.py')
        config=source/'data/menu_smoke_full_match.config'
        if (session/HISTORY_PATH).exists():
            raise ValueError('Expected fresh private runtime')
        with tempfile.TemporaryFile() as log:
            result=subprocess.run(['gdb','-nx','-batch','-return-child-result',
                '-ex','set confirm off','-ex','set print thread-events off',
                '-x',str(observer),'-ex','run','--args',str(session/'gameplayfootball'),str(config)],
                cwd=session,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
            log.seek(0)
            if result.returncode:
                raise RuntimeError('Debug smoke failed: '+log.read()[-6000:].decode(errors='replace'))
            text=log.read().decode(errors='replace')
        if '[menu-smoke] Full-match verification succeeded, quitting test run' not in text:
            raise RuntimeError('Missing native full-match completion marker')
        history=read_single(session/HISTORY_PATH)
        report=validate_snapshot(parse_log(text),history,session/'databases/default/database.sqlite')
        report.update(revision=e.REVISION,debugBinarySha256=e.digest(session/'gameplayfootball'),
                      sourceConfigSha256=e.digest(config),historySha256=e.digest(session/HISTORY_PATH),
                      source='isolated-debugger-full-time-upstream-smoke',nativeSourcePatched=False,
                      nativeReleaseBinaryChanged=False,acceleratedSmoke=True,
                      actualLeagueFixtureVerified=False,performanceVerified=False)
        e.verify_install(work,env)
        with output.open('x') as f:
            json.dump(report,f,indent=2,allow_nan=False)
        print(json.dumps(report),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--inside-private-xvfb',action='store_true')
    a=p.parse_args()
    if a.inside_private_xvfb:
        run(a.output)
    else:
        e.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                sys.executable,Path(__file__).resolve(),a.output.resolve(),'--inside-private-xvfb'],e.clean_env(os.environ))

if __name__=='__main__':
    main()
