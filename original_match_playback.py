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



def track_timing(path):
    """Independent per-track timing; container duration alone can hide a short track."""
    data=json.loads(subprocess.check_output(['ffprobe','-v','error',
        '-show_entries','stream=codec_type,start_time,duration,avg_frame_rate,nb_frames,sample_rate',
        '-of','json',str(path)],text=True,timeout=30))
    tracks={}
    for kind in ('video','audio'):
        matching=[s for s in data.get('streams',[]) if s.get('codec_type')==kind]
        if len(matching)!=1:
            raise ValueError('Expected exactly one '+kind+' track')
        s=matching[0]
        start=float(s['start_time'])
        duration=float(s['duration'])
        if not math.isfinite(start) or not math.isfinite(duration) or duration<=0:
            raise ValueError('Invalid '+kind+' track timing')
        tracks[kind]=dict(start=start,duration=duration,end=start+duration,
            frames=s.get('nb_frames'),frameRate=s.get('avg_frame_rate'),sampleRate=s.get('sample_rate'))
    return tracks


def exact_plan(tracks):
    video,audio=tracks['video'],tracks['audio']
    if video['duration']<TARGET_SECONDS or audio['duration']<TARGET_SECONDS:
        raise ValueError('Both original tracks must cover at least 300 seconds')
    if max(abs(video['start']),abs(audio['start']))>.05 or abs(video['start']-audio['start'])>.05:
        raise ValueError('Recording tracks must start near the shared zero epoch')
    if abs(video['end']-audio['end'])>.1:
        raise ValueError('Original tracks end more than 100 ms apart')
    if max(video['duration'],audio['duration'])>6*3600:
        raise ValueError('Recording exceeds six-hour limit')
    return playback_plan(video['duration'])


def convert_exact(source,destination):
    """Exactly 9000 frames and a 300s audio track, strictly offline.
    
    A short or mismatched source is rejected rather than stretched into a match.
    At most 100ms of terminal codec rounding can be filled; no event is generated.
    This validates encoded tracks, not the recording's native match provenance.
    """
    import hashlib
    import os
    source,destination=Path(source),Path(destination)
    if source.is_symlink() or not source.is_file() or destination.exists() or destination.is_symlink() or destination.suffix.lower()!='.mp4':
        raise ValueError('Use an existing recording and a new MP4 destination')
    def sha(path):
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):
                h.update(block)
        return h.hexdigest()
    source_digest=sha(source)
    tracks=track_timing(source)
    plan=exact_plan(tracks)
    speed=plan['playbackSpeed']
    factors=plan['audioTempoFactors']
    video_filter=(f'setpts=(PTS-STARTPTS)/{speed:.12g},fps=30,'
                  'tpad=stop_mode=clone:stop_duration=0.1,trim=end_frame=9000,setpts=N/(30*TB)')
    audio_filter=('asetpts=PTS-STARTPTS,'+','.join(f'atempo={x:.12g}' for x in factors)+
                  ',aresample=48000,apad=pad_dur=0.1,atrim=duration=300,asetpts=N/SR/TB')
    with tempfile.TemporaryDirectory(prefix='.native-exact-playback-',dir=destination.parent) as tmp:
        output=Path(tmp)/'match.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),
            '-map','0:v:0','-vf',video_filter,'-c:v','libx264','-pix_fmt','yuv420p','-preset','fast','-crf','22',
            '-map','0:a:0','-af',audio_filter,'-c:a','aac','-b:a','128k',
            '-movflags','+faststart',str(output)],check=True,timeout=1800)
        actual=track_timing(output)
        video,audio=actual['video'],actual['audio']
        if (video['frames']!='9000' or video['frameRate']!='30/1' or audio['sampleRate']!='48000'
                or abs(video['duration']-300)>.001 or abs(audio['duration']-300)>.001
                or abs(video['start'])>.001 or abs(audio['start'])>.001):
            raise RuntimeError('Exact playback track verification failed: '+json.dumps(actual))
        seconds,has_audio=inspect(output)
        if abs(seconds-300)>.001 or not has_audio or sha(source)!=source_digest:
            raise RuntimeError('Exact playback duration or source identity verification failed')
        output_digest=sha(output)
        os.link(output,destination)
    return dict(plan,outputSeconds=seconds,outputFrames=9000,outputFps=30,
                audioPreserved=True,sourceTracks=tracks,outputTracks=actual,
                sourceSha256=source_digest,outputSha256=output_digest,
                terminalPaddingBudgetSeconds=.1,exactEncodedDurationVerified=True,
                sourceRecordingVerifiedComplete=False,physicalAVSyncVerified=False,
                live=False,nativeSimulationChanged=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--exact',action='store_true',help='Require complete 300s encoded A/V duration')
    args=parser.parse_args()
    operation=convert_exact if args.exact else convert
    print(json.dumps(operation(args.source,args.destination),indent=2))


if __name__=='__main__':
    main()
