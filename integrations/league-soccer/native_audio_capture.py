"""Per-match private PulseAudio sink for the original OpenAL mix, and measured AAC evidence."""
import array,contextlib,json,math,os,re,subprocess,sys,tempfile,time
from pathlib import Path
def require(ok,message):
    if not ok:raise ValueError(message)
def audio_config(path):
    text=path.read_text()
    for key,value in (("audio_renderer","openal"),("audio_volume","0.500000")):
        pattern=r'^\s*"'+re.escape(key)+r'"\s+"[^"\n]*"\s*$'
        text=re.sub(pattern,'"'+key+'" "'+value+'"',text,flags=re.M) if re.search(pattern,text,re.M) else text.rstrip()+'\n"'+key+'" "'+value+'"\n'
    dest=path.with_name("native-audio.config");dest.write_text(text);return dest
@contextlib.contextmanager
def private_audio(out):
    # Private directory and Unix socket, no TCP, no host microphone or default sink.
    with tempfile.TemporaryDirectory(prefix="tribun-pulse-") as d:
        root=Path(d);sock=root/"native"
        env=os.environ.copy()
        for key in ("PULSE_SERVER","PULSE_SINK","PULSE_SOURCE","PULSE_COOKIE","ALSOFT_CONF","ALSOFT_LOGFILE"):
            env.pop(key,None)
        env.update(PULSE_SERVER="unix:"+str(sock),PULSE_RUNTIME_PATH=str(root),PULSE_STATE_PATH=str(root),
                   PULSE_SINK="tribun_match",PULSE_SOURCE="tribun_match.monitor",ALSOFT_DRIVERS="pulse")
        with (out/"native-audio.log").open("wb") as log:
            proc=subprocess.Popen(["pulseaudio","-n","--daemonize=no","--use-pid-file=no","--exit-idle-time=-1",
                "--disable-shm=true","--log-target=stderr",
                "--load=module-native-protocol-unix socket="+str(sock)+" auth-anonymous=1",
                "--load=module-null-sink sink_name=tribun_match rate=48000 channels=2"],env=env,stdout=log,stderr=subprocess.STDOUT)
            try:
                for _ in range(100):
                    if proc.poll() is not None:raise RuntimeError("Private audio server exited")
                    if sock.exists():
                        p=subprocess.run(["pactl","list","short","sources"],env=env,capture_output=True,text=True,timeout=3)
                        if p.returncode==0 and "tribun_match.monitor" in p.stdout:break
                    time.sleep(.1)
                else:raise RuntimeError("Private audio monitor unavailable")
                subprocess.run(["pactl","set-default-sink","tribun_match"],env=env,check=True,timeout=3)
                yield env
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
def pcm_metrics(stream,rate=48000):
    total=0;active=0;windows=0;peak=0;energy=0
    while True:
        raw=stream.read(rate*2)
        if not raw:break
        require(len(raw)%2==0,"Invalid PCM bytes")
        a=array.array("h");a.frombytes(raw)
        if sys.byteorder!="little":a.byteswap()
        count=len(a);total+=count;windows+=1
        squares=sum(int(x)*int(x) for x in a);energy+=squares
        peak=max(peak,max(abs(x) for x in a))
        if math.sqrt(squares/count)>=32768*10**(-45/20):active+=1
    require(total>0,"Empty decoded audio")
    def db(v):return round(20*math.log10(max(v/32768,1e-9)),2)
    return {"durationSeconds":total/rate,"windows":windows,"nonSilentWindows":active,"peakDbfs":db(peak),"rmsDbfs":db(math.sqrt(energy/total))}
def audit_audio(playlist,wall):
    require(type(wall) in (int,float) and math.isfinite(wall) and wall>0,"Missing observed match clock")
    common=["-protocol_whitelist","file,crypto,data","-allowed_extensions","ALL"]
    info=json.loads(subprocess.check_output(["ffprobe","-v","error",*common,"-show_streams","-of","json",str(playlist)],timeout=60))
    tracks=[s for s in info["streams"] if s.get("codec_type")=="audio"]
    require(len(tracks)==1,"Expected one audio track")
    a=tracks[0]
    require(a["codec_name"]=="aac" and a.get("profile")=="LC" and int(a["sample_rate"])==48000 and a["channels"]==2,"Unexpected AAC profile")
    proc=subprocess.Popen(["ffmpeg","-nostdin","-v","error",*common,"-i",str(playlist),"-map","0:a:0",
        "-ac","1","-ar","48000","-f","s16le","-"],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        with proc.stdout as f:metrics=pcm_metrics(f)
        require(proc.wait(timeout=30)==0,"Audio decode failed")
    finally:
        if proc.poll() is None:proc.kill();proc.wait()
    return {"codec":"aac-lc","sampleRate":48000,"channels":2,**metrics,
        "nonSilentCoveragePassed":metrics["durationSeconds"]>=wall-3 and metrics["nonSilentWindows"]>=10,
        "note":"Decoded audio energy, not proof of specific sound events or A/V synchronization."}
