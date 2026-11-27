"""Isolated native OpenAL audio and X11 video capture into shared HLS segments.

The PulseAudio server exists only for this test. The game uses its original
audio renderer and upstream smoke fixture, not patched code or default files.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import array
import math

import original_engine as engine
from original_native_saves_probe import populate
from original_native_browser_probe import terminate,ACTIVE
from original_av_stream import encoder_args,read_playlist,segment_probe,publication_age_ms


def audible_rms(path):
    raw=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(path),
        '-map','0:a:0','-ac','1','-ar','16000','-f','s16le','pipe:1'],timeout=10)
    values=array.array('h',raw)
    if sys.byteorder!='little':
        values.byteswap()
    return math.sqrt(sum(x*x for x in values)/len(values))/32768 if values else 0


def run():
    env=engine.clean_env(os.environ)
    display=env.get('DISPLAY','')
    if not display.startswith(':') or not display[1:].split('.')[0].isdigit():
        raise RuntimeError('Private Xvfb required')
    work=engine.cache_root()/engine.REVISION
    build=engine.verify_install(work,env)
    with tempfile.TemporaryDirectory(prefix='native-av-') as tmp:
        root=Path(tmp)
        session=root/'game'
        populate(build,session)
        engine.check_config(work/'source',session)
        output=root/'hls'
        output.mkdir(mode=0o700)
        runtime=root/'pulse-runtime'
        runtime.mkdir(mode=0o700)
        socket=root/'pulse.sock'
        # Isolate default audio device routing from the host. No host sink or
        # microphone is captured; the private server has exactly one null sink.
        env.update(PULSE_SERVER='unix:'+str(socket),PULSE_RUNTIME_PATH=str(runtime),
                   PULSE_SINK='tribun_test',PULSE_SOURCE='tribun_test.monitor')
        pulse=game=encoder=None
        with tempfile.TemporaryFile() as log,tempfile.TemporaryFile() as audio_log,tempfile.TemporaryFile() as encoder_log:
            try:
                pulse=subprocess.Popen(['pulseaudio','-n','--daemonize=no','--exit-idle-time=-1',
                    '--load=module-native-protocol-unix socket='+str(socket)+' auth-anonymous=1',
                    '--load=module-null-sink sink_name=tribun_test rate=48000 channels=2'],
                    env=env,stdout=audio_log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+15
                while time.monotonic()<deadline and pulse.poll() is None:
                    if socket.exists() and subprocess.run(['pactl','info'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3).returncode==0:
                        break
                    time.sleep(.2)
                else:
                    raise RuntimeError('Private audio server unavailable')
                subprocess.run(['pactl','set-default-sink','tribun_test'],env=env,check=True,timeout=5)
                game=subprocess.Popen(['stdbuf','-oL','-eL',str(session/'gameplayfootball'),
                    str(work/'source/data/menu_smoke_full_match.config')],cwd=session,env=env,
                    stdout=log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+120
                while time.monotonic()<deadline and game.poll() is None:
                    log.seek(0)
                    text=log.read()
                    if b'falling back to silent audio' in text:
                        raise RuntimeError('Native OpenAL did not open private audio device')
                    if ACTIVE.encode() in text:
                        break
                    time.sleep(.2)
                else:
                    raise RuntimeError('Native match not active')
                encoder=subprocess.Popen(encoder_args(display,'tribun_test.monitor',output),
                    env=env,stdout=encoder_log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+35
                report=None
                while time.monotonic()<deadline and encoder.poll() is None and game.poll() is None:
                    if (output/'stream.m3u8').is_file():
                        report=read_playlist(output)
                        if len(report['segments'])>=3:
                            break
                    time.sleep(.25)
                else:
                    raise RuntimeError('Expected three live audiovisual segments')
                paths=[output/x['name'] for x in report['segments']]
                inspected=[segment_probe(p) for p in paths]
                rms=[audible_rms(p) for p in paths]
                if max(rms)<0.0001:
                    raise RuntimeError('Native capture contains no measurable audio')
                from original_hls_delivery_probe import verify_delivery
                delivery=verify_delivery(output)
                print(json.dumps(dict(nativeAVSegmentProbePassed=True,
                    delivery=delivery,
                    segments=len(paths),audioRms=rms,streamInfo=inspected,
                    playlistWindowSeconds=report['windowSeconds'],
                    newestSegmentPublicationAgeMs=publication_age_ms(paths[-1]),
                    audioSource='private PulseAudio sink monitor',
                    captureToScreenLatencyVerified=False,publicStreaming=False,
                    fullMatchVerified=False,acceleratedUpstreamSmoke=True,
                    nativeSettingsPatched=False)),flush=True)
            except Exception:
                for stream in (log,audio_log,encoder_log):
                    stream.seek(0)
                    print(stream.read()[-5000:].decode(errors='replace'),file=sys.stderr)
                raise
            finally:
                terminate(encoder)
                terminate(game)
                terminate(pulse)
    engine.verify_install(work,env)


if __name__=='__main__':
    if sys.argv[1:]==['--inside-private-xvfb']:
        run()
    elif len(sys.argv)==1:
        engine.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
            sys.executable,Path(__file__).resolve(),'--inside-private-xvfb'],engine.clean_env(os.environ))
    else:
        raise SystemExit('Usage: original_native_av_probe.py')
