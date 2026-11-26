"""Private diagnostic: original native game window -> local MP4, no WebGL reconstruction."""
import argparse,hashlib,importlib.util,json,math,os,signal,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
def require(ok,message):
    if not ok:raise ValueError(message)
def save(path,data):
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+"\n")
def env_for(source,video):
    env={k:v for k,v in source.items() if not k.startswith(("TRIBUN_NATIVE_","TRIBUN_LEAGUE_SOCCER_","GF_CAPTURE_"))}
    env.update(TRIBUN_NATIVE_VIDEO_OUT=str(video.resolve()),TRIBUN_NATIVE_REALTIME="1",
      TRIBUN_NATIVE_FIXED_DURATION="1",TRIBUN_NATIVE_CLOCK_SCALE="1.0",TRIBUN_LEAGUE_SOCCER_ATTACK="baseline",
      LIBGL_ALWAYS_SOFTWARE="1",SDL_AUDIODRIVER="dummy",LP_NUM_THREADS="2")
    env.pop("SDL_VIDEODRIVER",None)
    return env
def stop(proc):
    if proc is None or proc.poll() is not None:return
    proc.send_signal(signal.SIGINT)
    try:proc.wait(timeout=15)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
def measure(video):
    info=json.loads(subprocess.check_output(["ffprobe","-v","error","-count_packets","-select_streams","v:0",
      "-show_entries","stream=codec_name,width,height,nb_read_packets,duration,avg_frame_rate:format=duration","-of","json",str(video)]))
    s=info["streams"][0]
    duration=float(s.get("duration") or info["format"]["duration"]);packets=int(s["nb_read_packets"])
    require(math.isfinite(duration) and 0<duration<=900 and s["codec_name"]=="h264" and 64<=s["width"]<=1920 and 64<=s["height"]<=1080 and packets>0,"Invalid captured video")
    return {"codec":s["codec_name"],"width":s["width"],"height":s["height"],"durationSeconds":duration,"packets":packets,"averageEncodedPacketsPerSecond":packets/duration}
def assess(capture,video):
    first,kickoff,final=(capture.get(k) for k in ("firstEncodedObserved","kickoffObserved","finalObserved"))
    observed=all(type(v) in (int,float) and math.isfinite(v) for v in (first,kickoff,final))
    wall=(final-kickoff) if observed else None
    return {"captureBeforeKickoff":bool(observed and first<=kickoff),"observedWallSeconds":wall,
       "wallWithinOneSecond":bool(observed and abs(wall-300)<=1),
       "videoLengthAtLeastObservedMatch":bool(observed and video["durationSeconds"]>=wall-1),
       "encodedCadenceAtLeast20":video["averageEncodedPacketsPerSecond"]>=20,
       "note":"Observation clocks and encoded frame cadence are not exact synchronization or unique rendered FPS."}
def capture_window(config,limit):
    video=Path(os.environ["TRIBUN_NATIVE_VIDEO_OUT"]);trace=Path(os.environ["TRIBUN_LEAGUE_SOCCER_TRACE"])
    require(video.is_absolute() and not video.exists() and video.suffix==".mp4","New absolute MP4 path required")
    hls=os.environ.get("TRIBUN_NATIVE_HLS_DIR")
    if hls:
        hls=Path(hls)
        require(hls.is_absolute() and hls.is_dir() and not any(hls.iterdir()),"New empty HLS directory required")
    progress=video.with_suffix(".progress");capture_log=video.with_suffix(".capture.log")
    game_log=video.with_suffix(".game.log");offset=0;first=kickoff=final=None;last=None;encoder=None
    with game_log.open("wb") as g,capture_log.open("wb") as e:
        game=subprocess.Popen(["timeout","--kill-after=10s",str(limit)+"s","./gameplayfootball",config],stdout=g,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+120;window=None
            while time.monotonic()<deadline and game.poll() is None:
                found=subprocess.run(["xdotool","search","--onlyvisible","--name","^League Soccer$"],capture_output=True,text=True)
                if found.returncode==0 and found.stdout.strip():
                    window=found.stdout.splitlines()[0].strip();break
                time.sleep(.1)
            require(window is not None and window.isdigit(),"Native SDL window not found")
            output_args=["-movflags","+faststart",str(video)]
            if hls:
                output_args=["-g","50","-keyint_min","50","-sc_threshold","0","-tune","zerolatency","-profile:v","baseline","-level:v","3.1",
                  "-f","hls","-hls_time","2","-hls_list_size","0","-hls_playlist_type","event","-hls_segment_type","fmp4",
                  "-hls_fmp4_init_filename","init.mp4","-hls_flags","independent_segments+temp_file",
                  "-hls_segment_filename",str(hls/"segment-%05d.m4s"),str(hls/"live.m3u8")]
            encoder=subprocess.Popen(["ffmpeg","-nostdin","-hide_banner","-loglevel","warning","-y","-f","x11grab",
              "-draw_mouse","0","-framerate","25","-window_id",window,"-i",os.environ["DISPLAY"],
              "-an","-vf",("scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2" if hls else "scale=trunc(iw/2)*2:trunc(ih/2)*2"),"-c:v","libx264","-threads","2",
              "-preset","ultrafast","-crf","25","-pix_fmt","yuv420p","-progress",str(progress),*output_args],stdout=e,stderr=subprocess.STDOUT)
            def drain():
                nonlocal offset,kickoff,final,last,first
                if first is None and progress.exists():
                    if any(l.startswith("frame=") and l[6:].strip().isdigit() and int(l[6:])>0 for l in progress.read_text(errors="replace").splitlines()):first=time.monotonic()
                if not trace.exists():return
                require(trace.stat().st_size<=100*1024*1024,"Trace too large")
                with trace.open("rb") as f:
                    f.seek(offset)
                    while True:
                        line=f.readline(262145)
                        require(len(line)<=262144,"Trace frame too large")
                        if not line.endswith(b"\n"):break
                        row=json.loads(line);offset=f.tell();last=row
                        c=row.get("fixedClock",{})
                        if c.get("started") and kickoff is None:kickoff=time.monotonic()
                        if row.get("done") and final is None:final=time.monotonic()
            while game.poll() is None:
                drain()
                if encoder.poll() is not None and final is None:raise RuntimeError("Video encoder stopped before full time")
                time.sleep(.075)
            drain()
            require(game.returncode==0 and last and last.get("done") is True,"Native match did not complete")
        finally:
            stop(encoder);stop(game)
    logs=game_log.read_text(errors="replace");print(logs)
    require("[menu-smoke] Full match complete:" in logs and "[menu-smoke] Full-match verification succeeded, quitting test run" in logs,"Missing native completion markers")
    save(video.with_suffix(".capture.json"),{"firstEncodedObserved":first,"kickoffObserved":kickoff,"finalObserved":final,"windowId":window,"audio":False})
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("runtime",type=Path);p.add_argument("fixture",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args()
    runtime=a.runtime.resolve();fixture=a.fixture.resolve();out=a.out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    video=out/"native-match.mp4";trace=out/"match.ndjson"
    from release_evidence import stamp,sha
    report=stamp({"schema":1,"authoritative":False,"productionEnabled":False,"status":"incomplete",
       "presentation":"original-native-opengl-window","simulation":"pinned-league-soccer","audio":False,
       "fixtureSha256":sha(fixture),"videoRedistributionApproved":False},runtime,"native-video-pilot")
    save(out/"native-video-report.json",report)
    with (out/"runner.log").open("wb") as log:
        subprocess.run(["bash",str(HERE/"run-frozen.sh"),str(runtime),str(fixture),str(trace),"0"],
            env=env_for(os.environ,video),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1000)
    spec=importlib.util.spec_from_file_location("fixed",HERE/"fixed-duration.py")
    fixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixed)
    with trace.open() as f:clock=fixed.verify(json.loads(line) for line in f)
    captured=json.loads(video.with_suffix(".capture.json").read_text());media=measure(video)
    checks=assess(captured,media)
    complete=checks["captureBeforeKickoff"] and checks["videoLengthAtLeastObservedMatch"]
    report.update(status="manual-review-required" if complete else "capture-coverage-inconclusive",
      nativeClock=clock,video=media,checks=checks,traceSha256=sha(trace),videoSha256=sha(video),
      note="Original window recorded, no reconstructed players. Silent local recording; startup/end screens possible. No live streaming, exact video alignment or production capacity claim.")
    save(out/"native-video-report.json",report)
    print(json.dumps(report,indent=2))
    if not complete:raise SystemExit(2)
if __name__=="__main__":
    import sys
    if len(sys.argv)==4 and sys.argv[1]=="--capture-window":capture_window(sys.argv[2],int(sys.argv[3]))
    else:main()
