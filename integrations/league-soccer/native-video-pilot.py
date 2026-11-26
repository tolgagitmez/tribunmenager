"""Private diagnostic: original native game window -> local MP4, no WebGL reconstruction."""
import argparse,hashlib,importlib.util,json,math,os,signal,subprocess,time
from pathlib import Path
from native_audio_capture import private_audio, audio_config
from native_audio_ownership import probe as audio_owner_probe
from native_hw_encoder import selected, preflight
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
    enabled=os.environ.get("TRIBUN_NATIVE_AUDIO_CAPTURE","0")
    require(enabled in ("0","1"),"Invalid audio capture flag")
    if enabled=="1":
        require(bool(os.environ.get("TRIBUN_NATIVE_HLS_DIR")),"Audio requires isolated HLS capture")
        with private_audio(Path(os.environ["TRIBUN_NATIVE_VIDEO_OUT"]).parent) as audio_env:
            _capture_window(str(audio_config(Path(config))),limit,audio_env)
    else:
        _capture_window(config,limit,None)
def _capture_window(config,limit,audio_env):
    video=Path(os.environ["TRIBUN_NATIVE_VIDEO_OUT"]);trace=Path(os.environ["TRIBUN_LEAGUE_SOCCER_TRACE"])
    require(video.is_absolute() and not video.exists() and video.suffix==".mp4","New absolute MP4 path required")
    hls=os.environ.get("TRIBUN_NATIVE_HLS_DIR")
    if hls:
        hls=Path(hls)
        require(hls.is_absolute() and hls.is_dir() and not any(hls.iterdir()),"New empty HLS directory required")
    backend,device,index,encoder_plan=selected(os.environ)
    require(backend=="x264" or hls,"Hardware encoding requires private HLS")
    init_args,encode_args,gop_args=encoder_plan
    encoder_threads=os.environ.get("TRIBUN_AV_X264_THREADS","2")
    require(encoder_threads in ("1","2"),"Invalid encoder thread count")
    require(encoder_threads=="2" or (hls and backend=="x264"),"Thread experiment requires local software HLS")
    if backend=="x264":
        encode_args=encode_args[:]
        encode_args[encode_args.index("-threads")+1]=encoder_threads
    if backend!="x264":
        save(video.parent/"encoder-preflight.json",preflight(backend,device,index))
    progress=video.with_suffix(".progress");capture_log=video.with_suffix(".capture.log")
    game_log=video.with_suffix(".game.log");offset=0;first=kickoff=final=None;last=None;encoder=None
    sink_input=False;next_audio_probe=0.0;audio_probes={};child_env=audio_env or os.environ.copy()
    gl_workers=os.environ.get("TRIBUN_AV_GL_WORKERS","2")
    swap_enabled=os.environ.get("TRIBUN_AV_SWAP_PROBE","0")
    require(gl_workers in ("1","2") and swap_enabled in ("0","1"),"Invalid render diagnostic")
    require((gl_workers=="2" and swap_enabled=="0") or (hls and not os.environ.get("TRIBUN_GPU_DISPLAY")),"Private software HLS required")
    game_env=dict(child_env,LP_NUM_THREADS=gl_workers)
    gpu_context=bool(os.environ.get("TRIBUN_GPU_DISPLAY"))
    if gpu_context:
        from native_gl_context import compile_hook
        require(not game_env.get("LD_PRELOAD"),"Existing preload not permitted")
        game_env.pop("LP_NUM_THREADS",None)
        gpu_hook=video.parent/"native-gl-context.so"
        compile_hook(HERE/"native_gl_context_hook.c",gpu_hook)
        game_env.update(LD_PRELOAD=str(gpu_hook),TRIBUN_NATIVE_GL_CONTEXT_LOG=str(video.parent/"native-gl-context.log"))
    swap_base=video.parent/"native-swaps"
    if swap_enabled=="1":
        from native_swap_probe import compile_probe
        require(not game_env.get("LD_PRELOAD"),"Existing preload not permitted")
        hook=video.parent/"native-swap-hook.so"
        compile_probe(HERE/"native_swap_hook.c",hook)
        game_env.update(LD_PRELOAD=str(hook),TRIBUN_SWAP_LOG=str(swap_base))
    with game_log.open("wb") as g,capture_log.open("wb") as e:
        game=subprocess.Popen(["timeout","--kill-after=10s",str(limit)+"s","./gameplayfootball",config],stdout=g,stderr=subprocess.STDOUT,env=game_env)
        try:
            deadline=time.monotonic()+120;window=None
            while time.monotonic()<deadline and game.poll() is None:
                found=subprocess.run(["xdotool","search","--onlyvisible","--name","^League Soccer$"],capture_output=True,text=True)
                if found.returncode==0 and found.stdout.strip():
                    if os.environ.get('TRIBUN_GPU_WSL_LOCAL')=='1':
                        from native_audio_ownership import descendants
                        owned=[]
                        for candidate in found.stdout.splitlines():
                            if not candidate.strip().isdigit():continue
                            pid=subprocess.run(['xdotool','getwindowpid',candidate.strip()],capture_output=True,text=True,timeout=5)
                            if pid.returncode==0 and pid.stdout.strip().isdigit() and int(pid.stdout.strip()) in descendants(game.pid):
                                owned.append(candidate.strip())
                        if len(owned)==1:window=owned[0];break
                    else:
                        window=found.stdout.splitlines()[0].strip();break
                time.sleep(.1)
            require(window is not None and window.isdigit(),"Native SDL window not found")
            if os.environ.get('TRIBUN_GPU_WSL_LOCAL')=='1':
                # Refuse a software game context before starting capture.
                from native_gl_context import verify
                context_path=video.parent/'native-gl-context.log'
                until=time.monotonic()+10
                while not context_path.is_file() and game.poll() is None and time.monotonic()<until:time.sleep(.05)
                context=verify(context_path,json.loads((video.parent/'gpu-preflight.json').read_text()))
                save(video.parent/'native-gl-context.json',context)
            window_geometry=None
            requested_size=os.environ.get("TRIBUN_AV_RENDER_SIZE")
            if requested_size:
                from native_render_resolution import verify_geometry
                geometry=subprocess.check_output(["xdotool","getwindowgeometry","--shell",window],text=True,timeout=5)
                window_geometry=verify_geometry(geometry,requested_size)
            output_args=["-movflags","+faststart",str(video)]
            if hls:
                output_args=[*gop_args,
                  "-f","hls","-hls_time","2","-hls_list_size","0","-hls_playlist_type","event","-hls_segment_type","fmp4",
                  "-hls_fmp4_init_filename","init.mp4","-hls_flags","independent_segments+temp_file",
                  "-hls_segment_filename",str(hls/"segment-%05d.m4s"),str(hls/"live.m3u8")]
            audio_args=["-an"] if audio_env is None else ["-thread_queue_size","512","-f","pulse","-i","tribun_match.monitor","-map","0:v:0","-map","1:a:0","-c:a","aac","-profile:a","aac_low","-b:a","96k","-ar","48000","-ac","2"]
            filter_threads=os.environ.get("TRIBUN_AV_FILTER_THREADS","0")
            require(filter_threads in ("0","1"),"Invalid diagnostic filter threads")
            require(filter_threads=="0" or hls,"Filter experiment requires local HLS")
            filter_args=[] if filter_threads=="0" else ["-filter_threads","1"]
            if not hls:
                encode_args=["-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2","-c:v","libx264","-threads","2","-preset","ultrafast","-crf","25","-pix_fmt","yuv420p"]
            encoder=subprocess.Popen(["ffmpeg","-nostdin","-hide_banner","-loglevel","warning","-y",*init_args,"-thread_queue_size","512","-f","x11grab",
              "-draw_mouse","0","-framerate","25","-window_id",window,"-i",os.environ["DISPLAY"],
              *audio_args,*filter_args,*encode_args,"-progress",str(progress),*output_args],stdout=e,stderr=subprocess.STDOUT,env=child_env)
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
                if audio_env is not None and not sink_input and time.monotonic()>=next_audio_probe:
                    status=audio_owner_probe(child_env,game.pid)
                    audio_probes[status]=audio_probes.get(status,0)+1
                    save(video.parent/"native-audio-ownership.json",{"ownedInputObserved":status=="owned","probeCounts":audio_probes})
                    sink_input=status=="owned";next_audio_probe=time.monotonic()+2
                if encoder.poll() is not None and final is None:raise RuntimeError("Video encoder stopped before full time")
                time.sleep(.075)
            drain()
            require(game.returncode==0 and last and last.get("done") is True,"Native match did not complete")
        finally:
            stop(encoder);stop(game)
    logs=game_log.read_text(errors="replace");print(logs)
    require("[menu-smoke] Full match complete:" in logs and "[menu-smoke] Full-match verification succeeded, quitting test run" in logs,"Missing native completion markers")
    if audio_env is not None:
        require("falling back to silent audio" not in logs and "using silent audio" not in logs,"Native OpenAL fallback to silent audio")
        require(sink_input,"Native OpenAL owned sink input never observed")
    context_report=None
    if gpu_context:
        from native_gl_context import verify
        context_report=verify(video.parent/"native-gl-context.log",json.loads((video.parent/"gpu-preflight.json").read_text()))
        save(video.parent/"native-gl-context.json",context_report)
    swap_report=None
    if swap_enabled=="1":
        from native_swap_probe import summarize
        swap_report=summarize(swap_base,kickoff,final)
        save(video.parent/"native-render-report.json",swap_report)
    save(video.with_suffix(".capture.json"),{"firstEncodedObserved":first,"kickoffObserved":kickoff,"finalObserved":final,"windowId":window,"audio":audio_env is not None,"nativeSinkInputObserved":sink_input,"nativeSinkOwnershipVerified":sink_input,"audioProbeCounts":audio_probes,"videoEncoder":backend,"renderProbe":swap_report,"softwareGLWorkers":int(gl_workers),"encoderThreads":int(encoder_threads),"hardwareContext":context_report,"windowGeometry":window_geometry})
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("runtime",type=Path);p.add_argument("fixture",type=Path);p.add_argument("out",type=Path)
    p.add_argument("--halftime-plan",action="store_true",help="Quarantined preconfigured native substitutions")
    a=p.parse_args()
    runtime=a.runtime.resolve();fixture=a.fixture.resolve();out=a.out.resolve()
    from native_roster import plan_from_config, verify_halftime
    plans=plan_from_config(json.loads(fixture.read_text()))
    require(bool(plans)==a.halftime_plan,"Use explicit --halftime-plan with prepared changes")
    out.mkdir(parents=True,exist_ok=False)
    video=out/"native-match.mp4";trace=out/"match.ndjson"
    from release_evidence import stamp,sha
    report=stamp({"schema":1,"authoritative":False,"productionEnabled":False,"status":"incomplete",
       "presentation":"original-native-opengl-window","simulation":"pinned-league-soccer","audio":False,
       "fixtureSha256":sha(fixture),"videoRedistributionApproved":False},runtime,"native-video-pilot")
    save(out/"native-video-report.json",report)
    env=env_for(os.environ,video)
    if a.halftime_plan:env["TRIBUN_NATIVE_EXPERIMENTAL_SUBSTITUTIONS"]="1"
    with (out/"runner.log").open("wb") as log:
        subprocess.run(["bash",str(HERE/"run-frozen.sh"),str(runtime),str(fixture),str(trace),"0"],
            env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1000)
    spec=importlib.util.spec_from_file_location("fixed",HERE/"fixed-duration.py")
    fixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixed)
    with trace.open() as f:clock=fixed.verify(json.loads(line) for line in f)
    captured=json.loads(video.with_suffix(".capture.json").read_text());media=measure(video)
    checks=assess(captured,media)
    complete=checks["captureBeforeKickoff"] and checks["videoLengthAtLeastObservedMatch"]
    roster=None
    if a.halftime_plan:
        roster=verify_halftime(trace,Path(str(trace)+".fixture.json"),Path(str(trace)+".season.json"))
        complete=complete and roster["allPlannedChangesObserved"]
    report.update(status="manual-review-required" if complete else "capture-coverage-inconclusive",
      nativeClock=clock,video=media,checks=checks,roster=roster,traceSha256=sha(trace),videoSha256=sha(video),
      note="Original window recorded, no reconstructed players. Silent local recording; startup/end screens possible. No live streaming, exact video alignment or production capacity claim.")
    save(out/"native-video-report.json",report)
    print(json.dumps(report,indent=2))
    if not complete:raise SystemExit(2)
if __name__=="__main__":
    import sys
    if len(sys.argv)==4 and sys.argv[1]=="--capture-window":capture_window(sys.argv[2],int(sys.argv[3]))
    else:main()
