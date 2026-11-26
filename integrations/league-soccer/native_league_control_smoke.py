"""One real native match controlled through the actual league HTTP handler.
Disposable accounts/database; no scheduler or official settlement. No private URL output.
"""
import argparse
from contextlib import closing
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
import server
import native_av_queue as q

class QuietHandler(server.Handler):
    def log_message(self,*args):pass

def request(base,token,body=None,expected=200):
    url=base+'/api/league/native-av/tactics'+('' if body is not None else '?round=3')
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(url,data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as r:
            if r.status!=expected:raise ValueError('Unexpected gateway status')
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code!=expected:raise RuntimeError('Unexpected gateway rejection: '+str(e.code)) from None
        return {}

def until(fn,seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        r=fn()
        if r:return r
        time.sleep(.25)
    raise TimeoutError('Gateway evidence deadline')

def run(runtime,root,fixture):
    root.mkdir(mode=0o700,parents=True,exist_ok=False)
    config=json.loads(fixture.read_text())
    accounts=[secrets.token_urlsafe(26) for _ in range(3)]
    server.DATA=root/'league.sqlite3'
    os.environ['TRIBUN_NATIVE_AV_GATEWAY_ROOT']=str(root)
    with closing(sqlite3.connect(server.DATA)) as db,db:
        db.executescript("""CREATE TABLE teams(league,slot,token);
        CREATE TABLE fixtures(league,round,home,away,kickoff,home_score);
        CREATE TABLE live_matches(league,round,home,away,kickoff,config);"""+q.SCHEMA)
        for slot,token in enumerate(accounts):db.execute('INSERT INTO teams VALUES(?,?,?)',('L' if slot<2 else 'X',slot,token))
        key=('L',3,0,1)
        db.execute('INSERT INTO fixtures VALUES(?,?,?,?,?,NULL)',(*key,time.time()-1))
        db.execute('INSERT INTO live_matches VALUES(?,?,?,?,?,?)',(*key,time.time()-1,q.canonical(config)))
        q.sync(db,time.time())
    job=q.claim(server.DATA,1)
    if not job:raise RuntimeError('Reservation failed')
    key,sha,_,attempt=job
    out=root/attempt;out.mkdir(mode=0o700);f=out/'fixture.json';f.write_text(q.canonical(config))
    http=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(http.server_port)
    env={k:v for k,v in os.environ.items() if not k.startswith(('TRIBUN_AV_','TRIBUN_GPU_','TRIBUN_EXPECT_'))}
    env.update(TRIBUN_EXPECT_AUDIO='1',TRIBUN_EXPECT_CONTROL='0',TRIBUN_EXPECT_FULL_PLAYBACK='1',TRIBUN_PLAYBACK_MIN_SECONDS='300',TRIBUN_AV_FILTER_THREADS='1')
    children=[]
    try:
        with (out/'native.log').open('wb') as n,(out/'browser.log').open('wb') as b:
            native=subprocess.Popen(['python3',str(HERE/'native-live-video.py'),str(runtime),str(f),str(out/'run'),'--audio','--interactive','--league-control','--linger','60'],env=env,stdout=n,stderr=subprocess.STDOUT)
            children.append(native)
            browser=subprocess.Popen(['node',str(HERE/'native-live-video-browser.cjs'),str(out/'run/local-url.txt')],env=env,stdout=b,stderr=subprocess.STDOUT,start_new_session=True)
            children.append(browser)
            request(base,'invalid',expected=403)
            request(base,accounts[2],expected=403)
            until(lambda:(out/'run/local-manager-0.txt').is_file() and (out/'run/league-gateway.key').is_file(),120)
            direct=(out/'run/local-manager-0.txt').read_text().strip()+'tactics.json'
            try:
                urllib.request.urlopen(direct,timeout=4).close()
                raise ValueError('Direct capability bypassed league control')
            except urllib.error.HTTPError as e:
                if e.code!=403:raise
            def eligible(token):
                if native.poll() is not None:raise RuntimeError('Native process stopped')
                try:r=request(base,token)
                except RuntimeError:return None
                return r if r.get('canControl') else None
            acknowledgements=[]
            for side,token in enumerate(accounts[:2]):
                state=until(lambda:eligible(token),100)
                if state['side']!=side or state['submittedRevision']!=0:raise ValueError('Unexpected manager state')
                body={'round':3,'requestId':'league-control-'+str(side),'tactics':dict(press=75 if side==0 else 35,counter=50,support=50,width=50,tempo=80 if side==0 else 40,formation=442 if side==0 else 4231)}
                # Cross-league authenticated rejection on actual HTTP POST.
                request(base,accounts[2],body,403)
                reply=request(base,token,body,202)
                if reply.get('revision')!=1 or request(base,token,body,202)!=reply:raise ValueError('Duplicate command mismatch')
                def applied():
                    r=request(base,token)
                    return r if r.get('appliedRevision')==1 else None
                ack=until(applied,90)['lastAcknowledgement']
                if any(ack.get(k)!=v for k,v in body['tactics'].items()):raise ValueError('Engine acknowledgement mismatch')
                acknowledgements.append({'side':side,'revision':ack['revision'],'formation':ack['formation']})
            until(lambda:all(p.poll() is not None for p in children),1000)
            if any(p.returncode for p in children):raise RuntimeError('Native or browser failed')
        report=q.verify_recording(f,out/'run',sha,control_source='league-gateway')
        # This evidence is still private; official scores never changed.
        if not q.finish(server.DATA,key,sha,attempt,report=report):raise ValueError('Private completion failed')
        with closing(sqlite3.connect(server.DATA)) as db:
            if db.execute('SELECT home_score FROM fixtures').fetchone()[0] is not None:raise ValueError('Official score changed')
        return {'passed':True,'authoritative':False,'acknowledgements':acknowledgements,'invalidTokenRejected':True,'foreignLeagueRejected':True,'directCapabilityRejected':True,'idempotent':True,'score':report['score'],'productionQualified':False}
    finally:
        http.shutdown();http.server_close();thread.join(timeout=5)
        for i,p in enumerate(children):
            if p.poll() is None:
                if i:os.killpg(p.pid,signal.SIGTERM)
                else:p.terminate()
            try:p.wait(timeout=30)
            except subprocess.TimeoutExpired:p.kill();p.wait()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path);p.add_argument('fixture',type=Path);p.add_argument('report',type=Path)
    a=p.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix='tribun-league-control-') as t:result=run(a.runtime.resolve(),Path(t)/'private',a.fixture.resolve())
    except Exception as exc:
        result={'passed':False,'failureType':type(exc).__name__,'productionQualified':False}
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
