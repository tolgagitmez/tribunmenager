"""Test genuine native-window preview in Chromium on a fresh private Xvfb.
The upstream accelerated smoke fixture is test-only. Production capture still
requires user consent; no native files, configuration, or gameplay are patched.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import original_engine as e

ACTIVE='[menu-smoke] Gameplay page reached and live match is active'
HALF='[menu-smoke] Continuing second half automatically'
FULL='[menu-smoke] Full match complete:'
DONE='[menu-smoke] Full-match verification succeeded, quitting test run'
ROOT=Path(__file__).resolve().parent


def terminate(process):
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run():
    env=e.clean_env(os.environ)
    if not env.get('DISPLAY','').startswith(':'):
        raise RuntimeError('Private Xvfb required')
    work=e.cache_root()/e.REVISION
    build=e.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='native-browser-test-') as tmp:
        session=Path(tmp)
        for name in e.RUNTIME:
            p=build/name
            if p.is_dir():
                shutil.copytree(p,session/name)
            else:
                shutil.copy2(p,session/name)
        e.check_config(work/'source',session)
        manager=server=game=None
        events=[]
        with tempfile.TemporaryFile() as game_log, tempfile.TemporaryFile() as other_log:
            try:
                manager=subprocess.Popen(['openbox'],env=env,stdout=other_log,stderr=other_log)
                time.sleep(1)
                if manager.poll() is not None:
                    raise RuntimeError('Private window manager did not start')
                server=subprocess.Popen([sys.executable,str(ROOT/'start.py'),'--port','8765'],
                    cwd=ROOT,env=env,stdout=other_log,stderr=other_log)
                for _ in range(40):
                    if server.poll() is not None:
                        raise RuntimeError('Private test server exited')
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:8765/api/health',timeout=1) as response:
                            if response.status==200:
                                break
                    except OSError:
                        time.sleep(.25)
                else:
                    raise RuntimeError('Private test server unavailable')
                game=subprocess.Popen(['stdbuf','-oL','-eL',str(session/'gameplayfootball'),
                    str(work/'source/data/menu_smoke_full_match.config')],env=env,cwd=session,
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
                def read_game():
                    for line in game.stdout:
                        game_log.write(line.encode())
                        for marker in (ACTIVE,HALF,FULL,DONE):
                            if marker in line:
                                events.append((int(time.time()*1000),marker,line.strip()))
                logger=threading.Thread(target=read_game,daemon=True)
                logger.start()
                deadline=time.monotonic()+120
                while not any(marker==ACTIVE for _,marker,_ in events):
                    if game.poll() is not None or time.monotonic()>=deadline:
                        raise RuntimeError('Original game did not reach active match')
                    time.sleep(.1)
                browser_env=dict(env,TRIBUN_PRIVATE_NATIVE_TEST='1')
                browser=subprocess.run(['node',str(ROOT/'tests/original-native-window-browser.cjs')],
                    env=browser_env,cwd=ROOT,capture_output=True,text=True,timeout=65)
                print(browser.stdout,flush=True)
                if browser.returncode:
                    raise RuntimeError('Real native window preview test failed: '+browser.stderr)
                lines=[line for line in browser.stdout.splitlines() if line.startswith('NATIVE_BROWSER_RESULT ')]
                if len(lines)!=1:
                    raise RuntimeError('Missing browser observation')
                result=json.loads(lines[0].split(' ',1)[1])
                code=game.wait(timeout=420)
                logger.join(timeout=10)
                if code or logger.is_alive() or [m for _,m,_ in events]!=[ACTIVE,HALF,ACTIVE,FULL,DONE]:
                    raise RuntimeError('Original smoke fixture did not complete normally')
                intervals=[(events[0][0],events[1][0]),(events[2][0],events[3][0])]
                overlap=sum(max(0,min(b,result['endMs'])-max(a,result['startMs'])) for a,b in intervals)
                if overlap<4000:
                    raise RuntimeError('Less than four seconds of active match overlapped browser capture')
                result.update(nativeWindowBrowserVerified=True,syntheticStream=False,
                    activeMatchOverlapMs=overlap,revision=e.REVISION,
                    fullTime=events[3][2],testOnlyAutoSelection=True,
                    hardwareFpsVerified=False,defaultSpeedMatchVerified=False)
                print(json.dumps(result,indent=2),flush=True)
            except Exception:
                game_log.seek(0)
                print(game_log.read()[-6000:].decode(errors='replace'),file=sys.stderr)
                other_log.seek(0)
                print(other_log.read()[-3000:].decode(errors='replace'),file=sys.stderr)
                raise
            finally:
                terminate(game)
                terminate(server)
                terminate(manager)
    e.verify_install(work,env)


if __name__=='__main__':
    if sys.argv[1:]==['--inside-private-display']:
        run()
    else:
        e.call(['xvfb-run','-a','-s','-screen 0 1600x1000x24 -nolisten tcp',
                sys.executable,Path(__file__).resolve(),'--inside-private-display'],
               e.clean_env(os.environ))
