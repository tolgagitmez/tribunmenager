"""Verify an argument-free original game startup on a fresh isolated Xvfb.
This only proves native window startup, not full default-speed match or GPU FPS.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import original_engine as e


def verify():
    env=e.clean_env(os.environ)
    work=e.cache_root()/e.REVISION
    build=e.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='native-default-start-') as tmp:
        session=Path(tmp)
        for name in e.RUNTIME:
            source=build/name
            if source.is_dir():
                shutil.copytree(source,session/name)
            else:
                shutil.copy2(source,session/name)
        e.check_config(work/'source',session)
        args=[str(session/'gameplayfootball')]
        with tempfile.TemporaryFile() as log:
            game=subprocess.Popen(args,env=env,cwd=session,stdout=log,stderr=subprocess.STDOUT)
            info=''
            try:
                deadline=time.monotonic()+60
                while time.monotonic()<deadline and game.poll() is None:
                    p=subprocess.run(['xwininfo','-name','League Soccer'],env=env,capture_output=True,text=True,timeout=5)
                    if p.returncode==0 and 'Map State: IsViewable' in p.stdout:
                        info=p.stdout
                        break
                    time.sleep(.25)
                if not info:
                    log.seek(0)
                    raise RuntimeError('Default native window did not appear: '+log.read(4096).decode(errors='replace'))
                time.sleep(2)
                if game.poll() is not None:
                    raise RuntimeError('Native game exited after startup')
                print(json.dumps(dict(revision=e.REVISION,normalStartup=True,commandArgumentCount=0,
                    sourceConfigVerified=True,windowViewable=True,windowInfo=info,
                    fullDefaultMatchVerified=False,gpuPerformanceVerified=False,
                    termination='external CI cleanup'),indent=2))
            finally:
                if game.poll() is None:
                    game.terminate()
                    try:
                        game.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        game.kill();game.wait()
    e.verify_install(work,env)


if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='--private-test-display':
        verify()
    else:
        e.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                sys.executable,Path(__file__).resolve(),'--private-test-display'],e.clean_env(os.environ))
