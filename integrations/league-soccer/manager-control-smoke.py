"""Submit actual commands after a native trace starts, then verify engine acknowledgements."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("control",HERE/"manager-control.py")
control=importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)

def run(runtime,fixture,output):
    output=Path(output).resolve()
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="tribun-control-") as mailbox:
        env={**os.environ,"TRIBUN_LEAGUE_SOCCER_COMMAND_DIR":mailbox}
        process=subprocess.Popen(["bash",str(HERE/"run-frozen.sh"),runtime,fixture,str(output)],env=env,start_new_session=True)
        deadline=time.monotonic()+800
        submitted=False
        second=False
        try:
            # Watch only complete appended records; don't block native process.
            seen=[]
            offset=0
            while process.poll() is None:
                if time.monotonic()>deadline:
                    raise TimeoutError("Native live control test timeout")
                if output.exists():
                    with output.open("rb") as f:
                        f.seek(offset)
                        while True:
                            line=f.readline()
                            if not line.endswith(b"\n"): break
                            offset=f.tell()
                            frame=json.loads(line)
                            seen.append(frame)
                    if seen and not submitted and not seen[-1]["done"]:
                        control.publish(mailbox,0,1,600000,91,82,73,64)
                        control.publish(mailbox,1,1,600000,21,32,43,54)
                        submitted=True
                    if submitted and not second and seen and seen[-1]["managerTactics"][0]["revision"]==1:
                        control.publish(mailbox,0,2,1800000,45,35,25,15)
                        second=True
                time.sleep(.05)
            if process.returncode:raise RuntimeError("Native test process failed")
            frames=[json.loads(line) for line in output.read_text().splitlines()]
            assert submitted and second and frames[-1]["done"]
            for team,revision,values,earliest in ((0,1,[91,82,73,64],600000),(1,1,[21,32,43,54],600000),(0,2,[45,35,25,15],1800000)):
                rows=[f["managerTactics"][team] for f in frames if f["managerTactics"][team]["revision"]==revision]
                assert rows and rows[0]["appliedMatchMs"]>=earliest
                assert [rows[0][k] for k in ("press","counter","support","width")]==values
                assert rows[0]["appliedElapsedMs"]>0
            assert frames[0]["managerTactics"][0]["revision"]==0
            for team in (0,1):
                revisions=[f["managerTactics"][team]["revision"] for f in frames]
                assert revisions==sorted(revisions)
            print("Native live control acknowledgements verified",flush=True)
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()

if __name__=="__main__":run(*sys.argv[1:])
