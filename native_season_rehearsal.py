"""Disposable season transaction rehearsal. Never opens a league database."""
import hashlib,json,sqlite3
import native_season
import season_state
SCHEMA="""
CREATE TABLE rehearsal_results(
 league TEXT NOT NULL, round INTEGER NOT NULL, home INTEGER NOT NULL, away INTEGER NOT NULL,
 home_score INTEGER NOT NULL, away_score INTEGER NOT NULL,
 candidate_sha TEXT NOT NULL, PRIMARY KEY(league,round,home,away));
"""
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False)
def create():
    db=sqlite3.connect(":memory:")
    db.row_factory=sqlite3.Row
    db.executescript(season_state.SCHEMA+SCHEMA)
    return db
def apply(db,key,final,manifest,report,fail=None):
    candidate=native_season.verify_report(final,manifest,report)
    league,round_number,home,away=key
    if league!="NATIVE-REHEARSAL" or type(round_number) is not int or round_number<0 or type(home) is not int or type(away) is not int or home==away or min(home,away)<0:
        raise ValueError("Only disposable rehearsal fixture supported")
    digest=hashlib.sha256(canonical({"final":final,"manifest":manifest,"candidate":candidate}).encode()).hexdigest()
    with db:
        db.execute("BEGIN IMMEDIATE")
        existing=db.execute("SELECT candidate_sha FROM rehearsal_results WHERE league=? AND round=? AND home=? AND away=?",key).fetchone()
        if existing:
            if existing["candidate_sha"]!=digest:raise ValueError("Conflicting completed fixture")
            return False
        prior=db.execute("""SELECT 1 FROM rehearsal_results WHERE league=? AND round>=?
            AND (home IN (?,?) OR away IN (?,?))""",(league,round_number,home,away,home,away)).fetchone()
        if prior:raise ValueError("Out-of-order or duplicate team round")
        db.execute("INSERT INTO rehearsal_results VALUES(?,?,?,?,?,?,?)",(*key,*candidate["score"],digest))
        season_state.apply_fixture(db,key,candidate["appearances"])
        if fail:fail()
        return True
def standings(db):
    result={}
    for row in db.execute("SELECT home,away,home_score,away_score FROM rehearsal_results ORDER BY round"):
        h,a,hg,ag=row
        for slot,gf,ga in ((h,hg,ag),(a,ag,hg)):
            r=result.setdefault(slot,dict(slot=slot,played=0,points=0,gf=0,ga=0))
            r["played"]+=1;r["points"]+=3 if gf>ga else 1 if gf==ga else 0;r["gf"]+=gf;r["ga"]+=ga
    return sorted(result.values(),key=lambda r:(-r["points"],-(r["gf"]-r["ga"]),-r["gf"],r["slot"]))
def snapshot(db):
    return {"standings":standings(db),"appearances":[dict(x) for x in db.execute("SELECT * FROM season_fixture_appearances ORDER BY round,slot,player_key")],"players":[dict(x) for x in db.execute("SELECT * FROM season_player_state ORDER BY slot,player_key")]}
def audit(final,manifest,report):
    db=create()
    try:
        key=("NATIVE-REHEARSAL",0,0,1)
        initial=snapshot(db)
        def fail():raise RuntimeError("Injected transaction failure")
        try:apply(db,key,final,manifest,report,fail)
        except RuntimeError:pass
        else:raise AssertionError("Expected rollback")
        if snapshot(db)!=initial:raise AssertionError("Partial transaction")
        if not apply(db,key,final,manifest,report):raise AssertionError("Retry rejected")
        saved=snapshot(db)
        if apply(db,key,final,manifest,report) or snapshot(db)!=saved:raise AssertionError("Duplicate result changed season")
        expected=native_season.candidate(final,manifest)
        if len(saved["appearances"])!=sum(a["minutes"]>0 for a in expected["appearances"]):raise AssertionError("Appearance count mismatch")
        return {"schema":1,"authoritative":False,"productionEnabled":False,"rollbackPassed":True,"retryPassed":True,"idempotent":True,
                "score":expected["score"],"cards":expected["cards"],"reds":expected["reds"],"standings":saved["standings"],
                "appearanceCount":len(saved["appearances"]),"note":"Disposable in-memory SQLite; not actual production persistence or process-crash recovery."}
    finally:db.close()
if __name__=="__main__":
    import sys
    from pathlib import Path
    trace=Path(sys.argv[1])
    with trace.open() as f:
        final=None
        for line in f:
            if line.strip():final=json.loads(line)
    manifest=json.loads(Path(str(trace)+".fixture.json").read_text())
    report=json.loads(Path(str(trace)+".season.json").read_text())
    print(json.dumps(audit(final,manifest,report),indent=2,allow_nan=False))
