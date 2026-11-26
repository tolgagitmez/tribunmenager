"""Loopback-only original-renderer HLS diagnostic. Not league authorization."""
import argparse,importlib.util,json,os,re,secrets,subprocess,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from release_evidence import stamp,sha
from native_audio_capture import audit_audio
from native_media_audit import audit_media
from native_motion_audit import audit as audit_motion
from native_capture_failure import summarize as capture_failure
from native_video_control import ControlBridge
from native_roster import plan_from_config,verify_halftime
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("video",HERE/"native-video-pilot.py")
V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)
def write_json(path,data):
    tmp=path.with_suffix(".tmp");tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+"\n");tmp.replace(path)
def allowed(name):
    return name in ("live.m3u8","init.mp4") or bool(re.fullmatch(r"segment-[0-9]{5}\.m4s",name))
def make_server(media,token,state,control=None):
    prefix="/"+token+"/"
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def route(self):
            if self.headers.get("Host")!=f"127.0.0.1:{self.server.server_port}":return None,None
            path=urlsplit(self.path).path
            if path.startswith(prefix):return path[len(prefix):],None
            if control:
                for side,key in enumerate(control.tokens):
                    base="/"+key+"/"
                    if path.startswith(base):return path[len(base):],side
            return None,None
        def send_json(self,status,value):
            data=json.dumps(value,allow_nan=False).encode()
            self.send_response(status);self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)));self.send_header("Cache-Control","no-store")
            self.send_header("Referrer-Policy","no-referrer");self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_POST(self):
            name,side=self.route()
            if name!="tactics.json" or side is None or control is None:self.send_error(404);return
            if self.headers.get("Origin")!=f"http://127.0.0.1:{self.server.server_port}" or self.headers.get("Content-Type")!="application/json":
                self.send_error(403);return
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=4096:raise ValueError("Invalid request length")
                self.connection.settimeout(3)
                body=json.loads(self.rfile.read(size))
                self.send_json(200,control.submit(side,body))
            except control.error_type as e:self.send_json(e.status,{"error":str(e)})
            except (ValueError,TimeoutError):self.send_json(400,{"error":"Geçersiz komut."})
        def do_GET(self):
            if self.headers.get("Host")!=f"127.0.0.1:{self.server.server_port}":
                self.send_error(403);return
            name,side=self.route()
            if name is None:self.send_error(404);return
            if name=="tactics.json":
                if side is None or control is None:self.send_error(404);return
                self.send_json(200,control.read(side));return
            if name in ("","index.html"):
                data=(HERE/"native-live-video.html").read_bytes();mime="text/html; charset=utf-8"
            elif name=="player.js":
                data=(HERE/"native-live-video.js").read_bytes();mime="text/javascript; charset=utf-8"
            elif name=="status.json":
                data=json.dumps({**state,"managerSide":side}).encode();mime="application/json"
            elif allowed(name):
                p=media/name
                if not p.is_file() or p.is_symlink():self.send_error(404);return
                data=p.read_bytes();mime="application/vnd.apple.mpegurl" if name.endswith(".m3u8") else "video/mp4"
            else:self.send_error(404);return
            self.send_response(200);self.send_header("Content-Type",mime);self.send_header("Content-Length",str(len(data)))
            self.send_header("Cache-Control","no-store");self.send_header("Referrer-Policy","no-referrer")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'none'; script-src 'self'; connect-src 'self'; media-src 'self' blob:; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
    return ThreadingHTTPServer(("127.0.0.1",0),Handler)
def validate_playlist(media):
    p=media/"live.m3u8";lines=p.read_text().splitlines()
    V.require(lines[0]=="#EXTM3U" and "#EXT-X-ENDLIST" in lines and '#EXT-X-MAP:URI="init.mp4"' in lines,"Incomplete HLS playlist")
    segments=[s for s in lines if s and not s.startswith("#")]
    durations=[float(s.split(":",1)[1].split(",")[0]) for s in lines if s.startswith("#EXTINF:")]
    V.require(len(segments)==len(durations)>0 and len(set(segments))==len(segments) and all(allowed(s) and s.endswith(".m4s") and (media/s).is_file() for s in segments),"Invalid segment set")
    V.require(all(0<d<=3 for d in durations),"Unexpected segment duration")
    return {"segmentCount":len(segments),"durationSeconds":sum(durations),"playlistSha256":sha(p),
        "bytes":sum((media/s).stat().st_size for s in segments)+(media/"init.mp4").stat().st_size}
def main():
    import signal
    def terminate(signum, frame):
        raise KeyboardInterrupt("Native supervisor termination requested")
    signal.signal(signal.SIGTERM, terminate)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("runtime",type=Path);p.add_argument("fixture",type=Path);p.add_argument("out",type=Path)
    p.add_argument("--linger",type=int,default=15);p.add_argument("--audio",action="store_true");p.add_argument("--interactive",action="store_true");p.add_argument("--halftime-plan",action="store_true")
    a=p.parse_args();V.require(0<=a.linger<=120,"Invalid linger")
    runtime=a.runtime.resolve();fixture=a.fixture.resolve();out=a.out.resolve()
    config=json.loads(fixture.read_text());plans=plan_from_config(config)
    V.require(bool(plans)==a.halftime_plan,"Use explicit --halftime-plan with prepared changes")
    out.mkdir(parents=True,exist_ok=False);media=out/"hls";media.mkdir()
    state={"phase":"starting","engine":"league-soccer","authoritative":False,"audio":False,"audioRequested":a.audio}
    trace=out/"match.ndjson";video=out/"native-match.mp4"
    control=ControlBridge(config,out/"commands",trace) if a.interactive else None
    token=secrets.token_urlsafe(24);server=make_server(media,token,state,control)
    url=f"http://127.0.0.1:{server.server_port}/{token}/"
    # URL is private to local filesystem; never included in report or artifact.
    (out/"local-url.txt").write_text(url+"\n");(out/"local-url.txt").chmod(0o600)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    if control:
        for side,key in enumerate(control.tokens):
            path=out/f"local-manager-{side}.txt"
            path.write_text(f"http://127.0.0.1:{server.server_port}/{key}/\n");path.chmod(0o600)
    report=stamp({"schema":1,"authoritative":False,"productionEnabled":False,"status":"incomplete",
        "fixtureSha256":sha(fixture),"videoRedistributionApproved":False,"transport":"local-hls-fmp4"},runtime,"native-live-video")
    report_path=out/"live-report.json";write_json(report_path,report)
    env=V.env_for(os.environ,video);env["TRIBUN_NATIVE_HLS_DIR"]=str(media);env["TRIBUN_NATIVE_AUDIO_CAPTURE"]="1" if a.audio else "0"
    if a.halftime_plan:env["TRIBUN_NATIVE_EXPERIMENTAL_SUBSTITUTIONS"]="1"
    if control:
        env["TRIBUN_NATIVE_VIDEO_CONTROL"]="1";env["TRIBUN_LEAGUE_SOCCER_COMMAND_DIR"]=str(control.directory)
    first=None;started=time.monotonic()
    try:
        with (out/"runner.log").open("wb") as log:
            proc=subprocess.Popen(["bash",str(HERE/"run-frozen.sh"),str(runtime),str(fixture),str(trace),"0"],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                while proc.poll() is None:
                    if control:control.drain()
                    if first is None and (media/"live.m3u8").is_file() and any(media.glob("segment-*.m4s")):
                        first=time.monotonic();state["phase"]="streaming";state["firstSegmentObserved"]=True
                    if time.monotonic()-started>1000:raise TimeoutError("Native live capture exceeded limit")
                    time.sleep(.1)
                if control:control.drain();control.close()
                if proc.returncode:
                    report["runnerExit"]=proc.returncode
                    raise RuntimeError("Native live capture failed")
            finally:
                if proc.poll() is None:
                    import signal
                    os.killpg(proc.pid,signal.SIGTERM)
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        fixed_spec=importlib.util.spec_from_file_location("fixed",HERE/"fixed-duration.py")
        fixed=importlib.util.module_from_spec(fixed_spec);fixed_spec.loader.exec_module(fixed)
        with trace.open() as f:clock=fixed.verify(json.loads(l) for l in f)
        playlist=validate_playlist(media);capture=json.loads(video.with_suffix(".capture.json").read_text())
        checks=V.assess(capture,{"durationSeconds":playlist["durationSeconds"],"averageEncodedPacketsPerSecond":0})
        checks.pop("encodedCadenceAtLeast20")
        checks["firstSegmentBeforeObservedFinal"]=first is not None and capture["finalObserved"] is not None and first<capture["finalObserved"]
        complete=all(checks[k] for k in ("captureBeforeKickoff","videoLengthAtLeastObservedMatch","firstSegmentBeforeObservedFinal"))
        roster=None
        if a.halftime_plan:
            roster=verify_halftime(trace,Path(str(trace)+".fixture.json"),Path(str(trace)+".season.json"))
            complete=complete and roster["allPlannedChangesObserved"]
        media_audit=audit_media(media/"live.m3u8",a.audio,checks["observedWallSeconds"])
        complete=complete and media_audit["timelinePassed"]
        audio=None
        if a.audio:
            V.require(capture.get("audio") is True and capture.get("nativeSinkInputObserved") is True,"No native sound producer observed")
            audio=audit_audio(media/"live.m3u8",checks["observedWallSeconds"])
            complete=complete and audio["nonSilentCoveragePassed"]
        control_report=control.report() if control else None
        if control_report:
            complete=complete and control_report["traceEvidence"]["consistent"]
        motion=None
        if os.environ.get("TRIBUN_AV_MOTION_AUDIT")=="1":
            motion=audit_motion(media/"live.m3u8")
            write_json(out/"native-motion-report.json",motion)
        report.update(status="local-live-evidence" if complete else "coverage-inconclusive",nativeClock=clock,audio=audio,
          gpuPreflight=json.loads((out/"gpu-preflight.json").read_text()) if (out/"gpu-preflight.json").is_file() else None,
          motionAudit=motion,renderProbe=capture.get("renderProbe"),softwareGLWorkers=capture.get("softwareGLWorkers",2),
          videoEncoder=capture.get("videoEncoder","x264"),encoderPreflight=json.loads((out/"encoder-preflight.json").read_text()) if (out/"encoder-preflight.json").is_file() else None,
          playlist=playlist,mediaTimeline=media_audit,checks=checks,traceSha256=sha(trace),control=control_report,roster=roster,
          note="Loopback only, 2-second HLS segments. Audio when requested is native OpenAL mix, not synthetic effects. Encoded A/V timestamp continuity checked; event-by-event sound and perceptual A/V alignment not verified. Browser latency, actual renderer FPS, asset clearance, league authorization and capacity not qualified. Manager status is current engine time, not synchronized video time.")
        state["audio"]=bool(audio and audio["nonSilentCoveragePassed"]);state["phase"]="finished" if complete else "failed";write_json(report_path,report)
        if not complete:raise RuntimeError("Live coverage inconclusive")
        print(json.dumps(report,indent=2),flush=True);time.sleep(a.linger)
    except BaseException as error:
        state["phase"]="failed"
        if control:control.close()
        report.update(status="failed",failureType=type(error).__name__,failureMessage=str(error)[:500],
                      captureFailure=capture_failure(out))
        write_json(report_path,report)
        raise
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
if __name__=="__main__":main()
