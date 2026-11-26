"""Measured native timing calibration. Never promotes a profile or edits league state."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

HERE=Path(__file__).resolve().parent
PROFILES=(("baseline","1.0","0"),("quick-restarts","1.0","1"),("quick-scale125","1.25","1"))

class Timing:
    def __init__(self):
        self.previous=None
        self.first=None
        self.final=None
        self.first_wall=None
        self.final_wall=None
        self.open_ms=0
        self.restart_ms=0
        self.dead_ms=0
        self.transition_ms=0
        self.gap_ms=0
        self.frames=0
        self.previous_wall=None
        self.max_observed_gap_ms=0
    def ingest(self,frame,now):
        if self.final is not None:
            raise ValueError("Frame after full time")
        if frame.get("engine")!="league-soccer" or frame.get("schema")!=1:
            raise ValueError("Wrong native trace")
        if any(type(frame.get(k)) is not bool for k in ("inPlay","setPiece","done")):
            raise ValueError("Missing play-state telemetry")
        if frame["inPlay"] and frame["setPiece"]:
            raise ValueError("Conflicting play states")
        if type(frame.get("elapsedMs")) is not int or frame["elapsedMs"]<0:
            raise ValueError("Invalid native clock")
        if self.previous and frame["elapsedMs"]<self.previous["elapsedMs"]:
            raise ValueError("Regressing clock")
        self.frames+=1
        if self.first is not None and self.previous_wall is not None:
            self.max_observed_gap_ms=max(self.max_observed_gap_ms,round((now-self.previous_wall)*1000))
        self.previous_wall=now
        if self.first is None and frame["inPlay"] and not frame["done"]:
            self.first=frame["elapsedMs"]
            self.first_wall=now
        if self.first is not None and self.previous and self.previous["elapsedMs"]>=self.first:
            dt=frame["elapsedMs"]-self.previous["elapsedMs"]
            if dt>250:
                self.gap_ms+=dt
            elif self.previous["phaseCode"]!=frame["phaseCode"] or any(self.previous[k]!=frame[k] for k in ("inPlay","setPiece")):
                self.transition_ms+=dt
            elif frame["inPlay"]:
                self.open_ms+=dt
            elif frame["setPiece"]:
                self.restart_ms+=dt
            else:
                self.dead_ms+=dt
        if frame["done"]:
            if self.first is None or frame.get("matchMs",0)<5400000:
                raise ValueError("Incomplete regulation match")
            self.final=frame["elapsedMs"]
            self.final_wall=now
        self.previous=frame
    def report(self):
        if self.final is None or self.first is None:
            raise ValueError("Missing observed full time")
        native=self.final-self.first
        wall=round((self.final_wall-self.first_wall)*1000)
        if native<=0 or wall<0:
            raise ValueError("Invalid match duration")
        if self.open_ms+self.restart_ms+self.dead_ms+self.transition_ms+self.gap_ms!=native:
            raise ValueError("Unaccounted timing interval")
        return dict(observedWallMs=wall,targetMs=300000,deviationMs=wall-300000,
                    nativeElapsedMs=native,openPlayMs=self.open_ms,setPieceMs=self.restart_ms,
                    deadBallMs=self.dead_ms,transitionMs=self.transition_ms,gapMs=self.gap_ms,
                    frames=self.frames,maxObservedGapMs=self.max_observed_gap_ms,withinFiveSeconds=abs(wall-300000)<=5000)

def run(runtime,fixture,out,profile,attack_profile='baseline',fixed_duration=False,retention=False,box_runs=False,timed_attack=False,render_threads=2):
    name,scale,quick=profile
    if type(render_threads) is not int or render_threads not in (1,2,3,4):raise ValueError("Invalid software renderer thread limit")
    if attack_profile not in ("baseline","short-match"):raise ValueError("Unknown attack profile")
    trace=Path(str(out)+"."+name+".ndjson").resolve()
    trace.unlink(missing_ok=True)
    env={**os.environ,"TRIBUN_NATIVE_REALTIME":"1","TRIBUN_NATIVE_CLOCK_SCALE":scale,
         "TRIBUN_NATIVE_QUICK_RESTARTS":quick,"TRIBUN_LEAGUE_SOCCER_ATTACK":attack_profile,
         "LP_NUM_THREADS":str(render_threads),"OMP_NUM_THREADS":"1"}
    env["TRIBUN_NATIVE_FIXED_DURATION"]="1" if fixed_duration else "0"
    env["TRIBUN_NATIVE_FINAL_THIRD_RETENTION"]="1" if retention else "0"
    env["TRIBUN_NATIVE_BOX_LANE_RUNS"]="1" if box_runs else "0"
    env["TRIBUN_NATIVE_TIMED_ATTACK"]="1" if timed_attack else "0"
    if (retention or box_runs or timed_attack) and (attack_profile!="short-match" or not fixed_duration):
        raise ValueError("Attack diagnostic requires fixed-clock short-match")
    if sum((retention,box_runs,timed_attack))>1:
        raise ValueError("Isolate one experimental policy at a time")
    for k in ("TRIBUN_LEAGUE_SOCCER_COMMAND_DIR","TRIBUN_NATIVE_EXPERIMENTAL_SUBSTITUTIONS"):
        env.pop(k,None)
    stats=Timing()
    offset=0
    def drain():
        nonlocal offset
        if not trace.exists():return
        if trace.stat().st_size>100*1024*1024:raise RuntimeError("Trace size limit")
        with trace.open("rb") as handle:
            handle.seek(offset)
            while True:
                line=handle.readline(262145)
                if len(line)>262144:raise RuntimeError("Frame size limit")
                if not line.endswith(b"\n"):break
                stats.ingest(json.loads(line),time.monotonic())
                offset=handle.tell()
    resources=Path(str(trace)+".resources.json")
    resources.unlink(missing_ok=True)
    command=["bash",str(HERE/"run-frozen.sh"),runtime,fixture,str(trace)]
    if Path("/usr/bin/time").is_file():
        command=["/usr/bin/time","-o",str(resources),"-f",
                 '{"userSeconds":%U,"systemSeconds":%S,"maxRssKiB":%M,"elapsedSeconds":%e}',*command]
    launch=time.monotonic()
    with Path(str(trace)+".log").open("wb") as log:
        process=subprocess.Popen(command,
                                 env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+900
        try:
            while process.poll() is None:
                drain()
                if time.monotonic()>deadline:raise TimeoutError("Timing pilot timeout")
                time.sleep(.1)
            drain()
            if process.returncode:raise RuntimeError("Native runner failed; see "+str(trace)+".log")
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
    report=stats.report()
    report.update(processWallMs=round((time.monotonic()-launch)*1000),
                  firstObservedMonotonic=stats.first_wall,finalObservedMonotonic=stats.final_wall,
                  traceBytes=trace.stat().st_size,resources=None)
    if resources.exists():
        import math
        r=json.loads(resources.read_text())
        if set(r)!={"userSeconds","systemSeconds","maxRssKiB","elapsedSeconds"} or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in r.values()):
            raise ValueError("Invalid process resource measurement")
        report["resources"]=r
    attack=json.loads(Path(str(trace)+".attack.json").read_text())
    if attack["engine"]!="league-soccer" or not attack.get("sampled"):raise ValueError("Missing attack report")
    report.update(profile=name,attackProfile=attack_profile,softwareRenderThreads=render_threads,retention=retention,boxRuns=box_runs,timedAttack=timed_attack,scale=float(scale),quickRestarts=quick=="1",
                  score=attack["score"],shots=attack["shots"],onTarget=attack["onTarget"],
                  controlledBoxCrossings=attack["sampled"]["controlledBoxCrossings"])
    Path(str(trace)+".timing.json").write_text(json.dumps(report,indent=2)+"\n")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime")
    p.add_argument("fixture")
    p.add_argument("out")
    args=p.parse_args()
    results=[]
    for profile in PROFILES:
        results.append(run(args.runtime,args.fixture,args.out,profile))
        Path(args.out+".timing.json").write_text(json.dumps({"schema":1,"authoritative":False,
             "targetMs":300000,"profiles":results,"note":"Single fixture per profile; no rollout or guaranteed duration."},indent=2)+"\n")
        print(json.dumps(results[-1]),flush=True)

if __name__=="__main__":main()
