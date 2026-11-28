"""Read-only preflight for handing native candidates to the web league.

The existing live_match worker owns the production transaction (including
player appearances and discipline). Do not race or bypass that owner.
This report never authorizes a production import.
"""
from contextlib import closing
import json
import math
from pathlib import Path
import re
import sqlite3

from original_catalog import connect

def preflight(root,web_db,key,now):
    if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):
        raise ValueError('Explicit reserved fixture key required')
    if type(now) not in (int,float) or not math.isfinite(now):
        raise ValueError('Invalid preflight timestamp')
    root=Path(root)
    with closing(connect(root/'verified-result-candidates.sqlite3')) as db:
        candidate=db.execute('SELECT payload FROM candidates WHERE key=?',(key,)).fetchone()
    with closing(connect(root/'fixture-dispatch.sqlite3')) as db:
        claim=db.execute('SELECT mapping FROM claims WHERE key=?',(key,)).fetchone()
    if candidate is None or claim is None:
        raise ValueError('Reviewed candidate and original reservation required')
    candidate,mapping=json.loads(candidate[0]),json.loads(claim[0])
    fields=('league','round','home','away')
    if candidate['fixtureKey']!=key or any(candidate[f]!=mapping[f] for f in fields):
        raise ValueError('Candidate does not match reserved web fixture')
    if any(candidate['nativeFixture'].get(f)!=mapping[f] for f in
           ('nativeFixtureId','homeTeamId','awayTeamId','nativeDate','managedTeamId')):
        raise ValueError('Candidate native identity does not match reservation')
    score=(candidate['homeGoals'],candidate['awayGoals'])
    if any(type(v) is not int or not 0<=v<=99 for v in score):
        raise ValueError('Invalid candidate score')
    identity=tuple(mapping[f] for f in fields)
    web_db=Path(web_db)
    if web_db.is_symlink() or not web_db.is_file():
        raise ValueError('Existing regular web league database required')
    blockers=[]
    # Read a consistent snapshot of the real schema, including WAL commits.
    # Unlike the closed native save reader, never use immutable=1 here.
    with closing(sqlite3.connect(web_db.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        fixture=db.execute('''SELECT kickoff,home_score,away_score FROM fixtures
            WHERE league=? AND round=? AND home=? AND away=?''',identity).fetchone()
        worker=db.execute('''SELECT final_state FROM live_matches
            WHERE league=? AND round=? AND home=? AND away=?''',identity).fetchone()
        if fixture is None:
            blockers.append('web-fixture-missing')
        else:
            kickoff,hg,ag=fixture
            if kickoff!=mapping['kickoff']:
                blockers.append('web-kickoff-changed')
            if now<kickoff+300:
                blockers.append('scheduled-match-not-ended')
            if hg is not None or ag is not None:
                blockers.append('web-score-already-set')
                if (hg,ag)!=score:
                    blockers.append('web-score-conflict')
        if worker is not None:
            blockers.append('legacy-worker-already-owns-fixture')
        prior=db.execute('''SELECT 1 FROM fixtures WHERE league=? AND round<?
            AND (home_score IS NULL OR away_score IS NULL) LIMIT 1''',identity[:2]).fetchone()
        if prior:
            blockers.append('prior-round-unfinished')
    # The native history currently contains only team-level statistics.
    # Never infer player minutes, cards, condition or suspension data.
    blockers.extend(['native-authoritative-ownership-not-integrated',
                     'native-player-season-evidence-unavailable'])
    return dict(fixtureKey=key,fixture=dict(zip(fields,identity)),candidateScore=list(score),
                blockers=blockers,productionImportAllowed=False,readOnly=True,
                scoreWritten=False,seasonStateWritten=False)

if __name__=='__main__':
    import argparse,time
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('web_db',type=Path)
    p.add_argument('key')
    a=p.parse_args()
    print(json.dumps(preflight(a.root,a.web_db,a.key,time.time()),indent=2))
