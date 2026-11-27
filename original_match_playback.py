"""External five-minute playback of a completed native match recording.

This is delayed playback, not live simulation. Never changes the engine or
its settings. The operator supplies an already recorded full match.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile

TARGET_SECONDS=300.0


def playback_plan(seconds):
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=6*3600:
        raise ValueError('Invalid recording duration')
    speed=max(1.0,seconds/TARGET_SECONDS)
    # atempo factors <=2 avoid the filter's high-speed sample skipping.
    remainder=speed
    factors=[]
    while remainder>2:
        factors.append(2.0)
        remainder/=2
    factors.append(remainder)
    return dict(sourceSeconds=seconds,targetSeconds=min(seconds,TARGET_SECONDS),
                playbackSpeed=speed,audioTempoFactors=factors,
                live=False,nativeSimulationChanged=False)


def inspect(path):
    report=json.loads(subprocess.check_output(['ffprobe','-v','error',
        '-show_entries','format=duration:stream=codec_type','-of','json',str(path)],text=True))
    kinds=[s.get('codec_type') for s in report.get('streams',[])]
    if 'video' not in kinds:
        raise ValueError('Completed video recording required')
    return float(report['format']['duration']), 'audio' in kinds


def convert(source,destination):
    source,destination=Path(source),Path(destination)
    if source.is_symlink() or not source.is_file() or destination.exists() or destination.is_symlink() or destination.suffix.lower()!='.mp4':
        raise ValueError('Use an existing recording and a new MP4 destination')
    seconds,audio=inspect(source)
    plan=playback_plan(seconds)
    # Use all source time, never select a highlight or create game events.
    # A slight speed margin accommodates encoded frame rounding at 30 fps.
    speed=plan['playbackSpeed']
    if seconds>=TARGET_SECONDS:
        speed=seconds/(TARGET_SECONDS-.15)
    remainder=speed
    factors=[]
    while remainder>2:
        factors.append(2.)
        remainder/=2
    factors.append(remainder)
    with tempfile.TemporaryDirectory(prefix='.native-playback-',dir=destination.parent) as tmp:
        output=Path(tmp)/'match.mp4'
        cmd=['ffmpeg','-nostdin','-v','error','-i',str(source),'-map','0:v:0',
             '-vf',f'setpts=PTS/{speed:.12g},fps=30','-c:v','libx264','-pix_fmt','yuv420p',
             '-preset','fast','-crf','22']
        if audio:
            cmd+=['-map','0:a:0','-af',','.join(f'atempo={x:.12g}' for x in factors),
                  '-c:a','aac','-b:a','128k']
        else:
            cmd+=['-an']
        cmd+=['-movflags','+faststart',str(output)]
        subprocess.run(cmd,check=True)
        observed,has_audio=inspect(output)
        expected=seconds/speed
        if observed>TARGET_SECONDS or abs(observed-expected)>.25 or has_audio!=audio:
            raise RuntimeError('Playback duration/audio did not validate')
        # Hard link publication refuses overwriting an existing destination.
        import os
        os.link(output,destination)
    return dict(plan,actualPlaybackSpeed=speed,outputSeconds=observed,
                audioPreserved=audio,allSourceTimeSelected=True,
                sourceRecordingVerifiedComplete=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    print(json.dumps(convert(args.source,args.destination),indent=2))


if __name__=='__main__':
    main()
