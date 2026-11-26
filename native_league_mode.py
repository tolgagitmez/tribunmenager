"""Immutable operator-created native-only development league routing."""
import sqlite3

SCHEMA="""
CREATE TABLE IF NOT EXISTS native_only_leagues(
 league TEXT PRIMARY KEY REFERENCES leagues(code), created REAL NOT NULL);
CREATE TRIGGER IF NOT EXISTS native_only_immutable_update BEFORE UPDATE ON native_only_leagues
BEGIN SELECT RAISE(ABORT,'Native league mode is immutable'); END;
CREATE TRIGGER IF NOT EXISTS native_only_immutable_delete BEFORE DELETE ON native_only_leagues
BEGIN SELECT RAISE(ABORT,'Native league mode is immutable'); END;
CREATE TRIGGER IF NOT EXISTS native_only_no_conversion BEFORE INSERT ON native_only_leagues
WHEN EXISTS(SELECT 1 FROM live_matches WHERE league=NEW.league)
 OR EXISTS(SELECT 1 FROM fixtures WHERE league=NEW.league AND home_score IS NOT NULL)
BEGIN SELECT RAISE(ABORT,'Existing league cannot switch engines'); END;
CREATE TRIGGER IF NOT EXISTS native_only_no_official_result BEFORE UPDATE OF home_score,away_score,home_yellows,away_yellows,home_reds,away_reds ON fixtures
WHEN EXISTS(SELECT 1 FROM native_only_leagues WHERE league=OLD.league)
BEGIN SELECT RAISE(ABORT,'Native-only results remain private'); END;
CREATE TRIGGER IF NOT EXISTS native_only_no_legacy_final BEFORE UPDATE OF final_state ON live_matches
WHEN NEW.final_state IS NOT NULL AND EXISTS(SELECT 1 FROM native_only_leagues WHERE league=OLD.league)
BEGIN SELECT RAISE(ABORT,'Legacy final state forbidden'); END;
"""
for table in ('live_match_operations','live_match_frames','native_shadow_matches','native_shadow_frames','season_player_state','season_fixture_appearances'):
    SCHEMA+=f"""CREATE TRIGGER IF NOT EXISTS native_only_block_{table} BEFORE INSERT ON {table}
    WHEN EXISTS(SELECT 1 FROM native_only_leagues WHERE league=NEW.league)
    BEGIN SELECT RAISE(ABORT,'Legacy league write forbidden'); END;
    """

def is_native(db,league):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='native_only_leagues'").fetchone():return False
    return db.execute('SELECT 1 FROM native_only_leagues WHERE league=?',(league,)).fetchone() is not None

def unfinished(db,league,before=None,due=None):
    sql="""SELECT 1 FROM fixtures f WHERE f.league=? AND NOT EXISTS(
      SELECT 1 FROM native_av_season_results n WHERE n.league=f.league AND n.round=f.round AND n.home=f.home AND n.away=f.away)"""
    args=[league]
    if before is not None:sql+=' AND f.round<?';args.append(before)
    if due is not None:sql+=' AND f.kickoff<=?';args.append(due)
    return db.execute(sql+' LIMIT 1',args).fetchone() is not None

def fixtures(db,league):
    rows=[dict(x) for x in db.execute('SELECT * FROM fixtures WHERE league=? ORDER BY round,home',(league,))]
    if not is_native(db,league):return rows
    results={(r['round'],r['home'],r['away']):r for r in db.execute('SELECT * FROM native_av_season_results WHERE league=?',(league,))}
    for f in rows:
        r=results.get((f['round'],f['home'],f['away']))
        if r:
            for key in ('home_score','away_score','home_yellows','away_yellows','home_reds','away_reds'):f[key]=r[key]
    return rows

def season_db(db,league):
    if not is_native(db,league):return db
    from native_av_season import PrivateSeason
    return PrivateSeason(db)

def match_lifecycle(db,league,rows,now):
    """Safe display states; never publish attempt IDs, error strings or paths."""
    import hashlib
    from pathlib import Path
    try:boot=hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()
    except OSError:boot=None
    jobs={(r['round'],r['home'],r['away']):r for r in db.execute("""
        SELECT j.round,j.home,j.away,j.state,l.boot,l.expires,l.quarantined
        FROM native_av_jobs j LEFT JOIN native_av_leases l ON l.attempt=j.attempt
        WHERE j.league=?""",(league,))}
    unfinished=[f['round'] for f in rows if f['home_score'] is None]
    first_pending=min(unfinished,default=None)
    for f in rows:
        job=jobs.get((f['round'],f['home'],f['away']))
        if f['home_score'] is not None:state='completed'
        elif job and job['state']=='failed':state='failed'
        elif job and job['state']=='ready':state='inconsistent'
        elif job and job['state']=='running':
            if not boot or job['boot']!=boot or job['expires'] is None or job['expires']<=now or job['quarantined']:
                state='interrupted'
            else:state='running'
        elif f['kickoff']>now:state='scheduled'
        elif f['round']!=first_pending:state='blocked'
        elif job and job['state']=='queued':state='queued'
        else:state='preparing'
        f['nativeState']=state
    return rows
