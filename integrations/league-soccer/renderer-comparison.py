"""Original OpenGL framebuffer vs browser replay: visual evidence, not FPS."""
import argparse,bisect,json,os,signal,struct,subprocess,time
from pathlib import Path
from release_evidence import stamp,sha
from validate_trace import validate
HERE=Path(__file__).resolve().parent
TARGETS=(15,45,75)
MAX_GAP_NS=750_000_000
def capture_env(source,directory):
    env={k:v for k,v in source.items() if not k.startswith(("TRIBUN_NATIVE_","TRIBUN_LEAGUE_SOCCER_","GF_CAPTURE_"))}
    env.update(TRIBUN_LEAGUE_SOCCER_ATTACK="baseline",GF_CAPTURE_DIRECTORY=str(directory.resolve()),
        GF_CAPTURE_INTERVAL_MS="2000",GF_CAPTURE_LIMIT="180",LIBGL_ALWAYS_SOFTWARE="1",SDL_AUDIODRIVER="dummy",LP_NUM_THREADS="2")
    env.pop("SDL_VIDEODRIVER",None)
    return env
def png_size(path):
    with path.open("rb") as f:head=f.read(24)
    if len(head)!=24 or head[:8]!=b"\x89PNG\r\n\x1a\n" or head[12:16]!=b"IHDR":raise ValueError("Invalid framebuffer PNG")
    w,h=struct.unpack(">II",head[16:24])
    if not 64<=w<=7680 or not 64<=h<=4320:raise ValueError("Invalid image dimensions")
    return [w,h]
def pair(captures,observations,start):
    # Timestamp at complete trace-line observation vs PNG write mtime.
    # This bounds observational proximity, not GPU/physics synchronization.
    observations=sorted(observations,key=lambda o:o[0])
    times=[o[0] for o in observations];candidates=[]
    for cap in captures:
        j=bisect.bisect_left(times,cap["mtimeNs"])
        choices=[i for i in (j-1,j) if 0<=i<len(times)]
        if not choices:continue
        i=min(choices,key=lambda i:abs(times[i]-cap["mtimeNs"]))
        observed,frame=observations[i];gap=abs(observed-cap["mtimeNs"])
        if gap>MAX_GAP_NS or frame.get("done") or frame.get("inPlay") is not True or frame.get("setPiece") or len(frame.get("players",[]))!=22:continue
        elapsed=frame["elapsedMs"]-start
        if elapsed<0:continue
        candidates.append({**cap,"elapsedMs":elapsed,"matchMs":frame["matchMs"],"score":frame["score"],"observationGapMs":round(gap/1e6,2)})
    selected=[]
    for minute in TARGETS:
        valid=[c for c in candidates if abs(c["matchMs"]/60000-minute)<=12 and c not in selected]
        if valid:selected.append(min(valid,key=lambda c:abs(c["matchMs"]/60000-minute)))
    return selected
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("runtime",type=Path);p.add_argument("fixture",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();runtime=a.runtime.resolve();fixture=a.fixture.resolve();out=a.out.resolve()
    out.mkdir(parents=True,exist_ok=False);native=out/"native";native.mkdir()
    trace=out/"match.ndjson";log=out/"native.log";offset=0;start=None;observations=[]
    report=stamp({"schema":1,"authoritative":False,"productionEnabled":False,"status":"incomplete",
        "fixtureSha256":sha(fixture),"mode":"baseline-native-opengl","note":"Same recorded match, approximate time correspondence, not pixel-synchronized. Software rendering and synchronous PNG capture invalidate FPS comparison. Manual visual and asset-license review required."},runtime,"renderer-comparison")
    def save():
        (out/"comparison.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    save()
    def drain():
        nonlocal offset,start
        if not trace.is_file():return
        if trace.stat().st_size>100*1024*1024:raise ValueError("Trace too large")
        with trace.open("rb") as f:
            f.seek(offset)
            latest=None
            while True:
                line=f.readline(262145)
                if len(line)>262144:raise ValueError("Frame too large")
                if not line.endswith(b"\n"):break
                latest=json.loads(line)
                if start is None:start=latest["elapsedMs"]
                offset=f.tell()
            # Do not attach one observation time to a backlog of old frames.
            if latest is not None:observations.append((time.time_ns(),latest))
    cmd=["bash",str(HERE/"run-frozen.sh"),str(runtime),str(fixture),str(trace),"0"]
    with log.open("wb") as f:
        proc=subprocess.Popen(cmd,env=capture_env(os.environ,native),stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+460
        try:
            while proc.poll() is None:
                drain()
                if time.monotonic()>deadline:raise TimeoutError("Native screenshot run exceeded limit")
                time.sleep(.075)
            drain()
            if proc.returncode:raise RuntimeError("Native OpenGL run failed; see native.log")
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    validate(trace)
    captures=[]
    for path in native.glob("frame-*.png"):
        captures.append({"nativeImage":str(path.relative_to(out)),"mtimeNs":path.stat().st_mtime_ns,"size":png_size(path),"sha256":sha(path)})
    if start is None or not captures:raise RuntimeError("No native framebuffer/trace")
    selected=pair(captures,observations,start)
    report.update(traceSha256=sha(trace),manifestSha256=sha(Path(str(trace)+".fixture.json")),
        captureCount=len(captures),observedFrames=len(observations),pairs=selected,status="native-captured" if len(selected)==len(TARGETS) else "insufficient-pairs")
    save()
    if report["status"]!="native-captured":raise SystemExit("Insufficient open-play capture pairs; inspect evidence, do not infer renderer quality")
    print(json.dumps({"captures":len(captures),"pairs":selected},indent=2))
if __name__=="__main__":main()
