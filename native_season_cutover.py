"""Rehearse native result cutover using ONLY a disposable in-memory SQLite copy."""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
import argparse
import season_state
import native_av_season as ledger
import league_standings

KEY='league=? AND round=? AND home=? AND away=?'

def digest(v):
    return hashlib.sha256(ledger.canonical(v).encode()).hexdigest()

def require(ok,msg):
    if not ok:raise ValueError(msg)

def rehearse(source,league):
    # Never write to source or accept a persistent destination.
    with closing(sqlite3.connect(':memory:')) as db:
        source.backup(db)
        db.row_factory=sqlite3.Row
        with db:
            return _project(db,league)

def _project(db,league):
    require(db.execute('PRAGMA database_list').fetchone()[2]=='','Only in-memory rehearsal is permitted')
    teams=[dict(r) for r in db.execute('SELECT * FROM teams WHERE league=? ORDER BY slot',(league,))]
    require(bool(teams),'Unknown league')
    require(not db.execute('SELECT 1 FROM fixtures WHERE league=? AND home_score IS NOT NULL',(league,)).fetchone(),'Existing official results prohibit native cutover')
    for table in ('live_match_operations','live_match_frames','season_player_state','season_fixture_appearances'):
        require(not db.execute('SELECT 1 FROM '+table+' WHERE league=? LIMIT 1',(league,)).fetchone(),'Legacy simulation or season state exists')
    require(not db.execute('SELECT 1 FROM live_matches WHERE league=? AND final_state IS NOT NULL',(league,)).fetchone(),'Legacy final state exists')
    results=db.execute('SELECT * FROM native_av_season_results WHERE league=? ORDER BY round,home,away',(league,)).fetchall()
    require(bool(results),'No verified private results')
    # Only whole rounds; no publication of a partial table.
    rounds=sorted({r['round'] for r in results})
    require(rounds==list(range(rounds[-1]+1)),'Nonconsecutive completed rounds')
    for r in rounds:
        expected={tuple(x) for x in db.execute('SELECT home,away FROM fixtures WHERE league=? AND round=?',(league,r))}
        actual={(x['home'],x['away']) for x in results if x['round']==r}
        require(expected and expected==actual,'Incomplete native round')
    for row in results:
        key=tuple(row[k] for k in ('league','round','home','away'))
        job=db.execute('SELECT state,config_sha,report FROM native_av_jobs WHERE '+KEY,key).fetchone()
        frozen=db.execute('SELECT config FROM live_matches WHERE '+KEY,key).fetchone()
        require(job is not None and job['state']=='ready' and frozen is not None,'Missing ready job or frozen fixture')
        report=json.loads(job['report'])
        require(digest(report)==row['evidence_sha'] and digest(json.loads(frozen['config']))==job['config_sha']==report['configSha256'],'Evidence/config digest mismatch')
        require(report.get('verified') is True and report.get('authoritative') is False and report.get('engine')=='league-soccer'
                and report.get('audioOwnershipVerified') is True and report.get('controlSource') in ('local-diagnostic','league-gateway'),'Unqualified native AV result')
        state=report['season']
        score=[row['home_score'],row['away_score']]
        cards=[row['home_yellows'],row['away_yellows']]
        reds=[row['home_reds'],row['away_reds']]
        require(state.get('engine')=='league-soccer' and state.get('done') is True and state.get('authoritative') is False
                and state['score']==report['score']==score and state['cards']==cards and state['reds']==reds,'Native season result mismatch')
        # Compare actual frozen starting fitness and discipline from the previous
        # projected round for every player that participated.
        if key[1]>0:
            for p in state['appearances']:
                if p['minutes']<=0:continue
                slot=key[2+p['team']]
                identity={'uid':p.get('rosterUid'),'id':p['rosterId'],'fitness':p['startFitness']}
                readiness=season_state.status(db,league,slot,identity,key[1])
                require(not readiness['season']['suspended'] and abs(readiness['fitness']-p['startFitness'])<=.02,'Frozen player readiness differs from previous native round')
        updated=db.execute('UPDATE fixtures SET home_score=?,away_score=?,home_yellows=?,away_yellows=?,home_reds=?,away_reds=? WHERE '+KEY+' AND home_score IS NULL',(*score,*cards,*reds,*key))
        require(updated.rowcount==1,'Missing or already settled fixture')
        season_state.apply_fixture(db,key,state['appearances'])
    # Exact comparison against the private ledger, including all player counters.
    for table in ('season_player_state','season_fixture_appearances'):
        official=[tuple(x) for x in db.execute('SELECT * FROM '+table+' WHERE league=? ORDER BY 1,2,3,4,5',(league,))]
        private=[tuple(x) for x in db.execute('SELECT * FROM native_av_'+table+' WHERE league=? ORDER BY 1,2,3,4,5',(league,))]
        require(sorted(official)==sorted(private),'Native and projected season state differ')
    fix=[dict(x) for x in db.execute('SELECT * FROM fixtures WHERE league=? ORDER BY round,home',(league,))]
    standings=league_standings.project(teams,fix)
    private={x['slot']:x for x in ledger.standings(db,league)}
    for s in standings:
        if s['slot'] not in private:require(s['played']==0,'Unexpected played match');continue
        p=private[s['slot']]
        require(all(s[a]==p[b] for a,b in (('played','played'),('w','won'),('d','drawn'),('l','lost'),('gf','gf'),('ga','ga'),('points','points'))),'Standings mismatch')
    return {'passed':True,'authoritative':False,'productionQualified':False,'sourceUnchanged':True,
        'completeRounds':rounds,'fixtures':len(results),'standings':[{k:v for k,v in r.items() if k!='manager'} for r in standings],
        'playerAppearances':db.execute('SELECT count(*) FROM season_fixture_appearances WHERE league=?',(league,)).fetchone()[0],
        'scope':'Only in-memory rehearsal of existing official season schema; no official publication'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('database',type=Path);p.add_argument('league')
    a=p.parse_args()
    with closing(sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        print(json.dumps(rehearse(db,a.league),indent=2,ensure_ascii=False))

if __name__=='__main__':main()
