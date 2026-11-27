"""Test persistence with a genuine save produced by the pinned upstream game.
The first session uses upstream's unmodified league smoke fixture. The second
session restores the bytes into a fresh runtime and verifies the actual database
read-only. A separate native UI probe then opens the restored autosave.
"""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import sys

import original_engine as e
import original_saves as saves
import original_results as results


def populate(build, session):
    session.mkdir()
    for name in e.RUNTIME:
        p=build/name
        if p.is_dir():
            shutil.copytree(p,session/name)
        else:
            shutil.copy2(p,session/name)


def save_manifest(root):
    return {p.relative_to(root).as_posix():e.digest(p)
            for p in sorted(root.rglob('*')) if p.is_file()}


def inspect(root):
    databases=sorted(root.glob('*/autosave.sqlite'))
    if not databases:
        raise RuntimeError('Upstream league smoke did not create an autosave')
    reports=[]
    for path in databases:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('PRAGMA trusted_schema=OFF')
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
                raise RuntimeError('Native save integrity check failed')
            teams=db.execute('SELECT count(*) FROM teams').fetchone()[0]
            fixtures=db.execute('SELECT count(*) FROM calendar').fetchone()[0]
            settings=db.execute('SELECT count(*) FROM settings').fetchone()[0]
            if min(teams,fixtures,settings)<=0:
                raise RuntimeError('Native league save missing required data')
            reports.append(dict(teams=teams,fixtures=fixtures,settings=settings))
    return reports


def verify_calendar(restored,report):
    """Independent SQL cross-check against genuine native-generated save data."""
    checked=[]
    for item in report['saves']:
        path=restored/item['saveName']/'autosave.sqlite'
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
            team,name=db.execute('SELECT s.team_id,t.name FROM settings s JOIN teams t ON t.id=s.team_id').fetchone()
            if item['managedTeam']!={'id':team,'name':name}:
                raise RuntimeError('Managed native club mismatch')
            calendar=db.execute('SELECT id,team1_id,team2_id,timestamp FROM calendar ORDER BY timestamp,id').fetchall()
            played={r[0] for r in db.execute('SELECT calendar_id FROM match_results WHERE played=1')}
            own=[r for r in calendar if team in r[1:3]]
            pending=[r[0] for r in own if r[0] not in played]
            completed={r[0] for r in own if r[0] in played}
            expected=pending[:results.MAX_PENDING]
            actual=[r['nativeFixtureId'] for r in item['pendingFixtures']]
            if actual!=expected or item['pendingTruncated']!=(len(pending)>results.MAX_PENDING):
                raise RuntimeError('Native calendar pending fixture mismatch')
            actual_completed={r['nativeFixtureId'] for r in item['results']}
            if not actual_completed.issubset(completed) or (not item['truncated'] and actual_completed!=completed):
                raise RuntimeError('Native calendar completed fixture mismatch')
            if set(actual)&actual_completed:
                raise RuntimeError('Played fixture incorrectly shown as pending')
            checked.append(dict(managedTeam=name,ownFixtures=len(own),pending=len(pending),completed=len(completed)))
    if not checked or not any(x['pending'] for x in checked):
        raise RuntimeError('Native test generated no pending fixtures')
    return checked


def main():
    env=e.clean_env(os.environ)
    work=e.cache_root()/e.REVISION
    build=e.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='native-save-roundtrip-') as tmp:
        base=Path(tmp)
        first,second=base/'first',base/'second'
        populate(build,first)
        e.check_config(work/'source',first)
        e.call(['bash',work/'source/tests/run_menu_smoke.sh',first/'gameplayfootball',
                work/'source/data/menu_smoke_league.config','90',
                '[menu-smoke] Main menu ready, opening League Mode',
                '[menu-smoke] League save created, entering league page',
                '[menu-smoke] League page flow succeeded'],env,first)
        native=first/'saves'
        original=save_manifest(native)
        if not original:
            raise RuntimeError('No actual native save files')
        before=inspect(native)
        with saves.locked_store(base/'store') as store:
            if not saves.commit(store,first,0):
                raise RuntimeError('Native clean exit was not saved')
            snapshot=saves.current_snapshot(store)
            if save_manifest(snapshot)!=original:
                raise RuntimeError('Snapshot differs from native output')
            populate(build,second)
            e.check_config(work/'source',second)
            saves.restore(store,second)
            restored=second/'saves'
            if save_manifest(restored)!=original or inspect(restored)!=before:
                raise RuntimeError('Restored native save differs')
            report=results.collect(second,e.REVISION,0)
            if not report['saves'] or report['skippedSaves']:
                raise RuntimeError('Native league result reader failed')
            calendar_checks=verify_calendar(restored,report)
            if save_manifest(restored)!=original:
                raise RuntimeError('Read-only native save inspection changed bytes')
            if saves.commit(store,second,1) or saves.current_snapshot(store)!=snapshot:
                raise RuntimeError('Failed exit replaced previous save')
            e.check_config(work/'source',second)
            print(json.dumps(dict(revision=e.REVISION,nativeLeagueSaveCreated=True,
                 snapshotByteExact=True,restoredByteExact=True,sqliteIntegrityPassed=True,
                 failedExitPreservedSnapshot=True,readOnlyResultsVerified=True,
                 savedFiles=len(original),nativeLeagueDatabases=before,
                 nativeCalendarVerified=True,nativeCalendarChecks=calendar_checks,
                 nativeMenuReopenVerified=False,productionConfigChanged=False),
                 indent=2),flush=True)
            # The previous immutable snapshot stays untouched even if native reload writes autosave.
            e.call([sys.executable,Path(__file__).resolve().with_name('original_native_reload_probe.py'),second],env)
            if save_manifest(snapshot)!=original:
                raise RuntimeError('Native reload modified retained snapshot')
        print(json.dumps(dict(revision=e.REVISION,nativeLeagueSaveCreated=True,
             snapshotByteExact=True,restoredByteExact=True,sqliteIntegrityPassed=True,
             failedExitPreservedSnapshot=True,readOnlyResultsVerified=True,
             savedFiles=len(original),nativeLeagueDatabases=before,
                 nativeCalendarVerified=True,nativeCalendarChecks=calendar_checks,
             nativeMenuReopenVerified=True,productionConfigChanged=False),indent=2))
    e.verify_install(work,env)


if __name__=='__main__':
    main()
