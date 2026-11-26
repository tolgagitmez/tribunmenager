"""Rehearse the two real concurrent recordings in a disposable league database.
Never opens the server database; does not grant capacity or official authority.
"""
import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from contextlib import closing
import native_av_queue as q
import native_av_season
import season_state

def replay(configs,reports):
    if len(configs)!=2 or len(reports)!=2:raise ValueError('Two complete matches required')
    with tempfile.TemporaryDirectory(prefix='tribun-integrated-') as tmp:
        path=Path(tmp)/'league.sqlite'
        keys=[('NATIVE-INTEGRATED',0,0,1),('NATIVE-INTEGRATED',0,2,3)]
        with closing(sqlite3.connect(path)) as db,db:
            db.executescript("""CREATE TABLE fixtures(league,round,home,away,home_score);
                CREATE TABLE live_matches(league,round,home,away,kickoff,config);"""+q.SCHEMA+season_state.SCHEMA)
            for key,config in zip(keys,configs):
                db.execute('INSERT INTO fixtures VALUES(?,?,?,?,NULL)',key)
                db.execute('INSERT INTO live_matches VALUES(?,?,?,?,?,?)',(*key,100,q.canonical(config)))
            if q.sync(db,100)!=2 or q.sync(db,100)!=0:raise ValueError('Queue duplication')
        jobs=[q.claim(path,2,100),q.claim(path,2,100)]
        if any(job is None for job in jobs) or q.claim(path,2,100) is not None:raise ValueError('Reservation failure')
        for (key,sha,_,attempt),report in zip(jobs,reports):
            if not q.finish(path,key,sha,attempt,report=report):raise ValueError('Completion rejected')
            if q.finish(path,key,sha,attempt,report=report):raise ValueError('Duplicate accepted')
        with closing(sqlite3.connect(path)) as db:
            db.row_factory=sqlite3.Row
            standings=native_av_season.standings(db,keys[0][0])
            scores=[list(row) for row in db.execute('SELECT home_score,away_score FROM native_av_season_results ORDER BY home')]
            expected=[r['score'] for r in reports]
            appearances=db.execute('SELECT count(*) FROM native_av_season_fixture_appearances').fetchone()[0]
            expected_appearances=sum(a['minutes']>0 for r in reports for a in r['season']['appearances'])
            if scores!=expected or len(standings)!=4 or appearances!=expected_appearances:raise ValueError('Persisted season mismatch')
            if db.execute("SELECT count(*) FROM native_av_jobs WHERE state='ready'").fetchone()[0]!=2:raise ValueError('Missing ready jobs')
            if db.execute('SELECT count(*) FROM fixtures WHERE home_score IS NOT NULL').fetchone()[0] or db.execute('SELECT count(*) FROM season_player_state').fetchone()[0]:raise ValueError('Official data changed')
            return {'passed':True,'authoritative':False,'productionQualified':False,'scores':scores,'standings':standings,
                    'appearanceCount':appearances,'duplicateRejected':True,'officialTablesUnchanged':True}

def audit(directory):
    cap=json.loads((directory/'capacity-report.json').read_text())
    if cap.get('passed') is not True or cap.get('requestedMatches')!=2 or cap.get('allMatchesPassed') is not True or not 285<=cap['overlapSeconds']<=310:
        raise ValueError('Concurrent trial did not pass')
    names=['match-01','match-02'];configs=[];reports=[]
    for i,name in enumerate(names):
        fixture=directory/'fixtures'/(name+'.json')
        config=json.loads(fixture.read_text())
        report=q.verify_recording(fixture,directory/name,q.digest(config))
        native=json.loads((directory/name/'live-report.json').read_text())
        if native['fixtureSha256']!=cap['matches'][i]['fixtureSha256'] or not isinstance(native.get('motionAudit'),dict):
            raise ValueError('Capacity evidence mismatch or missing motion audit')
        configs.append(config);reports.append(report)
    if len({q.digest(c) for c in configs})!=2:raise ValueError('Duplicate fixtures')
    if len({r['traceSha256'] for r in reports})!=2:raise ValueError('Duplicate trace')
    result=replay(configs,reports)
    result['overlapSeconds']=cap['overlapSeconds']
    result['scope']='Actual recordings replayed into disposable database; not live league authority'
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    try:r=audit(a.directory)
    except (OSError,ValueError,KeyError,TypeError,IndexError,sqlite3.Error) as exc:
        r={'passed':False,'failureType':type(exc).__name__,'productionQualified':False}
    a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(json.dumps(r,indent=2))
    return 0 if r['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
