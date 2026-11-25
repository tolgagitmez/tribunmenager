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

def run(runtime,fixture,output,*,fixed_duration=False):
    output=Path(output).resolve()
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="tribun-control-") as mailbox:
        env={**os.environ,"TRIBUN_LEAGUE_SOCCER_COMMAND_DIR":mailbox}
        for key in ("TRIBUN_NATIVE_REALTIME","TRIBUN_NATIVE_CLOCK_SCALE","TRIBUN_NATIVE_QUICK_RESTARTS",
                    "TRIBUN_NATIVE_FIXED_DURATION","TRIBUN_NATIVE_EXPERIMENTAL_SUBSTITUTIONS"):
            env.pop(key,None)
        second_earliest=3600000 if fixed_duration else 1800000
        if fixed_duration:
            env.update(TRIBUN_NATIVE_REALTIME="1",TRIBUN_NATIVE_CLOCK_SCALE="1.0",
                       TRIBUN_NATIVE_FIXED_DURATION="1",TRIBUN_NATIVE_EXPERIMENTAL_SUBSTITUTIONS="1",
                       TRIBUN_LEAGUE_SOCCER_ATTACK="short-match",LP_NUM_THREADS="2",OMP_NUM_THREADS="1")
        fixed_spec=importlib.util.spec_from_file_location("fixed",HERE/"fixed-duration.py")
        fixed=importlib.util.module_from_spec(fixed_spec)
        if fixed_duration:fixed_spec.loader.exec_module(fixed)
        timing=fixed.timing.Timing() if fixed_duration else None
        process=subprocess.Popen(["bash",str(HERE/"run-frozen.sh"),runtime,fixture,str(output)],env=env,start_new_session=True)
        deadline=time.monotonic()+(900 if fixed_duration else 800)
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
                    if output.stat().st_size>100*1024*1024:raise ValueError("Trace size limit")
                    with output.open("rb") as f:
                        f.seek(offset)
                        while True:
                            line=f.readline(262145)
                            if len(line)>262144:raise ValueError('Frame size limit')
                            if not line.endswith(b"\n"): break
                            offset=f.tell()
                            frame=json.loads(line)
                            seen.append(frame)
                            if timing:timing.ingest(frame,time.monotonic())
                    if seen and not submitted and not seen[-1]["done"]:
                        control.publish(mailbox,0,1,600000,91,82,73,64,85,442)
                        control.publish(mailbox,1,1,600000,21,32,43,54,25,0)
                        submitted=True
                    if submitted and not second and seen and seen[-1]["managerTactics"][0]["revision"]==1:
                        control.publish(mailbox,0,2,second_earliest,45,35,25,15,35,4231)
                        second=True
                time.sleep(.05)
            if process.returncode:raise RuntimeError("Native test process failed")
            frames=[json.loads(line) for line in output.read_text().splitlines()]
            assert submitted and second and frames[-1]["done"]
            for team,revision,values,earliest in ((0,1,[91,82,73,64],600000),(1,1,[21,32,43,54],600000),(0,2,[45,35,25,15],second_earliest)):
                rows=[f["managerTactics"][team] for f in frames if f["managerTactics"][team]["revision"]==revision]
                assert rows and rows[0]["appliedMatchMs"]>=earliest
                assert [rows[0][k] for k in ("press","counter","support","width")]==values
                assert rows[0]["appliedElapsedMs"]>0
            for team,revision,tempo,formation in ((0,1,85,442),(1,1,25,0),(0,2,35,4231)):
                frame=next(f for f in frames if f["managerTactics"][team]["revision"]==revision)
                ack=frame["managerTactics"][team]
                assert ack["tempo"]==tempo and ack["formation"]==formation
                if formation:
                    field=[p for p in frame["players"] if p["team"]==team and not p["goalkeeper"]]
                    assert len(field)==10
                    actual=sorted(round(p["formationTarget"][0]*52.5) for p in field)
                    expected=sorted([-25,-28,-28,-25,-1,-5,-5,-1,25,25] if formation==442 else [-25,-28,-28,-25,-9,-9,13,13,13,27])
                    assert actual==expected,(actual,expected)
            assert frames[0]["managerTactics"][0]["revision"]==0
            for team in (0,1):
                revisions=[f["managerTactics"][team]["revision"] for f in frames]
                assert revisions==sorted(revisions)
            print("Native live control acknowledgements verified",flush=True)
            if fixed_duration:
                # A final frame may be appended between the last poll and process exit.
                for frame in frames[len(seen):]:
                    timing.ingest(frame,time.monotonic())
                clock=fixed.verify(frames)
                spec=importlib.util.spec_from_file_location("reserves",HERE/"verify-substitutions.py")
                reserves=importlib.util.module_from_spec(spec);spec.loader.exec_module(reserves)
                manifest=json.loads(Path(str(output)+".fixture.json").read_text())
                reserves.verify(frames,manifest)
                season=json.loads(Path(str(output)+".season.json").read_text())
                if len(season["substitutions"])!=2 or not all(c["performed"] for c in season["substitutions"]):
                    raise ValueError("Missing season substitution confirmation")
                if season["score"]!=frames[-1]["score"] or season.get("authoritative") is not False:
                    raise ValueError("Season identity mismatch")
                acks=verify_fixed_controls(frames)
                result={**timing.report(),**clock,"authoritative":False,"substitutions":season["substitutions"],
                        "acknowledgements":acks,"wallClockExact":timing.report()["observedWallMs"]==300000,
                        "note":"Observed mailbox acknowledgements; not HTTP/concurrent or production certification."}
                Path(str(output)+".combined.json").write_text(json.dumps(result,indent=2)+"\n")
                print(json.dumps(result),flush=True)
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()

def verify_fixed_controls(frames):
    # Each command must have been applied during the appropriate half, on an open-play
    # tick. The sampled acknowledgement may be recorded slightly after that tick.
    start=next(f["fixedClock"]["startMs"] for f in frames if f["fixedClock"]["started"])
    checks=((0,1,600000,2700000),(1,1,600000,2700000),(0,2,3600000,5400000))
    result=[]
    for team,revision,earliest,limit in checks:
        frame=next((f for f in frames if f["managerTactics"][team]["revision"]==revision),None)
        if frame is None:raise ValueError("Missing fixed-duration acknowledgement")
        ack=frame["managerTactics"][team]
        nominal=ack["appliedMatchMs"]
        if not earliest<=nominal<limit or nominal!=(ack["appliedElapsedMs"]-start)*18:
            raise ValueError("Acknowledgement outside intended fixed-clock period")
        if ack["appliedElapsedMs"]>frame["elapsedMs"]:
            raise ValueError("Future acknowledgement")
        result.append({"team":team,**ack})
    return result

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("runtime");parser.add_argument("fixture");parser.add_argument("output")
    parser.add_argument("--fixed-duration",action="store_true")
    args=parser.parse_args()
    run(args.runtime,args.fixture,args.output,fixed_duration=args.fixed_duration)
