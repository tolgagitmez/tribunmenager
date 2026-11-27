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


def verify_standings(restored,report):
    """Compare web totals to the pinned native page's aggregate SQL."""
    checked=[]
    for item in report['saves']:
        path=restored/item['saveName']/'autosave.sqlite'
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
            table=item.get('standings')
            if not table:
                raise RuntimeError('Native standings missing')
            team=item['managedTeam']['id']
            league=db.execute('SELECT l.name FROM teams t JOIN leagues l ON t.league_id=l.id WHERE t.id=?',(team,)).fetchone()[0]
            if table['league']!=league:
                raise RuntimeError('Native standings league mismatch')
            clubs=db.execute('SELECT t.id,t.name FROM teams t JOIN leagues l ON t.league_id=l.id WHERE l.name=? ORDER BY t.name',(league,)).fetchall()
            native_stats={row[0]:row[1:] for row in db.execute("""
              SELECT team_id,COUNT(*),
                SUM(CASE WHEN gf>ga THEN 1 ELSE 0 END),
                SUM(CASE WHEN gf=ga THEN 1 ELSE 0 END),
                SUM(CASE WHEN gf<ga THEN 1 ELSE 0 END),
                SUM(gf),SUM(ga),
                SUM(CASE WHEN gf>ga THEN 3 WHEN gf=ga THEN 1 ELSE 0 END)
              FROM (
                SELECT team1_id AS team_id,team1_goals AS gf,team2_goals AS ga
                FROM match_results WHERE played=1
                UNION ALL
                SELECT team2_id AS team_id,team2_goals AS gf,team1_goals AS ga
                FROM match_results WHERE played=1
              ) GROUP BY team_id
            """)}
            def stats(ident):
                return native_stats.get(ident,(0,0,0,0,0,0,0))
            expected=sorted(clubs,key=lambda c:(-stats(c[0])[6],-(stats(c[0])[4]-stats(c[0])[5])))
            form_rows=db.execute("""SELECT m.team1_id,m.team2_id,m.team1_goals,m.team2_goals
                FROM match_results m JOIN calendar c ON c.id=m.calendar_id
                WHERE m.played=1 ORDER BY date(c.timestamp),m.id""").fetchall()
            actual=table['rows']
            if len(actual)!=len(expected):
                raise RuntimeError('Native standings team count mismatch')
            for position,((ident,name),row) in enumerate(zip(expected,actual),1):
                p,w,d,l,gf,ga,pts=stats(ident)
                form=[]
                for home,away,hg,ag in form_rows:
                    if ident==home:
                        a,b=hg,ag
                    elif ident==away:
                        a,b=ag,hg
                    else:
                        continue
                    form.append('W' if a>b else 'D' if a==b else 'L')
                want=(position,ident,name,p,w,d,l,gf,ga,gf-ga,pts,''.join(form[-5:]),ident==team)
                got=tuple(row[key] for key in ('position','teamId','name','played','won','drawn','lost',
                    'goalsFor','goalsAgainst','goalDifference','points','form','managed'))
                if got!=want:
                    raise RuntimeError('Native standings calculation mismatch')
            checked.append(dict(league=league,teams=len(actual),
                playedResults=db.execute('SELECT COUNT(*) FROM match_results WHERE played=1').fetchone()[0],
                allRowsMatched=True))
    if not checked:
        raise RuntimeError('No native standings verified')
    return checked


def verify_managed_squad(restored,report):
    """Compare the actual saved club rows and explicit XML values independently."""
    import xml.etree.ElementTree as ET
    checked=[]
    for item in report['saves']:
        path=restored/item['saveName']/'autosave.sqlite'
        team=item['managedTeam']['id']
        squad=item.get('managedSquad')
        if not squad or not squad['readOnly'] or squad['representsLiveLineup']:
            raise RuntimeError('Native saved squad report missing or mislabeled')
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
            expected=db.execute("""SELECT id,firstname,lastname,role,formationorder
                FROM players WHERE team_id=? ORDER BY formationorder,id""",(team,)).fetchall()
            actual=[(p['id'],p['name'],p['role'],p['formationOrder']) for p in squad['players']]
            want=[(i,' '.join(x for x in (first,last) if x),role,order)
                  for i,first,last,role,order in expected]
            if actual!=want[:128] or squad['truncated']!=(len(want)>128) or len(actual)<11:
                raise RuntimeError('Native saved roster mismatch or incomplete club')
            raw_formation,raw_tactics=db.execute('SELECT formation_xml,tactics_xml FROM teams WHERE id=?',(team,)).fetchone()
            slots=ET.fromstring('<root>'+(raw_formation or '')+'</root>')
            expected_slots=sorted((int(n.tag[1:]),n.findtext('role'),
                [float(x) for x in n.findtext('position').split(',')] if n.findtext('position') else None)
                for n in slots if n.tag in {f'p{i}' for i in range(1,12)})
            actual_slots=[(p['slot'],p['role'],p['rawPosition']) for p in (squad['formation'] or [])]
            if actual_slots!=expected_slots or len(actual_slots)!=11:
                raise RuntimeError('Native saved formation mismatch')
            raw=ET.fromstring('<root>'+(raw_tactics or '')+'</root>')
            explicit={n.tag:float(n.text) for n in raw if n.tag in __import__('original_catalog').KNOWN_TACTICS}
            actual_values={t['key']:t['value'] for t in (squad['tactics'] or []) if t['source']=='database'}
            if not explicit or actual_values!=explicit:
                raise RuntimeError('Native saved tactical values mismatch')
            checked.append(dict(managedTeam=item['managedTeam']['name'],rosterPlayers=len(actual),
                formationSlots=len(actual_slots),explicitTacticalValues=len(explicit),allRowsMatched=True))
    if not checked:
        raise RuntimeError('No genuine native squad verified')
    return checked


def verify_played_matchday(build,source,base,env):
    """Use the upstream's own matchday route, not a patched or rendered match."""
    session=base/'played-matchday'
    populate(build,session)
    e.check_config(source,session)
    e.call(['bash',source/'tests/run_menu_smoke.sh',session/'gameplayfootball',
            source/'data/menu_smoke_league_matchday.config','90',
            '[menu-smoke] Main menu ready, opening League Mode',
            '[menu-smoke] League dashboard advancing to next matchday',
            '[menu-smoke] League matchday summary reached successfully'],env,session)
    original=save_manifest(session/'saves')
    if not original:
        raise RuntimeError('No played matchday save')
    report=results.collect(session,e.REVISION,0)
    if not report['saves'] or report['skippedSaves']:
        raise RuntimeError('Could not read native played matchday')
    table_checks=verify_standings(session/'saves',report)
    if not any(x['playedResults']>0 for x in table_checks):
        raise RuntimeError('No native completed results in matchday report')
    # The first resolved day may involve other clubs only, so verify the
    # managed club's completed and pending fixtures without requiring a goal.
    for item in report['saves']:
        path=session/'saves'/item['saveName']/'autosave.sqlite'
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
            team=item['managedTeam']['id']
            expected=db.execute("""SELECT calendar_id,team1_id,team2_id,team1_goals,team2_goals
                FROM match_results WHERE played=1 AND (team1_id=? OR team2_id=?)
                ORDER BY calendar_id""",(team,team)).fetchall()
            actual=sorted((x['nativeFixtureId'],x['homeTeamId'],x['awayTeamId'],
                           x['homeGoals'],x['awayGoals']) for x in item['results'])
            if actual!=expected or set(x[0] for x in actual)&{x['nativeFixtureId'] for x in item['pendingFixtures']}:
                raise RuntimeError('Native completed matchday scores mismatch')
    if save_manifest(session/'saves')!=original:
        raise RuntimeError('Matchday report changed native save')
    with saves.locked_store(base/'played-store') as store:
        if not saves.commit(store,session,0):
            raise RuntimeError('Matchday snapshot failed')
        restored=base/'played-restored'
        restored.mkdir()
        saves.restore(store,restored)
        if save_manifest(restored/'saves')!=original or results.collect(restored,e.REVISION,0)!=report:
            raise RuntimeError('Played matchday report changed after restoration')
    e.check_config(source,session)
    print(json.dumps(dict(nativeMatchdayResultRoundtripVerified=True,
         source='upstream-matchday-fast-simulation',renderedMatchVerified=False,
         productionConfigChanged=False,standingsChecks=table_checks,
         managedCompletedResults=sum(len(x['results']) for x in report['saves']),
         savedFiles=len(original))),flush=True)


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
            standings_checks=verify_standings(restored,report)
            squad_checks=verify_managed_squad(restored,report)
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
                 nativeStandingsVerified=True,nativeStandingsChecks=standings_checks,
                 nativeSavedSquadVerified=True,nativeSavedSquadChecks=squad_checks,
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
                 nativeStandingsVerified=True,nativeStandingsChecks=standings_checks,
                 nativeSavedSquadVerified=True,nativeSavedSquadChecks=squad_checks,
             nativeMenuReopenVerified=True,productionConfigChanged=False),indent=2))
        verify_played_matchday(build,work/'source',base,env)
    e.verify_install(work,env)


if __name__=='__main__':
    main()
