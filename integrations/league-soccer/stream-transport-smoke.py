"""Synthetic transport preflight only; never football/engine evidence."""
import argparse,importlib.util,json,subprocess,threading,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("live",HERE/"native-live-video.py")
L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
def main():
    p=argparse.ArgumentParser();p.add_argument("out",type=Path);p.add_argument("--audio",action="store_true")
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);media=out/"hls";media.mkdir()
    state={"phase":"streaming","audioRequested":a.audio,"authoritative":False}
    server=L.make_server(media,"transport-preflight",state)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    (out/"local-url.txt").write_text(f"http://127.0.0.1:{server.server_port}/transport-preflight/\n")
    command=["ffmpeg","-nostdin","-v","warning","-re","-f","lavfi","-i","testsrc2=size=640x360:rate=25"]
    if a.audio:command+=["-re","-f","lavfi","-i","sine=frequency=440:sample_rate=48000","-c:a","aac","-profile:a","aac_low","-ac","2"]
    else:command+=["-an"]
    command+=["-t","18","-c:v","libx264","-threads","2","-preset","ultrafast","-tune","zerolatency","-profile:v","baseline","-level:v","3.1","-pix_fmt","yuv420p","-g","50","-keyint_min","50","-sc_threshold","0","-f","hls","-hls_time","2","-hls_list_size","0","-hls_playlist_type","event","-hls_segment_type","fmp4","-hls_fmp4_init_filename","init.mp4","-hls_flags","independent_segments+temp_file","-hls_segment_filename",str(media/"segment-%05d.m4s"),str(media/"live.m3u8")]
    try:
        subprocess.run(command,check=True,timeout=40)
        state["phase"]="finished"
        result=L.validate_playlist(media)
        from native_media_audit import audit_media
        audit=audit_media(media/"live.m3u8",a.audio,15)
        (out/"transport-report.json").write_text(json.dumps({"syntheticOnly":True,"audio":a.audio,**result,"mediaTimeline":audit},indent=2))
        if not audit["timelinePassed"]:raise RuntimeError("Synthetic transport timestamp audit failed")
        time.sleep(10)
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
if __name__=="__main__":main()
