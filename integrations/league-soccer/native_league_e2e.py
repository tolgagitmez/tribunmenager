"""One real native-only league fixture through actual server, worker and league UI.
Private disposable DB; only a single diagnostic slot, not admission evidence.
"""
import argparse
from contextlib import closing
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
import server
import native_av_queue as q
from live_match import Registry
from native_match_quality import inspect as inspect_quality

def require(ok,msg):
    if not ok:raise ValueError(msg)

def run(runtime,root):
    root.mkdir(mode=0o700)
    server.DATA=root/'league.sqlite3'
    server.LIVE_MATCHES=Registry()
    os.environ.update(TRIBUN_NATIVE_ONLY_LEAGUE='1',TRIBUN_NATIVE_AV_QUEUE='0',TRIBUN_NATIVE_SHADOW='0',
        TRIBUN_NATIVE_PRIVATE_SCREEN='1',TRIBUN_NATIVE_AV_GATEWAY_ROOT=str(root))
    server.init_db()
    home=server.new_league('Home',native=True)
    away_accounts=[server.join_league(home['code'],'Manager '+str(i)) for i in range(1,6)]
    foreign=server.new_league('Foreign',native=True)
    now=time.time()
    with closing(server.db()) as db,db:
        db.execute('UPDATE fixtures SET kickoff=? WHERE league=? AND round=0',(now-1,home['code']))
    require(server.settle_due(now)==3,'Expected three scheduled fixtures')
    require(not server.LIVE_MATCHES.matches,'Legacy worker registered')
    job=q.claim(server.DATA,1,managed=True)
    require(job is not None,'No diagnostic reservation')
    key,sha,config,attempt=job
    require(key[:3]==(home['code'],0,0) and key[3]==5,'Unexpected first fixture')
    require(config['matchBackend']=='native-only' and len(config['starters'])==len(config['awayStarters'])==11,'Frozen roster mismatch')
    http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(http.server_port)
    descriptor=root/'browser.json'
    fd=os.open(descriptor,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(dict(base=base,round=0,homeToken=home['token'],awayToken=away_accounts[4]['token'],foreignToken=foreign['token']),f)
    try:
        report=q.run_match(runtime,root,job,database=server.DATA,league_browser_descriptor=descriptor)
        require(report['commandHistory']['submitted']==[1,1] and report['commandHistory']['applied']==[1,1],'Incomplete two-manager history')
        require(q.finish(server.DATA,key,sha,attempt,report=report),'Private completion rejected')
        require(not q.finish(server.DATA,key,sha,attempt,report=report),'Duplicate completion accepted')
        def status(token):
            req=urllib.request.Request(base+'/api/league/status',headers={'Authorization':'Bearer '+token})
            with urllib.request.urlopen(req,timeout=10) as r:return json.loads(r.read())
        h=status(home['token']);a=status(away_accounts[4]['token'])
        require(h['matchBackend']==a['matchBackend']=='native-only','Wrong league backend')
        require(h['my_match']['home_score']==report['score'][0] and h['my_match']['away_score']==report['score'][1],'Projected score mismatch')
        require(h['my_match']['nativeState']=='completed' and h['nativeRoundStates']['completed']==1 and h['nativeRoundStates']['queued']==2,'Native lifecycle projection mismatch')
        points=lambda gf,ga:3 if gf>ga else 1 if gf==ga else 0
        require(next(x for x in h['standings'] if x['slot']==0)['points']==points(*report['score']),'Home points mismatch')
        require(next(x for x in a['standings'] if x['slot']==5)['points']==points(*reversed(report['score'])),'Away points mismatch')
        with closing(server.db()) as db:
            for table in ('live_match_operations','live_match_frames','season_player_state','season_fixture_appearances'):
                require(db.execute('SELECT count(*) FROM '+table+' WHERE league=?',(key[0],)).fetchone()[0]==0,'Legacy data written')
            require(db.execute('SELECT count(*) FROM fixtures WHERE home_score IS NOT NULL').fetchone()[0]==0,'Official score written')
            count=db.execute('SELECT count(*) FROM native_av_season_fixture_appearances WHERE league=?',(key[0],)).fetchone()[0]
            require(count==sum(x['minutes']>0 for x in report['season']['appearances']),'Appearance count mismatch')
            require(db.execute("SELECT count(*) FROM native_av_jobs WHERE state='queued' AND league=?",(key[0],)).fetchone()[0]==2,'Other fixtures not isolated')
        quality=inspect_quality(root/attempt/'run')
        return {'quality':quality,'passed':True,'authoritative':False,'productionQualified':False,'nativeOnly':True,'fixtureCount':1,
                'score':report['score'],'coverage':report['coverage'],'commandHistory':report['commandHistory'],
                'appearanceCount':count,'officialTablesUnchanged':True,'duplicateRejected':True,'leagueScreenVerified':True}
    except Exception as exc:
        q.finish(server.DATA,key,sha,attempt,error=type(exc).__name__)
        result={'passed':False,'productionQualified':False,'failureType':type(exc).__name__,'quality':inspect_quality(root/attempt/'run')}
        p=root/attempt/'run/browser-playback-report.json'
        if p.is_file():
            b=json.loads(p.read_text());result['browser']={k:b[k] for k in ('passed','stage','failureType','coverageFraction','accessStatuses') if k in b}
        p=root/attempt/'run/live-report.json'
        if p.is_file():
            n=json.loads(p.read_text());result['native']={k:n[k] for k in ('status','failureType','checks','nativeClock','captureFailure') if k in n}
        return result
    finally:
        descriptor.unlink(missing_ok=True);http.shutdown();http.server_close();thread.join(timeout=5)
        server.LIVE_MATCHES.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('runtime',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix='tribun-native-e2e-') as t:result=run(a.runtime.resolve(),Path(t)/'private')
    except Exception as exc:result={'passed':False,'productionQualified':False,'failureType':type(exc).__name__}
    from native_release_gate import stamp
    result=stamp(result,a.runtime.resolve(),'league-e2e')
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
