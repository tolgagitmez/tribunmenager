"""Private native season ledger, isolated from the official season tables."""
import hashlib
import json
import sqlite3
from contextlib import closing
import season_state
import native_season

def names(sql):
    return sql.replace('season_player_state','native_av_season_player_state').replace('season_fixture_appearances','native_av_season_fixture_appearances')

SCHEMA=names(season_state.SCHEMA)+"""
CREATE TABLE IF NOT EXISTS native_av_season_results(
 league TEXT NOT NULL, round INTEGER NOT NULL, home INTEGER NOT NULL, away INTEGER NOT NULL,
 home_score INTEGER NOT NULL, away_score INTEGER NOT NULL,
 home_yellows INTEGER NOT NULL, away_yellows INTEGER NOT NULL,
 home_reds INTEGER NOT NULL, away_reds INTEGER NOT NULL,
 evidence_sha TEXT NOT NULL, PRIMARY KEY(league,round,home,away)
);
"""
KEY='league=? AND round=? AND home=? AND away=?'

class PrivateSeason:
    def __init__(self,db):self.db=db
    def execute(self,sql,params=()):return self.db.execute(names(sql),params)

def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def verify_candidate(final,manifest,sidecar):
    candidate=native_season.verify_report(final,manifest,sidecar)
    return candidate

def apply(db,key,report):
    """Called inside the existing AV completion transaction, never commits itself."""
    if report.get('authoritative') is not False or report.get('verified') is not True:
        raise ValueError('Private verified evidence required')
    season=report['season']
    if season.get('authoritative') is not False or season.get('score')!=report['score']:
        raise ValueError('Season score mismatch')
    league,r,h,a=key
    if h==a or r<0:raise ValueError('Invalid fixture')
    digest=hashlib.sha256(canonical(report).encode()).hexdigest()
    prior=db.execute('SELECT evidence_sha FROM native_av_season_results WHERE '+KEY,key).fetchone()
    if prior:
        if prior[0]!=digest:raise ValueError('Conflicting native result')
        return False
    if db.execute("""SELECT 1 FROM fixtures f WHERE f.league=? AND f.round<?
         AND NOT EXISTS(SELECT 1 FROM native_av_season_results n WHERE n.league=f.league
         AND n.round=f.round AND n.home=f.home AND n.away=f.away) LIMIT 1""",(league,r)).fetchone():
        raise ValueError('Previous native round is incomplete')
    if db.execute("""SELECT 1 FROM native_av_season_results WHERE league=? AND round>=?
         AND (home IN (?,?) OR away IN (?,?)) LIMIT 1""",(league,r,h,a,h,a)).fetchone():
        raise ValueError('Duplicate team round or out-of-order result')
    db.execute('INSERT INTO native_av_season_results VALUES(?,?,?,?,?,?,?,?,?,?,?)',
               (*key,*season['score'],*season['cards'],*season['reds'],digest))
    season_state.apply_fixture(PrivateSeason(db),key,season['appearances'])
    return True

def standings(db,league):
    result={}
    for h,a,hg,ag in db.execute('SELECT home,away,home_score,away_score FROM native_av_season_results WHERE league=? ORDER BY round',(league,)):
        for slot,gf,ga in ((h,hg,ag),(a,ag,hg)):
            row=result.setdefault(slot,dict(slot=slot,played=0,won=0,drawn=0,lost=0,points=0,gf=0,ga=0))
            row['played']+=1
            row['won']+=int(gf>ga);row['drawn']+=int(gf==ga);row['lost']+=int(gf<ga)
            row['points']+=3 if gf>ga else 1 if gf==ga else 0
            row['gf']+=gf;row['ga']+=ga
    return sorted(result.values(),key=lambda r:(-r['points'],-(r['gf']-r['ga']),-r['gf'],r['slot']))
