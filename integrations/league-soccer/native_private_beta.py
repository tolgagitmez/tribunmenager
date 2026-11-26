"""One manually observed, private native diagnostic fixture; NOT a beta release."""
import argparse
from contextlib import closing
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import threading
import time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
import server
import native_av_queue as q
from native_av_scheduler import lock_host
from native_scheduler_policy import sample,pressure_ok
from live_match import Registry

def private_new(root):
    root=root.resolve()
    if root.is_relative_to(server.ROOT.resolve()):raise ValueError('Test directory must be outside source/static root')
    root.mkdir(mode=0o700,parents=False,exist_ok=False)
    return root

def prepare(runtime,root):
    if not sys.platform.startswith('linux'):raise ValueError('Linux diagnostic host required')
    for program in ('node','ffmpeg','ffprobe','xvfb-run','xauth','pulseaudio','pactl','xdotool'):
        if not shutil.which(program):raise ValueError('Missing prerequisite: '+program)
    for path in ('gameplayfootball','tribun-runtime.json','native-match.config'):
        if not (runtime/path).is_file():raise ValueError('Missing runtime file: '+path)
    manifest=json.loads((runtime/'tribun-runtime.json').read_text())
    if manifest.get('upstream')!=json.loads((HERE/'upstream.json').read_text()):raise ValueError('Wrong upstream revision')
    return private_new(root)

def run(runtime,root,port,delay):
    root=prepare(runtime,root)
    lock=lock_host()
    try:
        os.environ.update(TRIBUN_NATIVE_ONLY_LEAGUE='1',TRIBUN_NATIVE_AV_QUEUE='0',
            TRIBUN_NATIVE_SHADOW='0',TRIBUN_NATIVE_PRIVATE_SCREEN='1',TRIBUN_NATIVE_AV_GATEWAY_ROOT=str(root))
        server.DATA=root/'league.sqlite3'
        server.TRANSFERS_ENABLED=False
        server.LIVE_MATCHES=Registry()
        server.init_db()
        account=server.new_league('Yerel Deneme Menajeri',native=True)
        now=time.time()
        kickoff=now+delay
        with closing(server.db()) as db,db:
            db.execute('UPDATE fixtures SET kickoff=? WHERE league=? AND round=0',(kickoff,account['code']))
        token_path=root/'manager-session.txt'
        fd=os.open(token_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:f.write(account['token']+'\n')
        with ThreadingHTTPServer(('127.0.0.1',port),server.Handler) as http:
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            try:
                print('Yerel özel deneme: http://127.0.0.1:'+str(http.server_port)+'/native-beta-login.html',flush=True)
                print('Oturum anahtarını yalnızca yerel giriş formuna yapıştır: '+str(token_path),flush=True)
                print('Tek karşılaşma, başlangıç gecikmesi '+str(delay)+' saniye. Diğer iki karşılaşma başlatılmaz.',flush=True)
                while time.time()<kickoff:time.sleep(.25)
                server.settle_due()
                if not pressure_ok(sample(root)):raise RuntimeError('Host pressure too high; no diagnostic started')
                job=q.claim(server.DATA,1,managed=True)
                if not job:raise RuntimeError('No diagnostic reservation')
                key,sha,_,attempt=job
                if key[0]!=account['code'] or key[2]!=0:raise RuntimeError('Wrong fixture')
                try:
                    report=q.run_match(runtime,root,job,database=server.DATA)
                    if not q.finish(server.DATA,key,sha,attempt,report=report):raise RuntimeError('Completion rejected')
                    result={'passed':True,'score':report['score'],'coverage':report['coverage'],'commandHistory':report['commandHistory'],'productionQualified':False}
                except BaseException as exc:
                    q.finish(server.DATA,key,sha,attempt,error=type(exc).__name__)
                    if not isinstance(exc,Exception):raise
                    result={'passed':False,'failureType':type(exc).__name__,'productionQualified':False}
                (root/'private-beta-report.json').write_text(json.dumps(result,indent=2)+'\n')
                print(json.dumps(result,ensure_ascii=False),flush=True)
                print('Lig ekranını kontrol et. Sunucu 30 saniye sonra kapanır.',flush=True)
                time.sleep(30)
                return 0 if result['passed'] else 1
            finally:http.shutdown();thread.join(timeout=5);server.LIVE_MATCHES.close()
    finally:os.close(lock)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runtime',type=Path);p.add_argument('new_private_directory',type=Path)
    p.add_argument('--port',type=int,default=8000);p.add_argument('--delay',type=int,default=60)
    p.add_argument('--private-diagnostic',action='store_true')
    a=p.parse_args()
    if not a.private_diagnostic:p.error('Explicit private diagnostic opt-in required')
    if not 1<=a.port<=65535 or not 30<=a.delay<=300:p.error('Invalid port or delay')
    return run(a.runtime.resolve(),a.new_private_directory,a.port,a.delay)
if __name__=='__main__':raise SystemExit(main())
