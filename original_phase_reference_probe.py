"""Collect bounded native smoke screen candidates around upstream phase markers.

Capture receipt time is not exact game-state time. These are unreviewed
reference candidates, never a production halftime calibration.
"""
from collections import deque
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

import original_engine as engine
from original_capture_probe import ACTIVE,HALF,FULL,DONE,match_intervals
from original_halftime_gate import WIDTH,HEIGHT
from original_native_saves_probe import populate

FPS=20
FRAME_BYTES=WIDTH*HEIGHT
PRE=.75
POST=.75
MAX_EVENTS=8
MAX_FRAMES_PER_EVENT=36

class PhaseSamples:
    def __init__(self):
        self.ring=deque(maxlen=40)
        self.events=[]
        self.lock=threading.Lock()
    def sample(self,t,data):
        if len(data)!=FRAME_BYTES:
            raise ValueError('Incomplete grayscale frame')
        with self.lock:
            self.ring.append((t,data))
            for event in self.events:
                if event['time']<=t<=event['time']+POST and len(event['frames'])<MAX_FRAMES_PER_EVENT:
                    event['frames'].append((t,data))
    def mark(self,t,marker,line):
        with self.lock:
            if len(self.events)>=MAX_EVENTS:
                raise RuntimeError('Too many native phase markers')
            self.events.append(dict(time=t,marker=marker,line=line,
                frames=[(at,data) for at,data in self.ring if t-PRE<=at<=t][-MAX_FRAMES_PER_EVENT:]))
    def export(self,output):
        events=[(e['time'],e['marker'],e['line']) for e in self.events]
        intervals,full,extra=match_intervals(events)
        output=Path(output)
        output.mkdir(mode=0o700)
        manifest=[]
        for i,event in enumerate(self.events):
            frames=event['frames']
            # Require pre-marker observations; post-DONE frames may not exist.
            if event['marker'] in (HALF,FULL) and sum(t<event['time'] for t,_ in frames)<2:
                raise RuntimeError('Insufficient pre-marker screen candidates')
            entries=[]
            for j,(t,data) in enumerate(frames):
                name=f'{i:02d}-{j:02d}.pgm'
                with (output/name).open('xb') as out:
                    out.write(f'P5\n{WIDTH} {HEIGHT}\n255\n'.encode())
                    out.write(data)
                entries.append(dict(file=name,receiptOffsetMs=round((t-event['time'])*1000,2),
                                    rawSha256=hashlib.sha256(data).hexdigest()))
            manifest.append(dict(marker=event['marker'],line=event['line'],frames=entries))
        return dict(events=manifest,fullTimeMarker=full,extraGameplayEntries=extra,
                    observedHalvesSeconds=[round(b-a,3) for a,b in intervals],
                    phaseMarkerOrderVerified=True,operatorReviewed=False,
                    visualCalibrationVerified=False,normalLeagueCalibrationVerified=False)

def run(output):
    env=engine.clean_env(os.environ)
    work=engine.cache_root()/engine.REVISION
    build=engine.verify_install(work,env)
    source=work/'source'
    config=source/'data/menu_smoke_full_match.config'
    samples=PhaseSamples()
    errors=[]
    with tempfile.TemporaryDirectory(prefix='native-phase-reference-') as tmp:
        session=Path(tmp)/'game'
        populate(build,session)
        engine.check_config(source,session)
        with tempfile.TemporaryFile() as capture_log,tempfile.TemporaryFile() as game_log:
            capture=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-f','x11grab',
                '-draw_mouse','0','-framerate',str(FPS),'-video_size',f'{WIDTH}x{HEIGHT}',
                '-i',env['DISPLAY'],'-pix_fmt','gray','-threads','1','-vsync','0',
                '-f','rawvideo','pipe:1'],env=env,stdout=subprocess.PIPE,stderr=capture_log)
            game=None
            def read_frames():
                try:
                    while True:
                        data=capture.stdout.read(FRAME_BYTES)
                        if not data:
                            return
                        samples.sample(time.monotonic(),data)
                except Exception as exc:
                    errors.append(str(exc))
            reader=threading.Thread(target=read_frames,daemon=True)
            reader.start()
            try:
                deadline=time.monotonic()+20
                while not samples.ring and time.monotonic()<deadline and capture.poll() is None:
                    time.sleep(.05)
                if not samples.ring:
                    raise RuntimeError('Capture failed to start')
                game=subprocess.Popen(['stdbuf','-oL','-eL',str(session/'gameplayfootball'),str(config)],
                    cwd=session,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
                def read_game():
                    try:
                        for line in game.stdout:
                            game_log.write(line.encode())
                            for marker in (ACTIVE,HALF,FULL,DONE):
                                if marker in line:
                                    samples.mark(time.monotonic(),marker,line.strip())
                    except Exception as exc:
                        errors.append(str(exc))
                logger=threading.Thread(target=read_game,daemon=True)
                logger.start()
                deadline=time.monotonic()+420
                while game.poll() is None and time.monotonic()<deadline:
                    if errors or capture.poll() is not None:
                        raise RuntimeError('Phase capture failed: '+str(errors))
                    time.sleep(.1)
                if game.wait(timeout=1)!=0:
                    raise RuntimeError('Native smoke failed')
                logger.join(timeout=5)
                if logger.is_alive() or errors:
                    raise RuntimeError('Native marker collection failed')
                time.sleep(.3)
            finally:
                for process in (game,capture):
                    if process is not None and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill();process.wait()
                reader.join(timeout=5)
            if reader.is_alive():
                raise RuntimeError('Frame reader did not stop')
        report=samples.export(output)
        report.update(revision=engine.REVISION,smokeConfigSha256=engine.digest(config),
                      defaultConfigSha256=engine.digest(source/'data/football.config'),
                      source='accelerated-upstream-quick-match',screen=[WIDTH,HEIGHT],
                      requestedCaptureFps=FPS,nativeSettingsPatched=False,
                      sourceTiming='capture and log receipt, not exact game phase timestamp')
        (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
    engine.verify_install(work,env)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--inside-private-xvfb',action='store_true')
    args=p.parse_args()
    if args.inside_private_xvfb:
        run(args.output)
    else:
        engine.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                     sys.executable,Path(__file__).resolve(),args.output.resolve(),
                     '--inside-private-xvfb'],engine.clean_env(os.environ))

if __name__=='__main__':
    main()
