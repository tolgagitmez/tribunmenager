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
from original_av_stream import encoder_args,read_playlist,read_segment,probe_streams,publication_age_ms


def audible_rms(media):
    raw=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i','pipe:0',
        '-map','0:a:0','-ac','1','-ar','16000','-f','s16le','pipe:1'],input=media,timeout=10)
    values=array.array('h',raw)
    if sys.byteorder!='little':
        values.byteswap()
    return math.sqrt(sum(x*x for x in values)/len(values))/32768 if values else 0


def full_native_capture(work,session,output,env,display,game_log,encoder_log):
    """Capture before native startup and drain both browsers after smoke end."""
    import hashlib
    import signal
    import threading
    from original_capture_probe import ACTIVE,HALF,FULL,DONE,match_intervals
    from original_av_stream import audit_packet_timeline,read_published_file,MAX_SEGMENT_BYTES
    from original_hls_relay import HLSRelay
    game=encoder=browser=None
    events=[]
    capture_begin=time.monotonic()
    try:
        encoder=subprocess.Popen(encoder_args(display,'tribun_test.monitor',output,
            fmp4=True,hd=True,retain=True),env=env,stdout=encoder_log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+25
        while time.monotonic()<deadline and encoder.poll() is None:
            if (output/'stream.m3u8').is_file():
                ready=read_playlist(output,fmp4=True)
                if len(ready['segments'])>=2:
                    if ready['mediaSequence']!=0:
                        raise RuntimeError('Initial native stream fragments missed')
                    break
            time.sleep(.1)
        else:
            raise RuntimeError('HD native capture not ready before game start')
        capture_ready=time.monotonic()
        with HLSRelay(output,max_clients=8) as server, tempfile.TemporaryFile() as browser_log:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                script=Path(__file__).resolve().parent/'tests/original-hls-browser.cjs'
                browser=subprocess.Popen(['node',str(script),f'http://127.0.0.1:{server.server_port}',
                    '--native-full'],env=env,stdout=browser_log,stderr=subprocess.STDOUT)
                game=subprocess.Popen(['stdbuf','-oL','-eL',str(session/'gameplayfootball'),
                    str(work/'source/data/menu_smoke_full_match.config')],cwd=session,env=env,
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
                silent=[]
                def read_game():
                    for line in game.stdout:
                        game_log.write(line.encode())
                        if 'falling back to silent audio' in line:
                            silent.append(line)
                        for marker in (ACTIVE,HALF,FULL,DONE):
                            if marker in line:
                                events.append((time.monotonic(),marker,line.strip()))
                logger=threading.Thread(target=read_game,daemon=True)
                logger.start()
                deadline=time.monotonic()+420
                while game.poll() is None and time.monotonic()<deadline:
                    if encoder.poll() is not None or browser.poll() is not None or silent:
                        raise RuntimeError('Native capture, browser, or original sound ended prematurely')
                    time.sleep(.1)
                if game.wait(timeout=1)!=0:
                    raise RuntimeError('Native full smoke failed')
                logger.join(timeout=5)
                if logger.is_alive() or silent:
                    raise RuntimeError('Native marker or audio capture failed')
                intervals,full_line,extra=match_intervals(events)
                if capture_ready>intervals[0][0] or encoder.poll() is not None:
                    raise RuntimeError('Capture did not cover both native half markers')
                time.sleep(1)
                encoder.send_signal(signal.SIGINT)
                code=encoder.wait(timeout=15)
                capture_end=time.monotonic()
                if code not in (0,255) or capture_end<intervals[-1][1]:
                    raise RuntimeError('Native encoder did not finalize cleanly')
                final=read_playlist(output,fmp4=True)
                count=final['mediaSequence']+len(final['segments'])
                if not final['ended'] or not 3<=count<=240:
                    raise RuntimeError('Invalid bounded final native manifest')
                if browser.wait(timeout=40)!=0:
                    raise RuntimeError('Native full browser playback failed')
                browser_log.seek(0)
                evidence=json.loads(browser_log.read().decode())
                if not evidence.get('nativeFullStreamBrowserEnded'):
                    raise RuntimeError('Missing native browser end evidence')
                paths=[output/f'segment-{i:06d}.m4s' for i in range(count)]
                hashes=[hashlib.sha256(read_published_file(path,MAX_SEGMENT_BYTES)[0]).hexdigest()
                        for path in paths]
                for viewer in evidence['results']:
                    if [f['sha256'] for f in viewer['fragments']]!=hashes:
                        raise RuntimeError('Browser and native archive fragment hashes disagree')
                timeline=audit_packet_timeline((read_segment(path)[0] for path in paths),fps=30)
                if not timeline['encodedTimelineVerified']:
                    raise RuntimeError('Native full encoded timeline failed: '+json.dumps(timeline))
                endpoint_errors=[]
                for viewer in evidence['results']:
                    # Compare presented video PTS to independently decoded last
                    # video endpoint, not the browser's combined A/V duration.
                    end_error=timeline['lastVideoEnd']-viewer['lastMediaTime']
                    if not math.isfinite(end_error) or not -0.05<=end_error<=0.15:
                        raise RuntimeError('Native final video frame missing: '+json.dumps(dict(
                            lastVideoEnd=timeline['lastVideoEnd'],lastAudioEnd=timeline['lastAudioEnd'],
                            lastPresented=viewer['lastMediaTime'],mediaDuration=viewer['mediaDuration'],
                            differenceSeconds=end_error)))
                    endpoint_errors.append(round(end_error*1000,3))
                evidence.update(nativeFullStreamPlaybackVerified=True,videoEndpointDifferencesMs=endpoint_errors)
                native_span=intervals[-1][1]-intervals[0][0]
                video_span=timeline['lastVideoEnd']-timeline['firstVideoPts']
                if video_span<native_span or abs(video_span-(capture_end-capture_begin))>5:
                    raise RuntimeError('Native encoded duration does not cover observed match span')
                evidence.update(nativeFullSmokeCaptured=True,nativeMarkerOrderVerified=True,
                    nativeMarkerReceiptSeconds=[dict(marker=m,seconds=round(t-capture_begin,3)) for t,m,_ in events],
                    activeHalfSeconds=[round(b-a,3) for a,b in intervals],
                    nativeMatchSpanSeconds=round(native_span,3),encodedVideoSeconds=round(video_span,3),
                    captureProcessSeconds=round(capture_end-capture_begin,3),fullTimeMarker=full_line,
                    duplicateActiveMarkers=extra,archiveFragmentCount=count,encodedTimeline=timeline,
                    acceleratedUpstreamSmoke=True,realTime300SecondMatchVerified=False,
                    physicalAVSyncVerified=False,frameToNativeEventAlignmentVerified=False,
                    nativeSettingsPatched=False,publicStreaming=False)
                from original_match_playback import replay_verified_capture
                evidence['fiveMinuteReplayCandidate']=replay_verified_capture(
                    output,hashes,evidence,output.parent/'private-replay.mp4')
                print(json.dumps(evidence),flush=True)
            except Exception:
                browser_log.seek(0)
                print(browser_log.read()[-12000:].decode(errors='replace'),file=sys.stderr)
                raise
            finally:
                terminate(browser)
                terminate(game)
                terminate(encoder)
                server.shutdown()
                thread.join(timeout=5)
    finally:
        terminate(browser)
        terminate(game)
        terminate(encoder)


def run(browser=False,full_native=False):
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
                if full_native:
                    full_native_capture(work,session,output,env,display,log,encoder_log)
                    engine.verify_install(work,env)
                    return
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
                encoder=subprocess.Popen(encoder_args(display,'tribun_test.monitor',output,fmp4=browser),
                    env=env,stdout=encoder_log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+35
                report=None
                while time.monotonic()<deadline and encoder.poll() is None and game.poll() is None:
                    if (output/'stream.m3u8').is_file():
                        report=read_playlist(output,fmp4=browser)
                        if len(report['segments'])>=3:
                            break
                    time.sleep(.25)
                else:
                    raise RuntimeError('Expected three live audiovisual segments')
                # Inspect the same captured fragments for both codecs and PCM
                # energy. Freeze the sample bytes before the window rolls.
                paths=[output/x['name'] for x in report['segments']]
                samples=[read_segment(path) for path in paths]
                inspected=[dict(**probe_streams(media),bytes=size) for media,size in samples]
                rms=[audible_rms(media) for media,_ in samples]
                if max(rms)<0.0001:
                    raise RuntimeError('Native capture contains no measurable audio')
                evidence=dict(nativeAVSegmentProbePassed=True,segments=len(paths),
                    fragmentedMp4=browser,audioRms=rms,streamInfo=inspected,
                    playlistWindowSeconds=report['windowSeconds'],
                    newestSegmentPublicationAgeMs=publication_age_ms(paths[-1]),
                    audioSource='private PulseAudio sink monitor',
                    captureToScreenLatencyVerified=False,publicStreaming=False,
                    fullMatchVerified=False,acceleratedUpstreamSmoke=True,
                    nativeSettingsPatched=False)
                if browser:
                    from original_av_stream import audit_packet_timeline
                    timeline=audit_packet_timeline([media for media,_ in samples])
                    evidence['encodedTimeline']=timeline
                    print(json.dumps(dict(nativeEncodedTimeline=timeline)),flush=True)
                    if not timeline['encodedTimelineVerified']:
                        raise RuntimeError('Native encoded A/V timeline exceeded continuity budget')
                    import threading
                    from original_hls_relay import HLSRelay
                    with HLSRelay(output,max_clients=8) as server:
                        worker=threading.Thread(target=server.serve_forever,daemon=True)
                        worker.start()
                        try:
                            script=Path(__file__).resolve().parent/'tests/original-hls-browser.cjs'
                            response=subprocess.run(['node',str(script),f'http://127.0.0.1:{server.server_port}'],env=env,capture_output=True,text=True,timeout=45)
                            if response.returncode or game.poll() is not None or encoder.poll() is not None:
                                raise RuntimeError('Native browser AV playback failed: '+response.stderr)
                            print(json.dumps(evidence),flush=True)
                            print(response.stdout,flush=True)
                        finally:
                            server.shutdown()
                            worker.join(timeout=5)
                    engine.verify_install(work,env)
                    return
                from original_hls_delivery_probe import verify_delivery
                evidence['delivery']=verify_delivery(output)
                print(json.dumps(evidence),flush=True)
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


def five_minute_transport():
    """Wall-clock 300s synthetic transport test; never native match evidence."""
    import threading
    from original_av_stream import encoding_args
    from original_hls_relay import HLSRelay
    env=engine.clean_env(os.environ)
    with tempfile.TemporaryDirectory(prefix='five-minute-hls-') as tmp, tempfile.TemporaryFile() as log:
        output=Path(tmp)
        begin=time.monotonic()
        encoder=subprocess.Popen(['ffmpeg','-nostdin','-v','error',
            '-re','-f','lavfi','-i','testsrc2=size=640x512:rate=30',
            '-re','-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
            '-t','300',*encoding_args(output,fmp4=True,hd=True)],
            env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+20
            while time.monotonic()<deadline and encoder.poll() is None:
                if (output/'stream.m3u8').is_file():
                    report=read_playlist(output,fmp4=True)
                    if len(report['segments'])>=2:
                        if report['mediaSequence']!=0:
                            raise RuntimeError('Missed initial synthetic fragments')
                        break
                time.sleep(.15)
            else:
                raise RuntimeError('HD synthetic stream did not start')
            with HLSRelay(output,max_clients=8) as server:
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                try:
                    script=Path(__file__).resolve().parent/'tests/original-hls-browser.cjs'
                    result=subprocess.run(['node',str(script),
                        f'http://127.0.0.1:{server.server_port}','--five-minute'],
                        env=env,capture_output=True,text=True,timeout=375)
                    if result.returncode:
                        raise RuntimeError('Five-minute browser test failed: '+result.stderr[-12000:])
                    if encoder.wait(timeout=10)!=0:
                        raise RuntimeError('HD synthetic encoder failed')
                    final=read_playlist(output,fmp4=True)
                    if not final['ended'] or final['mediaSequence']+len(final['segments'])!=150:
                        raise RuntimeError('Missing final encoded fragment')
                    wall=time.monotonic()-begin
                    if not 295<=wall<=360:
                        raise RuntimeError('Transport test not completed in expected real time')
                    evidence=json.loads(result.stdout)
                    if not evidence.get('fiveMinuteTransportVerified'):
                        raise RuntimeError('Missing browser evidence')
                    evidence.update(syntheticSource=True,nativeMatchVerified=False,
                                    testWallSeconds=round(wall,3),targetSeconds=300,
                                    sourceResolution=[640,512],encodedResolution=[1280,720],
                                    targetEncodedFps=30)
                    print(json.dumps(evidence),flush=True)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
        except Exception:
            log.seek(0)
            print(log.read()[-8000:].decode(errors='replace'),file=sys.stderr)
            raise
        finally:
            terminate(encoder)


if __name__=='__main__':
    if sys.argv[1:]==['--five-minute-transport']:
        five_minute_transport()
    elif sys.argv[1:] in (['--inside-private-xvfb'],['--inside-private-xvfb','--browser'],['--inside-private-xvfb','--native-full']):
        run(browser='--browser' in sys.argv,full_native='--native-full' in sys.argv)
    elif sys.argv[1:] in ([],['--browser'],['--native-full']):
        engine.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
            sys.executable,Path(__file__).resolve(),'--inside-private-xvfb',*sys.argv[1:]],engine.clean_env(os.environ))
    else:
        raise SystemExit('Usage: original_native_av_probe.py [--browser | --five-minute-transport | --native-full]')
